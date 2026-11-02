locals {
  effective_jobs = length(var.jobs) > 0 ? var.jobs : {
    (var.name) = {
      command         = []
      enabled         = true
      timezone        = "Asia/Kolkata"
      schedules       = []
      timeout_seconds = 1800
      memory          = "1Gi"
      secrets         = []
    }
  }
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = substr("${var.name}-rt", 0, 28)
  display_name = "${var.name} runtime"
}

# Cloud Run opens each mounted secret as this account while saving the job.
# The grant has to finish first. One account serves every job in this module.
resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each = toset(var.mounted_secret_ids)

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_job" "app" {
  for_each = local.effective_jobs

  depends_on = [google_secret_manager_secret_iam_member.runtime]

  project             = var.project_id
  name                = replace(each.key, "_", "-")
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = "${each.value.timeout_seconds}s"

      dynamic "volumes" {
        for_each = var.cloud_sql_instance == null ? [] : [var.cloud_sql_instance]
        content {
          name = "cloudsql"
          cloud_sql_instance {
            instances = [volumes.value]
          }
        }
      }

      containers {
        image   = var.image
        command = length(each.value.command) > 0 ? each.value.command : null

        resources {
          limits = {
            cpu    = "1"
            memory = each.value.memory
          }
        }

        env {
          name  = "APP_ENV"
          value = var.environment
        }

        env {
          name  = "SERVICE_NAME"
          value = each.key
        }

        # RESOURCE_PREFIX is the app prefix, used only when code builds a resource name.
        # It is not the Cloud Run job name.
        dynamic "env" {
          for_each = var.secret_prefix == "" ? [] : [var.secret_prefix]
          content {
            name  = "RESOURCE_PREFIX"
            value = env.value
          }
        }

        dynamic "env" {
          for_each = var.gcs_bucket_name == null ? [] : [var.gcs_bucket_name]
          content {
            name  = "GCS_BUCKET_NAME"
            value = env.value
          }
        }

        dynamic "env" {
          for_each = var.plain_env
          content {
            name  = env.key
            value = env.value
          }
        }

        # Mount <prefix>-<ENV_NAME> or var.secret_map[ENV_NAME] back into the variable the process reads.
        dynamic "env" {
          for_each = each.value.secrets
          content {
            name = env.value
            value_source {
              secret_key_ref {
                secret  = lookup(var.secret_map, env.value, startswith(env.value, "${var.secret_prefix}-") ? env.value : "${var.secret_prefix}-${env.value}")
                version = "latest"
              }
            }
          }
        }

        dynamic "env" {
          for_each = var.cloud_sql_instance == null ? [] : [var.cloud_sql_instance]
          content {
            name  = "CLOUD_SQL_CONNECTION_NAME"
            value = env.value
          }
        }

        dynamic "env" {
          for_each = var.db_secret_id == null ? [] : [var.db_secret_id]
          content {
            name  = "DB_PASSWORD_SECRET_ID"
            value = env.value
          }
        }

        dynamic "volume_mounts" {
          for_each = var.cloud_sql_instance == null ? [] : [var.cloud_sql_instance]
          content {
            name       = "cloudsql"
            mount_path = "/cloudsql"
          }
        }
      }
    }
  }
}

resource "google_project_iam_member" "cloudsql" {
  count = var.cloud_sql_instance == null ? 0 : 1

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

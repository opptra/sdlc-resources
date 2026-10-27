data "google_project" "current" {
  project_id = var.project_id
}

locals {
  # Domain restricted sharing rejects allUsers. These modes open the URL
  # and the application checks the caller.
  accepts_unauthenticated = contains(["app-login", "public", "shared-secret"], var.auth)
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = substr("${var.name}-rt", 0, 28)
  display_name = "${var.name} runtime"
}

# Cloud Run opens each mounted secret as this account while saving the service.
# The grant has to finish first. A job account grant does not cover this service.
resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each = toset(var.mounted_secret_ids)

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_service" "app" {
  depends_on = [google_secret_manager_secret_iam_member.runtime]

  project              = var.project_id
  name                 = var.name
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  iap_enabled          = var.auth == "iap"
  invoker_iam_disabled = local.accepts_unauthenticated
  deletion_protection  = false

  template {
    service_account = google_service_account.runtime.email

    dynamic "volumes" {
      for_each = var.cloud_sql_instance == null ? [] : [var.cloud_sql_instance]
      content {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [volumes.value]
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image   = var.image
      command = length(var.command) > 0 ? var.command : null

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "APP_ENV"
        value = var.environment
      }

      env {
        name  = "SERVICE_NAME"
        value = var.name
      }

      dynamic "env" {
        for_each = var.secret_prefix == "" ? [] : [var.secret_prefix]
        content {
          name  = "RESOURCE_PREFIX"
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

      # Same mount as a job: the variable name, filled from <prefix>-<ENV_NAME>.
      dynamic "env" {
        for_each = var.secrets
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = startswith(env.value, "${var.secret_prefix}-") ? env.value : "${var.secret_prefix}-${env.value}"
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

resource "google_project_iam_member" "cloudsql" {
  count = var.cloud_sql_instance == null ? 0 : 1

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_service_iam_member" "iap" {
  count = var.auth == "iap" ? 1 : 0

  project  = google_cloud_run_v2_service.app.project
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

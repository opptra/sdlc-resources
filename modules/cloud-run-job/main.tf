locals {
  effective_jobs = length(var.jobs) > 0 ? var.jobs : {
    (var.name) = {
      command         = []
      enabled         = true
      timezone        = "Asia/Kolkata"
      schedules       = []
      timeout_seconds = 1800
      memory          = "1Gi"
    }
  }
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = substr("${var.name}-rt", 0, 28)
  display_name = "${var.name} runtime"
}

resource "google_cloud_run_v2_job" "app" {
  for_each = local.effective_jobs

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

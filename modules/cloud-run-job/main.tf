resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "${var.name}-runtime"
  display_name = "${var.name} runtime"
}

resource "google_cloud_run_v2_job" "app" {
  project             = var.project_id
  name                = var.name
  location            = var.region
  deletion_protection = false

  template {
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

      containers {
        image = var.image

        env {
          name  = "APP_ENV"
          value = var.environment
        }

        env {
          name  = "SERVICE_NAME"
          value = var.name
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

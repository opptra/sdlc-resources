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
      }
    }
  }
}

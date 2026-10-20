data "google_project" "current" {
  project_id = var.project_id
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "${var.name}-runtime"
  display_name = "${var.name} runtime"
}

resource "google_cloud_run_v2_service" "app" {
  project             = var.project_id
  name                = var.name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  iap_enabled         = var.auth == "iap"
  deletion_protection = false

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
      image = var.image

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

resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.auth == "iap" ? 0 : 1

  project  = var.project_id
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "iap" {
  count = var.auth == "iap" ? 1 : 0

  project  = var.project_id
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

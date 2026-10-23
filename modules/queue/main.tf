resource "google_cloud_tasks_queue" "queue" {
  project  = var.project_id
  name     = var.name
  location = var.region

  rate_limits {
    max_dispatches_per_second = 5
    max_concurrent_dispatches = 2
  }

  retry_config {
    max_attempts = 5
  }
}

resource "google_cloud_tasks_queue_iam_member" "enqueuer" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_tasks_queue.queue.name
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${var.runtime_service_account}"
}

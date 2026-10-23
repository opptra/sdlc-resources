resource "google_project_iam_member" "run_invoker" {
  count = length(var.schedules) > 0 ? 1 : 0

  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${var.runtime_service_account}"
}

resource "google_cloud_scheduler_job" "job" {
  for_each = var.schedules

  project   = var.project_id
  region    = var.region
  name      = replace(each.key, "_", "-")
  schedule  = each.value.cron
  time_zone = each.value.timezone

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${replace(each.value.job_name, "_", "-")}:run"

    oauth_token {
      service_account_email = var.runtime_service_account
    }
  }
}

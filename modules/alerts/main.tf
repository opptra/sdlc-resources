resource "google_monitoring_alert_policy" "error_logs" {
  project      = var.project_id
  display_name = "${var.name} unhandled error or failed job run"
  combiner     = "OR"

  conditions {
    display_name = "${var.name} severity >= ERROR"

    condition_matched_log {
      filter = "(resource.type=\"cloud_run_revision\" OR resource.type=\"cloud_run_job\") AND severity>=ERROR"
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "300s"
    }
  }
}

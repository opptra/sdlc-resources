output "alert_policy_id" {
  value = google_monitoring_alert_policy.error_logs.name
}

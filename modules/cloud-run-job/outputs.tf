output "name" {
  value = google_cloud_run_v2_job.app.name
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

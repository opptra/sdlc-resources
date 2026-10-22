output "name" {
  value = length(var.jobs) > 0 ? join(",", [for k, v in google_cloud_run_v2_job.app : v.name]) : google_cloud_run_v2_job.app[var.name].name
}

output "job_names" {
  value = { for k, v in google_cloud_run_v2_job.app : k => v.name }
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

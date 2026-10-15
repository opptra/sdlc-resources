output "uri" {
  description = "HTTPS URL of the Cloud Run service."
  value       = google_cloud_run_v2_service.app.uri
}

output "runtime_service_account" {
  description = "Email of the runtime service account."
  value       = google_service_account.runtime.email
}

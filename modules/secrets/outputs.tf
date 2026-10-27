output "secret_ids" {
  value = [for s in google_secret_manager_secret.secret : s.secret_id]
}

output "by_id" {
  description = "Secret id to that secret. Callers pass a value into a workload so the grant waits until the shell exists."
  value       = { for key, secret in google_secret_manager_secret.secret : key => secret.secret_id }
}

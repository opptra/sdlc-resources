output "connection_name" {
  description = "Cloud SQL connection name for the Cloud Run volume."
  value       = google_sql_database_instance.app.connection_name
}

output "secret_id" {
  description = "Secret Manager secret id that holds the database password."
  value       = google_secret_manager_secret.db.secret_id
}

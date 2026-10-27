# Grants access to the project's (default) database. The shared deploy creates
# that database when it is missing. This module does not, so two apps cannot
# both own it in Terraform state. The free quota applies to this one database.
resource "google_project_iam_member" "firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${var.runtime_service_account}"
}

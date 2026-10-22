# Uses the existing (default) Firestore database in the project so free tier applies.
resource "google_project_iam_member" "firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${var.runtime_service_account}"
}

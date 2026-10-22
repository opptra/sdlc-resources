# Secret Manager shells only. Values are never stored in Terraform state or Git.
resource "google_secret_manager_secret" "secret" {
  for_each = toset(var.secret_ids)

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each = toset(var.secret_ids)

  project   = var.project_id
  secret_id = google_secret_manager_secret.secret[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.runtime_service_account}"
}

# Grants the workload's runtime service account permission to run BigQuery
# jobs in the project and read/write any declared datasets.
resource "google_project_iam_member" "bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.runtime_service_account}"
}

resource "google_bigquery_dataset_iam_member" "dataset_editor" {
  for_each = toset(var.datasets)

  project    = var.project_id
  dataset_id = each.value
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.runtime_service_account}"
}

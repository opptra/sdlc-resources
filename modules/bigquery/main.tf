# Grants the workload's runtime service account permission to run BigQuery
# jobs in the runtime project and read/write any declared pre-existing datasets
# (supports both "<dataset_id>" in dataset_project/project_id and "<project_id>.<dataset_id>").
resource "google_project_iam_member" "bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.runtime_service_account}"
}

resource "google_bigquery_dataset_iam_member" "dataset_editor" {
  for_each = toset(var.datasets)

  project = (
    length(split(".", replace(each.value, ":", "."))) > 1
    ? element(split(".", replace(each.value, ":", ".")), 0)
    : coalesce(var.dataset_project, var.project_id)
  )
  dataset_id = (
    length(split(".", replace(each.value, ":", "."))) > 1
    ? element(split(".", replace(each.value, ":", ".")), 1)
    : each.value
  )
  role   = "roles/bigquery.dataEditor"
  member = "serviceAccount:${var.runtime_service_account}"
}

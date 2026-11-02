variable "project_id" {
  type        = string
  description = "Runtime GCP project ID where BigQuery jobs are billed/executed."
}

variable "dataset_project" {
  type        = string
  default     = null
  description = "Optional default GCP project ID hosting pre-existing BigQuery datasets (defaults to project_id)."
}

variable "runtime_service_account" {
  type        = string
  description = "Runtime service account email from module.service."
}

variable "datasets" {
  type        = list(string)
  default     = []
  description = "Optional list of BigQuery dataset IDs (dataset or project.dataset) this workload accesses."
}

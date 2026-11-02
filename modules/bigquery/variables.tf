variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "runtime_service_account" {
  type        = string
  description = "Runtime service account email from module.service."
}

variable "datasets" {
  type        = list(string)
  default     = []
  description = "Optional list of BigQuery dataset IDs this workload accesses."
}

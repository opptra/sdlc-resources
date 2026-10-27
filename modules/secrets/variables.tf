variable "project_id" {
  type = string
}

variable "secret_ids" {
  type        = list(string)
  default     = []
  description = "Secret Manager ids, each <prefix>-<ENV_NAME>. The workload that mounts one grants its own runtime account."
}

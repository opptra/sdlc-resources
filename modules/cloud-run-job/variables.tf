variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name" {
  type = string
}

variable "environment" {
  type = string
}

variable "image" {
  type = string
}

variable "cloud_sql_instance" {
  type    = string
  default = null
}

variable "db_secret_id" {
  type    = string
  default = null
}

variable "mounted_secret_ids" {
  type        = list(string)
  default     = []
  description = "Secret Manager ids this job account may read. Pass module.secrets.by_id values so the grant waits for each shell."
}

variable "secret_prefix" {
  type        = string
  default     = ""
  description = "App prefix from service.yaml. A secret id is <prefix>-<ENV_NAME>. The job name is not included."
}

variable "gcs_bucket_name" {
  type        = string
  default     = null
  description = "Plain GCS_BUCKET_NAME. The bucket name is not a secret."
}

variable "plain_env" {
  type        = map(string)
  default     = {}
  description = "Non-secret settings such as domains, ports, and flags."
}

variable "jobs" {
  description = "Optional map of job definitions sharing the same image."
  type = map(object({
    command         = list(string)
    enabled         = optional(bool, true)
    timezone        = optional(string, "Asia/Kolkata")
    schedules       = optional(list(string), [])
    timeout_seconds = optional(number, 1800)
    memory          = optional(string, "1Gi")
    secrets         = optional(list(string), [])
  }))
  default = {}
}

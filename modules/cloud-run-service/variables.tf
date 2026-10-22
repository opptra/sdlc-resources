variable "project_id" {
  type        = string
  description = "GCP project this apply changes. Staging uses opptra-staging. Production uses service.yaml prod_project."
}

variable "region" {
  type        = string
  description = "Cloud Run region. New apps use asia-south1."
}

variable "name" {
  type        = string
  description = "Cloud Run service name."
}

variable "environment" {
  type        = string
  description = "staging or prod. Written to the APP_ENV environment variable."

  validation {
    condition     = contains(["staging", "prod"], var.environment)
    error_message = "environment must be staging or prod."
  }
}

variable "auth" {
  type        = string
  description = "app-login, iap, public, or shared-secret. Same value as service.yaml auth."

  validation {
    condition     = contains(["app-login", "iap", "public", "shared-secret"], var.auth)
    error_message = "auth must be app-login, iap, public, or shared-secret."
  }
}

variable "image" {
  type        = string
  description = "Image to run, tagged with the git commit SHA."
}

variable "cloud_sql_instance" {
  type        = string
  default     = null
  description = "Cloud SQL connection name. Null when this service has no database."
}

variable "db_secret_id" {
  type        = string
  default     = null
  description = "Secret Manager secret ID holding the database password."
}

variable "command" {
  type        = list(string)
  default     = []
  description = "Optional command override for the container."
}

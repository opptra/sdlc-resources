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

variable "jobs" {
  description = "Optional map of job definitions sharing the same image."
  type = map(object({
    command         = list(string)
    enabled         = optional(bool, true)
    timezone        = optional(string, "Asia/Kolkata")
    schedules       = optional(list(string), [])
    timeout_seconds = optional(number, 1800)
    memory          = optional(string, "1Gi")
  }))
  default = {}
}

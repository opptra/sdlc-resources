variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "runtime_service_account" {
  type = string
}

variable "schedules" {
  description = "Map of schedule_key => { job_name, cron, timezone } for enabled jobs only."
  type = map(object({
    job_name = string
    cron     = string
    timezone = string
  }))
  default = {}
}

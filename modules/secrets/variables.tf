variable "project_id" {
  type = string
}

variable "secret_ids" {
  type    = list(string)
  default = []
}

variable "runtime_service_account" {
  type = string
}

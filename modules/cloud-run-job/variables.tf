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

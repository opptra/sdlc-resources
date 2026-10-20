resource "random_password" "db" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "app" {
  project          = var.project_id
  name             = "${var.name}-db"
  region           = var.region
  database_version = "POSTGRES_16"

  deletion_protection = true

  settings {
    tier = "db-g1-small"

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled = true
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_database" "app" {
  project  = var.project_id
  name     = "app"
  instance = google_sql_database_instance.app.name
}

resource "google_sql_user" "app" {
  project  = var.project_id
  name     = var.name
  instance = google_sql_database_instance.app.name
  password = random_password.db.result
}

resource "google_secret_manager_secret" "db" {
  project   = var.project_id
  secret_id = "${var.name}-db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db" {
  secret      = google_secret_manager_secret.db.id
  secret_data = random_password.db.result
}

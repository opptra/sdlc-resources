# Secret Manager shells only. Values are never stored in Terraform state or Git.
# Each id is <prefix>-<ENV_NAME>, the same variable the process reads.
# Domains, ports, and flags are plain environment variables, not secrets.
#
# This module does not grant read access. The job or service that mounts a
# secret grants its own runtime account and waits for that grant. Cloud Run
# checks the mount while saving the revision, so a grant created here in
# parallel would still be refused.
resource "google_secret_manager_secret" "secret" {
  for_each = toset(var.secret_ids)

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }
}

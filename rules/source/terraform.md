GCP resources are declared in infra and the shared module. Do not apply Terraform against production from a laptop.

`make ci` runs `terraform validate` with `-backend=false` when Terraform is installed and the deploy workflows were generated. That check does not read state and does not apply. Read the plan comment on the pull request before you call the change done. A database, when one is added, uses lifecycle prevent_destroy.

GCP resources are declared in infra and the shared module. Do not apply Terraform against production from a laptop.

`make ci` runs `terraform validate` with `-backend=false` when Terraform is installed and the deploy workflows were generated. That check does not read state and does not apply. Review the plan linked from the pull request checks. App-owned promotion shows the plan in the Actions run summary. That comment lists each add, change, replace, and destroy, and a destroy or a replace is at the top. A database, when one is added, uses lifecycle prevent_destroy.


Keep the staging and production backend locations separate and preserve their keys during handoff. Adoption imports app-owned resources into the appropriate state and uses explicit references for shared resources. Confirm the live IDs and review the first production plan before replacing the old deployment path. In promotion, merging a reviewed PR from main into production triggers apply.
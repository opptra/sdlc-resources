---
title: Migrate
parent: Using it
nav_order: 7
---

# Migrate an existing repository

Start with `align-app` to inspect the repository and choose a path. For a repository that needs CI and agent rules while keeping its current deploy path, follow [Align an existing repository](align.md). To replace a manual production deployment with Terraform, use `adopt-terraform` and follow [Adopt a live production app](infra-handoff.md#adopt-a-live-production-app).

1. Compare live production, the legacy deploy scripts and their dependencies, and the proposed Terraform and workflow. Record coverage, owners, and intentional differences in `docs/terraform-adoption.json`.
2. Set `infra_management: adoption` and rehearse the complete release on `staging`. Keep production on its current deployment path during rehearsal.
3. Record the successful staging run and review evidence in the handoff PR. CI checks them before the switch to `app-owned`.
4. Review the production imports and references, switch to a single production writer, and verify the new release. Retire the old path after the first successful Terraform apply.

Keep the existing production project and preserve Terraform state keys and addresses where already managed. Treat a runtime move, such as moving a database off a VM, as a separate migration.

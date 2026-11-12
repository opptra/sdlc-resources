---
title: Infrastructure handoff and promotion
parent: Using it
nav_order: 4
---

# Infrastructure handoff and promotion

Use `sync-infra` to scaffold a new app. After the first local checks pass, set `infra_management: app-owned` in the root `service.yaml`. Commit it alongside the infrastructure. An omitted field means generator ownership. A legacy migration uses the [adoption flow below](#adopt-a-live-production-app). In `adoption` or `app-owned`, `odlc sync` refreshes managed agent rules and preserves the Product contract, Terraform, workflow callers, component manifests, deployment helpers, and local build files.

| Setting | Where to look after handoff |
|---|---|
| Cloud resources, schedules, IAM, runtime values, and secret references | The Terraform root at `infra/` or `<component>/infra/`, its modules, and its environment inputs |
| Deploy triggers, Docker paths, state bucket and prefix, and release hooks | `.github/workflows/promotion.yml` or the app's active caller |
| App metadata, rule selection, and pipeline values still read from a manifest | Root `service.yaml` and the component manifest named in the caller |
| Secret payloads | Secret Manager in the target environment. Keep examples as placeholders. |

Run `odlc status --json` to list ownership, Terraform roots, and the standard promotion caller. For a root-level Terraform stack, setup writes a `service.deploy.yaml` manifest for the workflow. Read the caller and its named manifests before editing or removing settings. `render_tfvars.py` still reads project, region, resource naming, archetype, and auth from the deployment manifest. The promotion workflow selects optional `staging.tfvars` or `prod.tfvars` from the Terraform root for runtime configuration. The workflow supplies the deployment variables after those files. Keep each value with its owner.

## Enable promotion

The reusable workflow supports Cloud Run services and jobs. VM workers use their existing deployment path. Config-only repos use CI without Terraform.

1. Get a published full commit SHA from `opptra/sdlc-resources` containing the reusable workflow. Set the ownership field. Add `workflow_call` under `on` in an older app's `.github/workflows/ci.yml` so the staging push can run the same checks.
2. Run `odlc setup-promotion service.yaml . --workflow-ref <published-sha>`. For a fresh scaffold, pass `--replace-bootstrap-workflows` to remove the unchanged generated plan and deploy callers. For an existing app with customized callers, record their actual state locations and release behavior, then retire the callers explicitly in the same PR. Keep only one deploy path per environment.
3. Check the generated `staging_bucket`, `staging_prefix`, `production_bucket`, and `production_prefix` against the actual backend. Defaults match the standard legacy naming. Copy existing values exactly for an already-managed stack, including custom projects or prefixes. Keep separate state for each component and environment. A release with an empty bucket or prefix for its target stops before cloud authentication. Run `terraform fmt -recursive` from the app root. Commit the Terraform provider lock files and the generated caller and helper scripts.
4. Provision separate state, databases, and immutable Docker registries for staging and production. The default registry name is `apps-release` in each environment's project. A source tree tag allows reuse within that environment. Terraform and migrations consume the resolved image digest.
5. Configure `WIF_PROVIDER` and `WIF_SERVICE_ACCOUNT` on the GitHub environments below. Scope impersonation to the repository, workflow, environment, and allowed refs. Require review and the production plan check on PRs from the same repository's `main` to `production`.

| GitHub environment | Access |
|---|---|
| `staging-build`, `production-build` | Build and publish candidate images in that environment's registry. Restrict production candidate builds to same-repository promotion PRs from `main`. |
| `staging-plan`, `production-plan` | Read that environment's state and resource metadata. Allow state-lock operations separately from writes to state. |
| `staging`, `production` | Apply Terraform and run migrations for that environment. Restrict to the corresponding branch. |
| `production-recovery` | Production apply and migration permissions. Restrict to the protected production branch and configure required reviewers. The workflow verifies the approval before proceeding. |

Seed required values in the target Secret Manager before deploying a workload that mounts them. If needed, provision secret containers in a prerequisite change. Keep sensitive plan data in the runner. The uploaded review record contains a fingerprint and the candidate image reference.

## Deploy

- **Integration.** PRs into `main` run app CI and Terraform formatting and validation with the backend disabled. Merges into `main` publish no images and deploy nothing.
- **Staging.** Push to `staging` to build a staging candidate. The caller's `staging_mode` defaults to `auto` for established apps and `reviewed` during adoption. In reviewed mode, inspect the plan and dispatch the workflow on `staging` with that run's ID in `reviewed_run`. The developer can approve their own staging apply. The dispatch checks the current commit, digest, and plan.
- **Production.** Open a PR from `main` to `production`. The workflow builds or resolves its own candidates, displays their digests and the production plan, and records the proposed source tree and plan fingerprint. Approve the PR after the selected plan run completes, then merge to release those exact digests. A new plan run requires a new approval. A fresh plan must match before migrations or Terraform apply. Routine production releases use only production inputs. Closed PRs leave their candidate images in the registry.
- **Production plan drift.** Dispatch the workflow on `production` with `reviewed_run` empty. It reuses the merged PR's candidate digest and shows a fresh plan. Review it, then dispatch with the recovery plan run ID. A reviewer approves the `production-recovery` environment and the workflow checks the plan again. If the source tree changed or the original receipt is unavailable, use a new production PR.

Set the optional `migrate` input to an app script that runs pending migrations with `RELEASE_IMAGE` against the current environment and waits for success. Use `pre_apply` for app-specific backup or maintenance steps before migration. A failure stops rollout. Test migration changes against disposable Postgres in the app's CI. In multi-component apps, use workflow job dependencies so Terraform applies for dependent schedules and services wait for the component that runs migrations. Verify candidate health before traffic shifts when the app uses a separate rollout.

## Adopt a live production app

1. Compare the union of the live production inventory, the legacy deploy entry points and their scripts, and the proposed Terraform and workflow. Verify live settings with read-only access. Record gaps as unverified until they are resolved. The reviewer checks completeness and approves intentional differences.
2. Generate initial files, set `infra_management: adoption`, then run `odlc setup-promotion service.yaml . --workflow-ref <published-sha>`. Run `odlc sync --upgrade` with the updated CLI to install the current agent rules. During adoption, sync preserves the edited Terraform and workflows while the replacement can deploy to staging. Its production jobs remain disabled. Keep the live production deploy path available during rehearsal. Retire old staging callers on the migration branch and prepare to disable the legacy production writer at cutover.
3. Land the caller on the default branch with the marker still in `adoption` so GitHub can accept a manual staging dispatch. Configure production-only import inputs before the rehearsal so they are included in the reviewed tree. Push the proposed release tree to `staging`. Review the plan and dispatch the staging apply. Run the full release and verify the items in the report. Where applicable, demonstrate backup before migration, migration before deployment, and candidate health before traffic switch. Test the failure paths that should stop the switch and link the evidence. A plan or a run holding the staging image fixed is insufficient.
4. Record the parity review and completed staging apply run in `docs/terraform-adoption.json`. Change the marker to `app-owned` in the handoff PR. Run `odlc adoption-check --repo <owner/repository>` with GitHub Actions read access. The generated caller checks this transition and checks the first production promotion. Require the caller's adoption check for the handoff PR. The checked tree can differ from the rehearsal only in the report and the ownership marker. Later releases use ordinary CI once the target branch is app-owned.

The report has a top-level `review` link, a `staging` object with integer `run_id` and full Git `commit`, and an `items` array. Cover `workloads`, `triggers`, `runtime`, `identity`, `secrets`, `data`, and `release`. Record one row per item. A category with verified absence can use `not-applicable` with evidence and a reason. Use `verified` or `intentional-difference` for covered items. Give differences and retirements a reason. Record secret references only.

```json
{
  "category": "triggers",
  "item": "Daily reconciliation",
  "live": "Cloud Scheduler reconciliation-daily at 03:00 UTC",
  "legacy": "scripts/deploy-scheduler.sh sets the target and invoker",
  "proposed": "infra/scheduler.tf defines the trigger and its identity",
  "status": "intentional-difference",
  "reason": "Staging targets the test reconciliation job",
  "disposition": "import",
  "owner": "Terraform scheduler module",
  "verification": "Staging run link and job invocation evidence"
}
```

Other dispositions are `create`, `reference`, `retain-external`, and `retire`. The automated check verifies report coverage fields, the staging run, and the rehearsed tree. The migration reviewer verifies the inventory and the evidence for behavior.

Inventory live resources and confirm each provider ID and Terraform address. Create what is missing in staging. Use environment-scoped import blocks for existing app-owned production resources. Reference shared databases, datasets, and secrets by ID. Preserve the existing staging state and addresses.

Configure Terraform to match the live production settings and set `adoption_image` to the exact live image reference for that component. The first production PR should show imports and no resource updates, creates, deletes, or replacements. The adoption run skips image build, the pre-apply hook, and migrations. Review the plan, suspend the legacy production writer for cutover, merge, and verify a clean follow-up plan and the live app. Remove the temporary adoption input in the first normal release. Roll out intentional infrastructure changes separately from the imports.

## Upgrade an older pipeline

Apps opt in through a PR. Their existing callers continue working until that app changes them.

1. Update the installed Opptra skills and CLI after the shared changes are released. Read the app's current caller, component paths, and state keys. In the app PR, add the ownership field **before** running `odlc sync --upgrade`. The upgraded CLI rejects a pre-handoff engine for an app-owned repo. Verify the rules-only diff.
2. For an app that already deploys through Terraform, prepare the new caller with the existing state locations. For the handoff-only plan, set `staging_adoption_image` and `adoption_image` to the respective live image references and verify a no-op plan. Remove those inputs before a normal rollout. Remove any other app workflow or Cloud Build trigger that can write to the same environment as part of cutover. A legacy hosted app follows the adoption procedure above.
3. To update a future workflow release, change the shared workflow SHA in the caller and review it in an app PR. Compare both environment plans, configure the environment identities, and update the caller with the dispatch input, `pull-requests: read` permission, and any versioned helper scripts. Let any in-flight production PRs finish on their pinned workflow before changing the pin. The ownership marker and the workflow SHA solve different problems. The marker protects app files from regeneration, while the SHA controls deployment behavior.

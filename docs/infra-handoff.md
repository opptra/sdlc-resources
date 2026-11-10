---
title: Infrastructure handoff and promotion
parent: Using it
nav_order: 4
---

# Infrastructure handoff and promotion

Use `sync-infra` to scaffold an app. After the first local checks pass, set `infra_management: app-owned` in the root `service.yaml`. Commit it alongside the infrastructure. An omitted field means generator ownership. On an app-owned repo, `odlc sync` refreshes managed agent rules and preserves the Product contract, Terraform, workflow callers, component manifests, deployment helpers, and local build files.

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
3. Check the generated `staging_bucket`, `staging_prefix`, `production_bucket`, and `production_prefix` against the actual backend. Defaults match the standard legacy naming. Copy existing values exactly for an already-managed stack, including custom projects or prefixes. Keep separate state for each component and environment. Run `terraform fmt -recursive` from the app root. Commit the Terraform provider lock files and the generated caller and helper scripts.
4. Ask the platform administrator to provision the state buckets and an immutable Docker registry in each component's region and deployment project. The workflow defaults to `apps-release`. Set `artifact_repo` in the caller to use another immutable registry. Keep its write access with the trusted release identity. The workflow uses the source tree as its immutable image tag so the PR plan and merged release agree. See [Artifact Registry image tags](https://docs.cloud.google.com/artifact-registry/docs/docker/names).
5. Configure `WIF_PROVIDER` and `WIF_SERVICE_ACCOUNT` as **environment variables in GitHub Actions** for the four GitHub environments below. Use distinct identities for preview and apply. Scope Google Cloud impersonation to the repository and environment, and restrict the write environments to their deployment refs. Keep state access scoped to the app's prefixes where possible. For production, require the plan and PR review through branch protection. A separate environment reviewer gate would add a second approval after merge. See [GitHub OIDC claims](https://docs.github.com/en/actions/reference/security/oidc).

| GitHub environment | Access |
|---|---|
| `staging-plan` | Read staging state and the metadata required for a plan. |
| `production-plan` | Read production state and the metadata required for a plan. |
| `staging` | Write staging state, manage app-owned staging resources, and publish staging images. Limit to the staging branch. |
| `production` | Write production state, manage app-owned production resources, and publish production images. Limit to the protected production branch. |

Plan jobs use same-repository PRs, a read-only cloud identity, and no state lock. State itself can contain sensitive information. Grant plan access only for trusted repository contributors and avoid reading secret payloads in Terraform. Seed required secret versions in Secret Manager as part of environment setup, before rolling out a workload that mounts them. When the app must first provision secret containers, land that Terraform in a prerequisite change and seed the values before mounting them.

## Deploy

1. Push the feature or fix branch to `staging`. GitHub runs app CI, Terraform formatting and validation, then plans and applies to staging.
2. Open the PR from the same branch into `main`. Review CI and the staging plan. Keep product code and its Terraform together when they ship together.
3. Open a PR from `main` to `production`. Review the production plan in the Terraform check's Actions summary. Merge the PR to deploy. The workflow plans again using the merged tree and current production state, compares the result with the successful PR plan, and applies the saved final plan. An absent or different review receipt stops the apply. If the state or merge tree changed, review a fresh promotion before retrying.

Production blocks deletes and replacements. Staging allows switching between feature branches while protecting persistent GCP resources such as databases and buckets. For public and app-login services with a Terraform `uri` output, the default smoke test requests `/api/health`. Use `pre_apply` and `post_apply` inputs for custom release checks or an app-owned migration script. The pre-apply hook runs after image build and before applying the saved plan. A job needed by the hook must already be available. Verify any candidate traffic shift or multi-step rollout with the app's own rollout configuration before switching the legacy writer off.

## Adopt a live production app

Inventory live resources and confirm each provider ID and Terraform address. Create what is missing in staging. Use environment-scoped import blocks for existing app-owned production resources. Reference shared databases, datasets, and secrets by ID. Preserve the existing staging state and addresses.

Configure Terraform to match the live production settings and set `adoption_image` to the exact live image reference for that component. The first production PR should show imports and no resource updates, creates, deletes, or replacements. The adoption run skips the image build and pre-apply hook. Review the plan, suspend the legacy production writer for cutover, merge, and verify a clean follow-up plan and the live app. Remove the temporary adoption input in the first normal release. Roll out intentional infrastructure changes separately from the imports.

## Upgrade an older pipeline

Apps opt in through a PR. Their existing callers continue working until that app changes them.

1. Update the installed Opptra skills and CLI after the shared changes are released. Read the app's current caller, component paths, and state keys. In the app PR, add the ownership field **before** running `odlc sync --upgrade`. The upgraded CLI rejects a pre-handoff engine for an app-owned repo. Verify the rules-only diff.
2. For an app that already deploys through Terraform, prepare the new caller with the existing state locations. For the handoff-only plan, set `staging_adoption_image` and `adoption_image` to the respective live image references and verify a no-op plan. Remove those inputs before a normal rollout. Remove any other app workflow or Cloud Build trigger that can write to the same environment as part of cutover. A legacy hosted app follows the adoption procedure above.
3. To update a future workflow release, change the shared workflow SHA in the caller and review it in an app PR. Compare both environment plans and update any versioned helper scripts called by the new workflow. The ownership marker and the workflow SHA solve different problems. The marker protects app files from regeneration, while the SHA controls deployment behavior.

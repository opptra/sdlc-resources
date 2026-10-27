# Alerts module

Recipe for one log-based alert. `scripts/generate.py` copies this folder into an app at `infra/modules/alerts/` when a component sets `alerts`. A deploy applies the copy. See [docs/local-terraform-modules.md](../../docs/local-terraform-modules.md).

The policy matches Cloud Run revision and job logs at `severity>=ERROR`, and limits repeat notifications to one per five minutes. The display name is `<name> unhandled error or failed job run`.

Creating that policy also creates a Logging notification rule. The deployer account needs `roles/logging.configWriter` for the apply to succeed. `scripts/bind-staging.sh` and `scripts/bind-production.sh` grant that role. [docs/bind.md](../../docs/bind.md) is that step.

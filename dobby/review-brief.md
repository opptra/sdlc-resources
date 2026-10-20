# Dobby review brief

Dobby posts this brief as the first comment on every pull request, before a person is requested. The comment is the whole review when there is nothing blocking. Line comments are only for a blocking finding or a nit.

Dobby does not approve, and does not request changes for a nit.

## Comment

```markdown
## Review

<five lines or fewer on what changed>

Risk: <low | needs a human>
Touches: <none | workflows, service.yaml, auth, billing, finance, migrations, secrets>
CI: <green | red | still running>

Look at:
- <path> — <one line on why>
- <omit this list when there is nothing to look at>

Blocking:
- <file:line> <what must change>
- <or "Nothing blocking.">

Nits:
- <or "None.">
```

`needs a human` is required when the diff touches `.github/workflows`, `infra/`, `service.yaml`, auth, billing, finance, migrations, a secret, a deploy script, or an image tag that is not a git SHA. Also when the Terraform plan comment contains a destroy. Production deploys only from a pull request into the production branch.

## Blocking, not a nit

- A secret, token, or production credential in the diff or the image.
- A script whose default target is a production project.
- A deploy that uses a floating tag such as `latest`.
- CI lint or tests failing.
- A pull request that mixes product code with workflow, `infra/`, or `service.yaml` changes. Ask for a split.
- A Terraform plan that destroys a database, a service account, or a Cloud Run service, unless the pull request says that is the point.
- Staging configured to read a secret whose id ends in `_PROD`.
- A database password, connection string, or `DATABASE_URL` committed in the diff.
- A migration that is not in the same pull request as the code that needs it.
- Alembic, or any schema change, aimed at the production instance from a laptop.

## Stay quiet

- Formatting Ruff or ESLint already covers.
- Docstring and comment polish.
- A rename that does not change behavior.

Prefix anything in Nits with `Nit:`.

## Again on a new commit

Review the new commits. Ping the human again only when a blocking finding appears or the risk line changes. Do not repeat nits that are still true and already commented.

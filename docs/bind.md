---
title: Bind a repository
parent: Platform
nav_order: 3
---

# Bind a repository

Do this once for each app, after the generator has written the repository and the developer has pushed `main`, `staging`, and `production`. It lets GitHub Actions impersonate a deployer in GCP. It does not deploy the app, and it does not protect branches.

A push to `staging` deploys staging. A merge into `production` deploys production. `main` does not deploy.

Staging and production are two scripts because the person who can change `opptra-staging` often cannot change the production project. Each script touches one project.

The company already has one Workload Identity pool, `opptra-github`, in the identity project `opptra-sdlc-ci`. Do not create a second pool. Both scripts use that pool. A staging token can impersonate only the staging deployer. A production token can impersonate only the production deployer.

## What a repository admin adds on GitHub

This needs the repository Admin role. Maintain and Write cannot open environment protection rules. On a private repository, required reviewers exist on GitHub Enterprise. The reviewer needs Read on the repository.

1. Open the app repository on GitHub. Go to **Settings → Environments**.
2. Create an environment named `staging`.
3. Create an environment named `production`. When the plan allows it, add a required reviewer on `production`. A production plan or deploy then waits for that person.
4. After the scripts below have been run, set the four Actions variables they print. A repository admin can set them. The person who ran a script can set that script's two variables when they have permission to change Actions variables on the repository.

| Variable | Set by | Value |
|---|---|---|
| `WIF_PROVIDER_STAGING` | `scripts/bind-staging.sh` | The provider in `opptra-sdlc-ci` |
| `WIF_SERVICE_ACCOUNT_STAGING` | `scripts/bind-staging.sh` | `<repo-name>-deployer@opptra-staging.iam.gserviceaccount.com` |
| `WIF_PROVIDER_PROD` | `scripts/bind-production.sh` | The same provider in `opptra-sdlc-ci` |
| `WIF_SERVICE_ACCOUNT_PROD` | `scripts/bind-production.sh` | `<repo-name>-deployer@<prod_project>.iam.gserviceaccount.com` |

Create both environments before the first pull request. A pull request into `production` plans as the `production` environment. Any other pull request plans as `staging`.

## What you run

Run this if you can change IAM in `opptra-staging` and you can read the pool in `opptra-sdlc-ci`. You do not need access to the production project.

The generator fills in the repository name. From the app repository:

```bash
gcloud auth login
gh auth login
scripts/bind-staging.sh
```

Then run the two `gh variable set` commands the script prints.

A checkout of `opptra/sdlc-resources` that was not filled in by the generator takes the repository explicitly:

```bash
scripts/bind-staging.sh opptra/<repo>
```

The script creates `<repo-name>-deployer` in `opptra-staging`, grants it permission to push images and apply Terraform, and lets only the GitHub environment `staging` impersonate it. The apply permission includes Logging Configuration Writer, because a log-based error alert also creates a Logging notification rule. The service-account id must be 6 to 30 characters. A longer repository name fails here.

Both bind scripts require `gh`. Each reads the repository's token name from GitHub and trusts that name. A login that cannot read the repository stops here. When that name differs from the older `repo:<org/repo>:environment:<environment>` form, the script removes the old binding.

Staging can deploy after this step and the two staging variables are set. Production cannot deploy yet.

## What you send to someone with production access

Send them the file `scripts/bind-production.sh` from the app repository. It is already filled in with the repository and with `prod_project` from `service.yaml`.

They need permission to change IAM in that production project, and permission to read the pool in `opptra-sdlc-ci`. They do not need access to `opptra-staging`.

They run:

```bash
gcloud auth login
gh auth login
scripts/bind-production.sh
```

Then they run the two `gh variable set` commands the script prints. If they cannot set Actions variables, they send those two commands back to a repository admin.

A template checkout that was not filled in takes both arguments:

```bash
scripts/bind-production.sh opptra/<repo> <prod-project-id>
```

If that production project has no Terraform state bucket yet, they create `gs://<prod-project-id>-tfstate` first. The commands are in [gcp-bootstrap.md](gcp-bootstrap.md). The script checks for the bucket and exits if it is missing. `opptra-staging` and `opptra-applications` already have buckets.

The script creates the deployer in the production project only, and lets only the GitHub environment `production` impersonate it.

## Order

1. Repository admin creates the GitHub environments `staging` and `production`.
2. You run `scripts/bind-staging.sh` and set `WIF_PROVIDER_STAGING` and `WIF_SERVICE_ACCOUNT_STAGING`.
3. You send `scripts/bind-production.sh` to someone who can change IAM in `prod_project`.
4. That person runs it and sets `WIF_PROVIDER_PROD` and `WIF_SERVICE_ACCOUNT_PROD`, or sends those two commands to a repository admin.

After step 2, a push to `staging` can deploy. After step 4, a merge into `production` can deploy.

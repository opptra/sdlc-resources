# New app

The developer creates the GitHub repository. The agent fills it.

1. A person opens a Linear issue with the users, the outcome, the production GCP project, and who can sign in.
2. The developer decides this is a new repo.
3. The developer creates an empty `opptra/<name>` repository.
4. The developer runs the create-app skill in a checkout of `opptra/sdlc`. The skill recommends the components and the auth. If nothing fits, it stops. Apps Script stops.
5. After the developer agrees, the skill writes `service.yaml` and runs `scripts/generate.py` into an empty directory.
6. The developer copies that directory into the new repo, pushes `main`, and creates `staging` and `production` from `main`.
7. A platform owner runs `scripts/protect-branches.sh` and `scripts/bind-repo.sh`. Protection covers `main` and `production` only. For an app with Terraform, set `PLAN_CHECK=plan`.

The generated tests pass. `/api/health` is the passing test for an API. A job and a worker each have a passing entrypoint test. The first failing test for a feature waits for a feature branch.

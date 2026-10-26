# Opptra SDLC

This is the guide for how an Opptra app is set up, aligned, changed, reviewed, and deployed. The pages here are the same files as `docs/` in [opptra/sdlc-resources](https://github.com/opptra/sdlc-resources). A checkout still opens those files directly. This site is the copy that does not require one.

Start with [which skill to use](workflows.md).

The agent skills live in [opptra/agent-skills](https://github.com/opptra/agent-skills). `service.yaml` in an app is the only decision that app records. [mapping.yaml](https://github.com/opptra/sdlc-resources/blob/main/mapping.yaml) and [scripts/sdlc.py](https://github.com/opptra/sdlc-resources/blob/main/scripts/sdlc.py) turn those facts into the repository.

`main` does not deploy. A push to `staging` deploys staging. A pull request from `main` into `production` deploys production.

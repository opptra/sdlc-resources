---
name: create-app
description: Interview for a new Opptra app, recommend an archetype and auth, write service.yaml, and run the generator. Use when a developer asks to scaffold, create, or set up a new app or repo.
disable-model-invocation: true
---

# Create an app

You fill in facts. scripts/generate.py decides the files, CI, deploy, and rules. Do not invent a pipeline. Do not create the GitHub repository. Do not run bind-repo.sh or protect-branches.sh.

Apps Script is not a choice. If the description only fits Apps Script, say so and stop.

## Questions

Ask what the app is for. Then ask, in order, and stop at the first match for each runnable part:

1. Config, prompts, or skills only, with no running service? Part `config`, archetype `config-only`, auth `none`.
2. Work on a schedule or a queue, with no page a person waits on? Part `job`, archetype `cloud-run-job`, auth `none`.
3. A real browser, a long-lived process, or a disk Cloud Run will not keep? Part `worker`, archetype `vm-worker`, auth `none`.
4. A page or an API a person or another service calls? Parts `api` and, if there is a page, `ui`. Archetype `cloud-run-service`.

A console plus a scraper is two components in one service.yaml.

Auth, only for a Cloud Run service:

- Opptra staff, Google account, no separate password: `iap`
- The app signs users in itself: `app-login`
- Anyone on the internet, no account: `public`

Also ask for the app name, the production GCP project, and the region. The region default is `asia-south1`.

## Recommendation

Say one sentence that names the components, the archetype, and the auth, and why. If no archetype fits, name the closest one and stop. Do not write files until the developer agrees.

## Write

Write service.yaml with name, prod_project, region, and components. Run:

```bash
python3 scripts/check_manifest.py service.yaml
python3 scripts/generate.py service.yaml <empty-directory>
```

Tell the developer to create the GitHub repo, copy the directory in, push main, create staging and production from main, then ask a platform owner to run protect-branches.sh and bind-repo.sh.

The generated tests pass. A failing test for a Linear issue belongs on a feature branch, not in this scaffold.

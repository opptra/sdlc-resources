---
title: Bug
parent: Using it
nav_order: 5
---

# Bug

1. A person opens a Linear issue with the steps, the expected result, the actual result, and whether it was staging or production.
2. If the fix needs a product or design choice, follow [feature.md](feature.md).
3. Otherwise the agent prints the route banner, waits for a yes, branches from `main` as `fix/<ticket>-<short-slug>`, writes `.sdlc/intent.yaml`, writes a failing test, then the fix. A new chat reads that file and continues.
4. The pull request into `main` has the Linear link, the reproduction, and the test name.
5. The agent prints the ship card for the active caller. Apps with deployment IAM use a reviewed PR into `staging`. Legacy callers deploy staging on push. Production uses a PR from `main` into `production`.
6. The developer squash-merges the integration PR as `fix: <ticket> <short summary>` and follows the ship card to verify staging and promote the fix.
7. The issue is Done when production has applied.

A production bug uses this path. If the fix needs a cloud resource, the agent opens the infra pull request in the same chat and writes the test only after the developer says that pull request has merged. A rollback is a revert merged to `main`, then a pull request from `main` into `production`. Use the active staging path to test the revert.

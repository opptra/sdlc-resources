# Bug

1. A person opens a Linear issue with the steps, the expected result, the actual result, and whether it was staging or production.
2. If the fix needs a product or design choice, follow [feature.md](feature.md).
3. Otherwise the agent prints the route banner, waits for a yes, branches from `main` as `fix/<ticket>-<short-slug>`, writes `.sdlc/intent.yaml`, writes a failing test, then the fix. A new chat reads that file and continues.
4. The pull request into `main` has the Linear link, the reproduction, and the test name.
5. The developer squash-merges as `fix: <ticket> <short summary>`. To check staging they push the fix branch directly to `staging`. They do not merge `main` into `staging`. Production is a pull request from `main` into `production`.
6. The issue is Done when production has applied.

A production bug uses this path. A rollback is a revert merged to `main`, then a pull request from `main` into `production`. Staging is updated by pushing the revert branch directly to `staging`.

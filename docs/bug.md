# Bug

1. A person opens a Linear issue with the steps, the expected result, the actual result, and whether it was staging or production.
2. If the fix needs a product or design choice, follow [feature.md](feature.md).
3. Otherwise the agent branches from `main` as `fix/<ticket>-<short-slug>`, writes a failing test, then the fix.
4. The pull request into `main` has the Linear link, the reproduction, and the test name.
5. The developer squash-merges as `fix: <ticket> <short summary>`, pushes `main` onto `staging`, checks the URL, then merges `main` into `production`.
6. The issue is Done when production has applied.

A production bug uses this path. A rollback is a revert through `main`, then `staging`, then `production`.

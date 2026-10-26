---
title: Review
parent: Platform
nav_order: 4
---

# Review

Dobby reviews every pull request. One human approval is what merges it to `staging` or to `main`. Dobby does not count as that approval.

## What Dobby posts

The brief is specified in [dobby/review-brief.md](../dobby/review-brief.md). It is posted before a person is pinged, and only after it can say whether CI is green.

A blocking finding requests changes. A nit stays a comment and does not request changes. The human is pinged again only when a new commit adds a blocking finding or changes the risk label.

Comments that people always dismiss get removed from Dobby's rules. Those rules should match [rules/](../rules/) in this repository, so Dobby flags a laptop deploy, a committed secret, and a floating image tag.

Changing Dobby to post this brief is work in the Dobby repository. This repository holds the spec so reviewers can agree on the text first.

A Dobby finding becomes a required status check only after the team trusts that class of comment. Until then it is a comment.

## Human approval

Branch protection requires one approving review. Admins are included. Stale reviews are dismissed on a new push.

The reviewer looks at whether this is the right change and what it can break. Style, formatting, and the lint rules are CI's job. Approve when the change improves the codebase. Mark polish with the prefix `Nit:`.

## CODEOWNERS

The template `CODEOWNERS` requests `@opptra/platform` for:

- `.github/workflows/`
- `service.yaml`

Extend that file in the app for auth, billing, finance, and migration paths. Replace `@opptra/platform` with a real team or with GitHub usernames before you enable "require review from code owners". A missing team will block every merge.

Code owner review is in addition to the one human approval when those paths change. A pull request that does not touch them still needs one human approval and a green CI check.

## Release notes

Not in v1. A later Dobby job can draft notes on the `staging` to `main` pull request from the commit titles.

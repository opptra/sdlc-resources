Read the root service.yaml before you change infra, workflows, or deploy settings. Archetype, auth, and parts come from that file.

main is the default branch. Cut feature branches from main. Open the pull request into main. Merging to main does not deploy.

A push of main onto staging deploys the staging project. A pull request from main into production deploys prod_project when it merges.

Do not add deploy.sh. Do not run gcloud run deploy. Do not commit a .env or a credential. Do not tag an image latest.

Product code and changes to infra, .github/workflows, or service.yaml go in separate pull requests.

Branch names are feat/<ticket-id>-<short-slug> for a feature and fix/<ticket-id>-<short-slug> for a bug.

Commit messages are feat: <ticket-id> <short summary> or fix: <ticket-id> <short summary>.

Every pull request links the Linear issue.

Done means the test command for each part you touched has been run.

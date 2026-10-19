Read the root service.yaml before you change infra, workflows, or deploy settings. Archetype, auth, and parts come from that file.

main is the default branch. Cut feature branches from main. Open the pull request into main. Merging to main does not deploy.

A push of main onto staging deploys the staging project. A pull request from main into production deploys prod_project when it merges.

Do not add deploy.sh. Do not run gcloud run deploy. Do not commit a .env or a credential. Do not tag an image latest.

Product code and changes to infra, .github/workflows, or service.yaml go in separate pull requests.

When the user asks for a change and does not name a skill, decide and follow one. A broken or incorrect behavior follows the bug skill. New behavior follows the feature skill. Do not wait for /feature or /bug.

At the start of a feature or a bug, read the Linear issue. If Linear is not connected, stop. Tell the developer to connect Linear in Cursor or Claude. The ticket id is required for the branch name, the commit message, and the pull request. Do not invent a ticket id.

Branch names are feat/<ticket-id>-<short-slug> for a feature and fix/<ticket-id>-<short-slug> for a bug.

Commit messages are feat: <ticket-id> <short summary> or fix: <ticket-id> <short summary>.

Every pull request links the Linear issue.

A feature writes an OpenSpec under openspec/ before any product code. The pull request includes that path. A bug writes an OpenSpec only when the fix needs a product or design choice.

Before you edit files, tell the developer what you will change and wait for a yes. Before a commit, show the message and the file list and wait. Before a push or a pull request, show the branch, title, and body and wait. Do not commit or push in the same turn as the code unless they already agreed.

Done means the test command for each part you touched has been run.

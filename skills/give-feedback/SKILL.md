---
name: give-feedback
description: Files a GitHub issue in opptra/sdlc-resources with a developer's feedback on the Opptra SDLC, its skills, generator, workflows, or docs. Use when a developer says give feedback, report a problem with the SDLC, suggest an improvement to a skill, or asks to file an issue against sdlc-resources.
---

# Give feedback

Turns feedback about the Opptra SDLC into one GitHub issue in `opptra/sdlc-resources`. It does not change any code, skill, or the current repository.

```text
Route: give-feedback | Target: opptra/sdlc-resources (issue only)
Human Gates: one yes on the issue title and body before it is created
```

## Steps

1. **Collect.** Use what the developer already said. Ask once, in one message, only for what is missing:
   - Kind: `bug` (something is broken or wrong), `improvement` (something works but could be better), or `question`.
   - Area: a skill (`create-app`, `change-app`, `feature`, ...), the generator (`odlc`, `scripts/`), `modules/`, workflows, rules, or docs.
   - What happened or what is wanted, and the expected result.
   - For a bug: the command or prompt, and the error text.
2. **Add context from the session.** Include the skills commit (`git -C <agent-skills checkout> rev-parse --short HEAD`) and the `generator_sha` from `.sdlc/state.yaml` when those exist. Include the current repo name when it helps. Leave out anything you cannot read.
3. **Remove secrets.** Replace tokens, secret values, keys, passwords, and customer data with `<redacted>`. The issue is visible to the whole organization.
4. **Check for a duplicate.** Run `gh issue list -R opptra/sdlc-resources --state open --search "<keywords>" --limit 5`. If one matches, show it and ask whether to comment on it (`gh issue comment <n> -R opptra/sdlc-resources --body-file <file>`) instead of opening a new one.
5. **Draft and confirm.** Show the title (under 80 characters, starts with the area, for example `feature skill: ...`) and the body below. Wait for a yes.

   ```markdown
   ## Kind
   bug | improvement | question

   ## Area
   <skill, script, module, workflow, or doc page>

   ## What happened / what I want
   <text>

   ## Expected
   <text>

   ## Context
   - Skills commit: <sha or unknown>
   - generator_sha: <sha or unknown>
   - Repo: <opptra/name or unknown>
   - Linear: <ticket id, if any>

   Filed by the `give-feedback` skill.
   ```

6. **Create.** Write the body to a temporary file so quoting cannot change it, then run:

   ```bash
   gh issue create -R opptra/sdlc-resources --title "<title>" --body-file "$BODY" --label feedback
   ```

   If the label does not exist, run the same command without `--label`. If `gh auth status` fails, print the title and body and tell the developer to run `gh auth login` or paste them at https://github.com/opptra/sdlc-resources/issues/new/choose. Do not retry in a loop.
7. **Finish.** Print the issue URL and stop. Do not start a fix, branch, or pull request.

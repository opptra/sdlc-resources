Use Vite, React, and TypeScript. Call the API with relative /api paths.

Product analytics goes through src/analytics.ts. That function stays empty until a tool is chosen.

Do not add Next.js or a second Node server. From the frontend directory, run npm run lint and npm run typecheck before you stop.

Before any visible UI change, load Opptra design system 0.1.0 from https://opptra.github.io/opptra-design-system/. Fetch `manifest.json`, `SKILL.md`, the component families you will use in `guidelines.md`, `tokens.json`, and `tokens.css`. If the `opptra-design-system` skill is installed, read that `SKILL.md` first. For presentations, documents, emails, and charts, use `opptra-branding` instead.

Build with semantic tokens (`var(--color-action-primary)` and the rest). Spectral for headings, Raleway for UI text. Navy labels on orange actions. Small accent links use `#B53F00`.

Reuse a component family (C01–C27) before adding a pattern. Cover empty, error, loading, permission, and success when the screen has them. Keep zero, missing, stale, and restricted data distinct.

If the app has no `tokens.css`, add the published file. Leave the gallery's synthetic demo content out of the product. Record the manifest version and any extension in the plan or OpenSpec.

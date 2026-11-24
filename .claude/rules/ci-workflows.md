---
paths:
  - ".github/**"
---
# GitHub Actions workflows

- Least privilege: top-level `permissions: {}` or `contents: read`; grant per job only what it needs
  (`pages: write`, `id-token: write`, `issues: write`, `actions: write` for the monthly cron re-enable).
- Pin third-party actions by full commit SHA with a `# vX.Y.Z` comment; Dependabot keeps them current.
- `concurrency:` per workflow so two data updates never race; `timeout-minutes` on every job.
- Secrets only via `${{ secrets.X }}` into env of the step that needs them; never echo them; logs redacted.
  `DATA_REPO_TOKEN` is a fine-grained PAT limited to contents:write on econ-data.
- Cron uses odd minutes (`17 23 * * *`) - top-of-hour runs are delayed. Keep `workflow_dispatch`.
- Pushes with GITHUB_TOKEN do not trigger other workflows - no `[skip ci]` needed.
- Pages artifacts drop dotfiles and symlinks; data files are content-hashed + manifest served no-store.
- Changing a workflow is an outward-facing change: the main thread confirms with the Owner before pushing.

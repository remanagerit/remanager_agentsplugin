# Dependency notes

Release verification is fail-closed while a documented upstream P2 exists. `REMAN_SOURCE_CI_ALLOW_DOCUMENTED_OPENCLAW_P2=1` is accepted only by protected source CI on `main`; it must never be set by a tag, package or release workflow.

## OpenClaw 2026.6.11

The connector has one runtime dependency, `typebox@1.1.39`, and a peer dependency on OpenClaw. Development verification installs `openclaw@2026.6.11` to compile and inspect the native plugin contract.

`npm audit` and `npm audit --omit=dev` report zero vulnerabilities for the connector checkout. `npm ls --all` currently reports invalid transitive relationships inside the published `openclaw@2026.6.11` development dependency involving `tar` and `@types/retry`. These packages are not declared by the REmanager connector and are not included as connector-owned code in `npm pack`, but the non-clean peer development tree is a reproducibility risk.

Before public release, Deploy must rerun `npm ls --all` on the supported Node LTS runtime, record the exact output, and either:

1. upgrade the minimum tested OpenClaw version to an upstream release with a clean tree; or
2. obtain and document an upstream resolution explaining the published dependency metadata.

Do not suppress or silently ignore the `npm ls` failure in release CI.

### Deploy verification 2026-07-11

Deploy repeated a clean install and `npm ls --all` in the official
`node:22-alpine` image (`Node v22.23.1`, npm `10.9.8`). The command still exits
with `ELSPROBLEMS` for exactly:

- `tar@7.5.16`, while `@openclaw/fs-safe` declares `7.5.13`;
- `@types/retry@0.12.5`, while OpenClaw's nested `p-retry` declares `0.12.0`.

The npm registry still identifies `2026.6.11` as the latest stable OpenClaw
release and declares Node `>=22.19.0`; the available newer line is beta. The
connector therefore keeps Node `>=22.19` but remains blocked from public
release pending either a clean stable upstream version or a documented
upstream resolution. The release workflow reports this known P2 and fails
before producing release artifacts while it remains unresolved.

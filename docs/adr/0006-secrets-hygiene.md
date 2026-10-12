# ADR 0006: Secrets hygiene — `.env` only, nothing else committed

## Context

The reference repo this project's conventions were deliberately modeled on
(`applications.ai.agenticbot.backend`) has `secrets.env`, `secrets 1.env`,
`secrets_old.env`, `secrets_old1.env`, `secrets_old2.env`, and two `.pfx`
certificate files committed at its repository root.

## Decision

This project never commits a real secret, under any filename. Only
`.env.example` (every variable name, no real values) is committed; `.env`
itself is gitignored. The dev-default JWT secret
(`dev-only-change-me-replace-with-32-bytes-random-value`) is long enough to
satisfy HS256's minimum recommended key length (PyJWT warns below 32 bytes —
see Lesson 43) specifically so it never looks "real" or gets mistaken for a
production value, while still letting tests run without configuration.

## Consequences

- A fresh clone can never accidentally leak a credential through git
  history — there is no history to leak, because the pattern was never
  committed in the first place.
- The Microsoft Entra ID device-code flow (see `scripts/setup_entra.sh`) was
  deliberately chosen as a **public client** specifically so no client
  secret is ever generated or stored anywhere in this project, sidestepping
  the entire problem for that integration.
- Docker images (`Dockerfile`, `Dockerfile.ui`) never `COPY .env` — secrets
  are injected at `docker run`/`docker compose` time via environment
  variables only; `.dockerignore` excludes `.env*` defensively even though
  the Dockerfiles don't reference it.

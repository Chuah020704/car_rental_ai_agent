# ADR 0004: Two-tier configuration (`config.yaml` + `.env`)

## Context

The project has two different kinds of configuration with different
lifecycles: secrets/per-environment values (API keys, JWT signing key) that
must never be committed, and tunables (model names, temperatures, retrieval
thresholds, rate limits) that are product decisions worth reviewing in a PR
diff like any other code change.

## Decision

Mirror the pattern found in `applications.ai.agenticbot.backend`: a committed
`app/core/config/config.yaml` for tunables, loaded with `yaml.safe_load`, and
grouped `pydantic-settings` `BaseSettings` subclasses reading `.env` for
secrets — composed into one `Settings` object, both cached via `lru_cache`.

## Consequences

- A missing required secret fails fast at first access, with a clear
  `ConfigurationException`, rather than surfacing as a confusing error deep
  in an LLM call.
- `.env.example` documents every variable name with no real values — the
  reference repo's own worst practice (committing `secrets.env`,
  `secrets_old.env`, and `.pfx` certificate files directly) is the anti-
  pattern this ADR exists to avoid; see ADR 0006.
- Model-name/threshold changes (e.g. the RAG distance-threshold recalibration
  in Lesson 21) are reviewable in git history, not buried in an
  environment variable someone has to go find.

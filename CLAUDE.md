# CLAUDE.md

Shared contracts of the integration platform: the event envelope, its Python
library, the AsyncAPI landscape, contract templates and the lint rules. Ground
rules and decisions live in the
[ai-intelligence-domain](https://github.com/azure-intelligence-domain/ai-intelligence-domain)
repository; contract style follows the adidas API guidelines (ADR 0008).

- Never edit `rulesets/adidas/`: it is vendored, verified by checksum. Put
  adaptations in `rulesets/azure-intelligence-domain.spectral.yaml`, each with
  its reason, and record them in ADR 0008.
- A released envelope version is immutable (`schemas/envelope/released.json`).
  Changes go into a new version folder and follow the adidas rules for
  extending: only add optional attributes.
- The library ships a copy of the latest schema; keep both identical (a test
  checks this).
- Every new lint rule gets a test in `tests/test_rulesets.py` proving it fires.
- Before committing: `uv run ruff check . && uv run ruff format --check . &&
  uv run pytest` and `npm run lint`.

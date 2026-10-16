# Vendored: adidas API guidelines rulesets

Unmodified copies of the Spectral rulesets from
[adidas/api-guidelines](https://github.com/adidas/api-guidelines), pinned to
commit `222b294d13872d55befbf61b3ee60998fcb9e57b` (2025-09-19).

| File here | Upstream file | Contents |
|---|---|---|
| `adidas-spectral.yaml` | `adidas-spectral.yaml` | The ruleset the adidas README documents. |
| `adidas-maturity.spectral.yml` | `.spectral.yml` | The same rules plus 15 API maturity matrix rules, but without `adidas-headers-no-x-headers` and `adidas-request-GET-no-body`. |
| `supermodel/adidas/api/HAL.yaml` | same path | Schema used by the HAL rules. |
| `supermodel/adidas/api/ProblemDetail.yaml` | same path | Schema used by the Problem Detail rules. |
| `SHA256SUMS` | — | Checksums of the files above, verified by the tests. |

Neither upstream file contains all adidas rules, so the platform ruleset
extends **both**. The 25 rules they share are defined identically (checked
when vendoring).

Licensed under the MIT licence by adidas-group (see `LICENSE` in this folder).

**Do not edit these files.** Deviations live in
`../azure-intelligence-domain.spectral.yaml`, each with its reason. To update,
copy the files again from a newer upstream commit and change the commit above.

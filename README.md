# contracts

The shared contracts of the
[AI Intelligence Domain demo](https://github.com/azure-intelligence-domain/ai-intelligence-domain)
integration platform. Owned by the **platform team**.

> Standardise the envelope, not the payload.

All contracts follow the **[adidas API guidelines](https://github.com/adidas/api-guidelines)**,
with the adaptations listed in
[ADR 0008](https://github.com/azure-intelligence-domain/ai-intelligence-domain/blob/main/docs/adr/0008-adidas-api-guidelines.md).

| Folder | What |
|---|---|
| [`schemas/envelope/`](schemas/envelope/) | The event envelope: CloudEvents 1.0 + `correlationid` + business keys. Versioned and immutable once released. |
| [`src/integration_envelope/`](src/integration_envelope/) | Python library to create and validate envelopes (`integration-envelope`). |
| [`asyncapi/landscape.asyncapi.yaml`](asyncapi/landscape.asyncapi.yaml) | Shared servers and security schemes every AsyncAPI contract refers to. |
| [`rulesets/`](rulesets/) | Spectral lint rules: the adidas ruleset (vendored, unmodified) plus this platform's rules. |
| [`templates/`](templates/) | Starting points for new contracts: event producer, event consumer, REST API. They pass every lint rule. |
| [`.github/workflows/contract-check.yml`](.github/workflows/contract-check.yml) | Reusable contract check every repository calls before it deploys. |

## The envelope

Every event on the platform is a CloudEvent in structured JSON mode
(`application/cloudevents+json`):

```json
{
  "specversion": "1.0",
  "id": "a1f3-77c2",
  "type": "com.acme.stock.reserved",
  "source": "/wms/stock-to-3pl/v2.4",
  "time": "2026-10-07T14:02:00Z",
  "datacontenttype": "application/json",
  "correlationid": "ord-4711",
  "customerid": "ACME",
  "orderid": "4711",
  "data": { "warehouseId": "BRU-01", "reservedQuantity": 12 }
}
```

```mermaid
flowchart LR
    subgraph envelope["Envelope · this repository · same for every event"]
        core["CloudEvents core<br/>specversion · id · source · type · time · datacontenttype"]
        journey["Journey<br/>correlationid · required"]
        keys["Business keys<br/>customerid · orderid · partnerid · componentid<br/>at least one required"]
        trace["Tracing<br/>traceparent · tracestate · optional"]
    end
    subgraph payload["data · producer's AsyncAPI contract · differs per event"]
        data["camelCase fields<br/>ISO 8601 UTC · ISO 4217 · ISO 3166"]
    end
    envelope --- payload
```

| Rule | Enforced by |
|---|---|
| `correlationid` is required | schema `required` |
| At least one business key (`customerid`, `orderid`, `partnerid`, `componentid`) | schema `anyOf` |
| `time` is ISO 8601 in UTC (`Z`) | schema `pattern` (adidas common data types) |
| `type` is reverse-DNS, at least four segments | schema `pattern` |
| No `null` values, no unknown attributes from producers | schema types, `additionalProperties: false` |
| Consumers tolerate unknown attributes | `read()` (adidas robustness principle) |

Envelope attribute names are lowercase because CloudEvents requires it. The
`data` payload follows the adidas camelCase convention.

## Using the library

```python
from integration_envelope import BusinessKeys, new_event

event = new_event(
    type="com.acme.supply.stock.reserved",
    source="/system-api-wms/1.0.0",
    correlation_id="ord-4711",
    keys=BusinessKeys(customer_id="ACME", order_id="4711"),
    data={"warehouseId": "BRU-01", "reservedQuantity": 12},
)
```

Install a released version, pinned:

```toml
dependencies = [
  "integration-envelope @ git+https://github.com/azure-intelligence-domain/contracts@v1.2.0",
]
```

## Contract check: no contract, no deploy

Every repository calls the reusable workflow before it deploys:

```yaml
jobs:
  contracts:
    uses: azure-intelligence-domain/contracts/.github/workflows/contract-check.yml@v1.1.0
    with:
      contracts: openapi.yaml asyncapi.yaml
      contracts-ref: v1.1.0
  deploy:
    needs: contracts
```

```mermaid
flowchart LR
    pr["Change in a repository"] --> exists{"Contract<br/>exists?"}
    exists -- no --> fail["❌ No deploy"]
    exists -- yes --> lint{"adidas API<br/>guidelines?"}
    lint -- "error or warning" --> fail
    lint -- ok --> changed{"Changed since<br/>last release tag?"}
    changed -- no --> ok["✅ Deploy"]
    changed -- yes --> version{"info.version<br/>increased?"}
    version -- no --> fail
    version -- yes --> breaking{"Breaking<br/>change?"}
    breaking -- yes --> fail
    breaking -- no --> ok
```

Breaking changes follow the adidas rules for extending:

| Contract | Tool | Breaking |
|---|---|---|
| OpenAPI | [oasdiff](https://github.com/oasdiff/oasdiff) (`ERR` level) | Removed paths or properties, new required parameters, changed types, … |
| AsyncAPI | `@asyncapi/diff` for channels and operations, plus [`scripts/asyncapi-breaking.mjs`](scripts/asyncapi-breaking.mjs) for message payloads | Removed messages, properties or enum values; any change to `required`; changed types, constants or constraints |

`@asyncapi/diff` does not classify payload schema changes, which is why the
payload check exists. A change that cannot follow the rules for extending
becomes a new event type on a new channel, or a new resource variant.

### Producers and consumers

A producer's AsyncAPI contract has only `publish` operations and owns the
message definitions. Each consumer has its own contract with only `subscribe`
operations, referring to the producer's released message. EventCatalog combines
both into one picture of who sends and who receives.

## Versioning

- Envelope and library follow semantic versioning.
- A released schema version is **immutable**: its SHA-256 is recorded in
  [`schemas/envelope/released.json`](schemas/envelope/released.json) and a test
  fails if the file changes. Changes go into a new version folder, following
  the adidas rules for extending (add only optional attributes).

## Development

```bash
uv sync && npm ci && scripts/install-oasdiff.sh
uv run ruff check . && uv run pytest
npx spectral lint templates/*.yaml asyncapi/*.yaml --fail-severity=warn
```

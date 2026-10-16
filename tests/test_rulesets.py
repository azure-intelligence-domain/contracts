"""The lint rules enforce the adidas guidelines and the platform rules.

Each test copies a template, breaks one rule and asserts that Spectral reports exactly that rule.
The templates themselves must pass with no warnings or errors.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RULESET = ROOT / ".spectral.yaml"
ASYNC_TEMPLATE = "templates/event-producer.asyncapi.yaml"
REST_TEMPLATE = "templates/rest-api.openapi.yaml"
SEVERITIES = {0: "error", 1: "warn", 2: "info", 3: "hint"}


def lint(path: Path) -> dict[str, str]:
    """Spectral results as {rule code: severity}, infos and hints excluded."""
    run = subprocess.run(
        [
            "npx",
            "--no-install",
            "spectral",
            "lint",
            str(path),
            "--ruleset",
            str(RULESET),
            "--format",
            "json",
            "--quiet",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    results = json.loads(run.stdout or "[]")
    return {r["code"]: SEVERITIES[r["severity"]] for r in results if r["severity"] <= 1}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A copy of the contracts, so templates keep resolving their relative $refs."""
    for folder in ("asyncapi", "schemas", "templates"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    return tmp_path


def broken(workspace: Path, template: str, change) -> Path:
    path = workspace / template
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "contract",
    [ASYNC_TEMPLATE, REST_TEMPLATE, "asyncapi/landscape.asyncapi.yaml"],
)
def test_templates_pass_every_rule(contract):
    assert lint(ROOT / contract) == {}


# --- AsyncAPI ------------------------------------------------------------------------------------

CHANNEL = "supply.wms.event.stock-reserved"


def message(document):
    return document["components"]["messages"]["stockReserved"]


def rename_channel(document):
    document["channels"]["StockReserved"] = document["channels"].pop(CHANNEL)


def drop_envelope(document):
    message(document)["payload"] = message(document)["payload"]["allOf"][1]


def set_offset_time_in_example(document):
    message(document)["examples"][0]["payload"]["time"] = "2026-10-07T16:02:00+02:00"


def drop_correlation_id_from_example(document):
    del message(document)["examples"][0]["payload"]["correlationid"]


def snake_case_data_property(document):
    properties = document["components"]["schemas"]["stockReservedData"]["properties"]
    properties["warehouse_id"] = properties.pop("warehouseId")


ASYNC_VIOLATIONS = {
    "platform-channel-name": rename_channel,
    "platform-channel-description": lambda d: d["channels"][CHANNEL].pop("description"),
    "platform-channel-servers": lambda d: d["channels"][CHANNEL].pop("servers"),
    "platform-producers-listed": lambda d: d["channels"][CHANNEL]["publish"].pop("x-producers"),
    "platform-consumers-listed": lambda d: d["channels"][CHANNEL]["subscribe"].pop("x-consumers"),
    "platform-operation-required-fields": lambda d: d["channels"][CHANNEL]["publish"].pop(
        "externalDocs"
    ),
    "platform-message-cloudevents": lambda d: message(d).update(contentType="application/json"),
    "platform-message-envelope": drop_envelope,
    "platform-message-description": lambda d: message(d).pop("description"),
    "platform-message-examples": lambda d: message(d).pop("examples"),
    "platform-payload-properties-camelCase": snake_case_data_property,
    "platform-contact-email-or-url": lambda d: d["info"]["contact"].pop("url"),
    "platform-asyncapi-id": lambda d: d.update(id="supply-events"),
    "platform-external-docs-catalog": lambda d: d.pop("externalDocs"),
    "asyncapi-info-description": lambda d: d["info"].pop("description"),
}


@pytest.mark.parametrize("rule", sorted(ASYNC_VIOLATIONS))
def test_asyncapi_violation_is_reported(workspace, rule):
    assert rule in lint(broken(workspace, ASYNC_TEMPLATE, ASYNC_VIOLATIONS[rule]))


@pytest.mark.parametrize("change", [set_offset_time_in_example, drop_correlation_id_from_example])
def test_examples_must_follow_the_envelope(workspace, change):
    assert "asyncapi-message-examples" in lint(broken(workspace, ASYNC_TEMPLATE, change))


# --- OpenAPI -------------------------------------------------------------------------------------

PATH = "/orders/{orderId}"


def operation(document):
    return document["paths"][PATH]["get"]


def version_the_uri(document):
    document["paths"]["/v1" + PATH] = document["paths"].pop(PATH)


def camel_case_path(document):
    document["paths"]["/salesOrders/{orderId}"] = document["paths"].pop(PATH)


def plain_json_success(document):
    content = operation(document)["responses"]["200"]["content"]
    content["application/json"] = content.pop("application/hal+json")


def plain_json_error(document):
    content = operation(document)["responses"]["404"]["content"]
    content["application/json"] = content.pop("application/problem+json")


def x_header(document):
    operation(document)["parameters"].append(
        {
            "name": "X-Request-Id",
            "in": "header",
            "description": "Legacy id.",
            "schema": {"type": "string"},
        }
    )


def drop_correlation_id(document):
    operation(document)["parameters"] = [{"$ref": "#/components/parameters/orderId"}]
    document["components"]["parameters"].pop("correlationId")


REST_VIOLATIONS = {
    "platform-oas-no-uri-versioning": version_the_uri,
    "adidas-paths-kebab-case": camel_case_path,
    "platform-oas-title-domain": lambda d: d["info"].update(title="Orders API"),
    "platform-oas-resource-name": lambda d: d["paths"][PATH].pop("x-summary"),
    "platform-oas-summary-title-case": lambda d: operation(d).update(summary="retrieve an order"),
    "platform-oas-correlation-id": drop_correlation_id,
    "platform-oas-error-problem-json": plain_json_error,
    "adidas-oas3-response-success-OK": plain_json_success,
    "adidas-headers-no-x-headers": x_header,
    "adidas-oas3-security-section-required": lambda d: d.pop("security"),
    "adidas-oas3-stable-semantic-version": lambda d: d["info"].update(version="1.0.0-SNAPSHOT"),
}


@pytest.mark.parametrize("rule", sorted(REST_VIOLATIONS))
def test_openapi_violation_is_reported(workspace, rule):
    assert rule in lint(broken(workspace, REST_TEMPLATE, REST_VIOLATIONS[rule]))

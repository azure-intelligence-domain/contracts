import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any
from uuid import uuid4

from jsonschema import Draft7Validator, FormatChecker

SCHEMA_VERSION = "1.1.0"
SCHEMA: dict[str, Any] = json.loads(
    files("integration_envelope").joinpath("envelope.schema.json").read_text(encoding="utf-8")
)
BUSINESS_KEYS = ("customerid", "orderid", "partnerid", "componentid")

_validator = Draft7Validator(SCHEMA, format_checker=FormatChecker())


class EnvelopeError(ValueError):
    """The event does not follow the envelope contract. `problems` lists every violation."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Invalid event envelope: " + "; ".join(problems))


@dataclass(frozen=True)
class BusinessKeys:
    """Who and what the event is about. At least one key is required."""

    customer_id: str | None = None
    order_id: str | None = None
    partner_id: str | None = None
    component_id: str | None = None

    def as_attributes(self) -> dict[str, str]:
        attributes = {
            "customerid": self.customer_id,
            "orderid": self.order_id,
            "partnerid": self.partner_id,
            "componentid": self.component_id,
        }
        # adidas JSON rule: fields with a null value are omitted.
        return {name: value for name, value in attributes.items() if value is not None}


def new_event(
    *,
    type: str,
    source: str,
    correlation_id: str,
    keys: BusinessKeys,
    data: Mapping[str, Any],
    subject: str | None = None,
    dataschema: str | None = None,
    traceparent: str | None = None,
    id: str | None = None,
    time: datetime | None = None,
) -> dict[str, Any]:
    """Build a valid envelope around `data`, or raise EnvelopeError."""
    event: dict[str, Any] = {
        "specversion": "1.0",
        "id": id or str(uuid4()),
        "source": source,
        "type": type,
        "time": _utc_timestamp(time or datetime.now(UTC)),
        "datacontenttype": "application/json",
        "correlationid": correlation_id,
        **keys.as_attributes(),
        "data": dict(data),
    }
    optional = {"subject": subject, "dataschema": dataschema, "traceparent": traceparent}
    event.update({name: value for name, value in optional.items() if value is not None})
    validate(event)
    return event


def validate(event: Mapping[str, Any]) -> None:
    """Producer side: raise EnvelopeError unless `event` follows the contract exactly."""
    problems = [_describe(error) for error in _validator.iter_errors(dict(event))]
    if problems:
        raise EnvelopeError(sorted(problems))


def read(event: Mapping[str, Any]) -> dict[str, Any]:
    """Consumer side: validate the attributes we know, ignore unknown ones (tolerant reader)."""
    known = {name: value for name, value in event.items() if name in SCHEMA["properties"]}
    validate(known)
    return dict(event)


def _utc_timestamp(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise EnvelopeError(["time: must be timezone-aware so it can be converted to UTC"])
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _describe(error) -> str:
    if error.validator == "anyOf" and not error.path:
        return "event must carry at least one business key: " + ", ".join(BUSINESS_KEYS)
    if error.validator == "required":
        missing = error.message.split("'")[1]
        return f"{missing}: required"
    if error.validator == "additionalProperties":
        return "unknown attribute(s): " + error.message.split("(")[-1].rstrip(")")
    location = ".".join(str(part) for part in error.path) or "event"
    return f"{location}: {error.message}"

from datetime import UTC, datetime, timedelta, timezone

import pytest

from integration_envelope import BusinessKeys, EnvelopeError, new_event, read, validate

# The event from the talk's "Every event carries its context" slide.
TALK_EXAMPLE = {
    "specversion": "1.0",
    "id": "a1f3-77c2",
    "type": "com.acme.stock.reserved",
    "source": "/wms/stock-to-3pl/v2.4",
    "time": "2026-10-07T14:02:00Z",
    "datacontenttype": "application/json",
    "correlationid": "ord-4711",
    "customerid": "ACME",
    "orderid": "4711",
    "data": {"warehouseId": "BRU-01", "reservedQuantity": 12},
}


def an_event(**overrides):
    event = dict(TALK_EXAMPLE)
    event.update(overrides)
    return {name: value for name, value in event.items() if value is not ...}


def problems_of(event) -> list[str]:
    with pytest.raises(EnvelopeError) as raised:
        validate(event)
    return raised.value.problems


def test_the_talk_example_is_a_valid_envelope():
    validate(TALK_EXAMPLE)


def test_new_event_builds_a_valid_envelope_with_defaults():
    event = new_event(
        type="com.acme.supply.stock.reserved",
        source="/system-api-wms/1.0.0",
        correlation_id="ord-4711",
        keys=BusinessKeys(customer_id="ACME", order_id="4711"),
        data={"reservedQuantity": 12},
    )
    assert event["specversion"] == "1.0"
    assert event["datacontenttype"] == "application/json"
    assert event["time"].endswith("Z")
    assert event["customerid"] == "ACME" and event["orderid"] == "4711"
    assert "partnerid" not in event  # null fields are omitted, not sent as null
    assert "subject" not in event


def test_new_event_converts_time_to_utc():
    brussels = timezone(timedelta(hours=2))
    event = new_event(
        type="com.acme.supply.stock.reserved",
        source="/system-api-wms/1.0.0",
        correlation_id="ord-4711",
        keys=BusinessKeys(order_id="4711"),
        data={},
        time=datetime(2026, 10, 7, 16, 2, tzinfo=brussels),
    )
    assert event["time"] == "2026-10-07T14:02:00.000Z"


def test_new_event_rejects_a_naive_time():
    with pytest.raises(EnvelopeError, match="timezone-aware"):
        new_event(
            type="com.acme.supply.stock.reserved",
            source="/system-api-wms/1.0.0",
            correlation_id="ord-4711",
            keys=BusinessKeys(order_id="4711"),
            data={},
            time=datetime(2026, 10, 7, 14, 2),
        )


def test_new_event_refuses_to_build_an_event_without_business_keys():
    with pytest.raises(EnvelopeError, match="at least one business key"):
        new_event(
            type="com.acme.supply.stock.reserved",
            source="/system-api-wms/1.0.0",
            correlation_id="ord-4711",
            keys=BusinessKeys(),
            data={},
            time=datetime.now(UTC),
        )


def test_correlation_id_is_required():
    assert "correlationid: required" in problems_of(an_event(correlationid=...))


@pytest.mark.parametrize("key", ["customerid", "orderid", "partnerid"])
def test_any_single_business_key_is_enough(key):
    event = an_event(customerid=..., orderid=...)
    event[key] = "ACME-1"
    validate(event)


def test_at_least_one_business_key_is_required():
    problems = problems_of(an_event(customerid=..., orderid=...))
    assert problems == [
        "event must carry at least one business key: customerid, orderid, partnerid"
    ]


@pytest.mark.parametrize(
    "time",
    ["2026-10-07T16:02:00+02:00", "2026-10-07 14:02:00Z", "2026-10-07"],
)
def test_time_must_be_iso_8601_in_utc(time):
    assert any(problem.startswith("time:") for problem in problems_of(an_event(time=time)))


@pytest.mark.parametrize(
    "bad_type", ["StockReserved", "com.acme.reserved", "com.acme.stock.Reserved"]
)
def test_type_must_be_reverse_dns_with_four_segments(bad_type):
    assert any(problem.startswith("type:") for problem in problems_of(an_event(type=bad_type)))


def test_data_content_type_must_be_json():
    problems = problems_of(an_event(datacontenttype="application/xml"))
    assert any(problem.startswith("datacontenttype:") for problem in problems)


def test_null_values_are_rejected():
    problems = problems_of(an_event(customerid=None))
    assert any(problem.startswith("customerid:") for problem in problems)


def test_producers_may_not_send_unknown_attributes():
    assert problems_of(an_event(priority="high")) == [
        "unknown attribute(s): 'priority' was unexpected"
    ]


def test_consumers_tolerate_unknown_attributes():
    event = read(an_event(priority="high"))
    assert event["priority"] == "high"


def test_consumers_still_reject_a_missing_correlation_id():
    with pytest.raises(EnvelopeError, match="correlationid"):
        read(an_event(correlationid=..., priority="high"))


def test_traceparent_must_be_w3c_trace_context():
    valid = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    validate(an_event(traceparent=valid))
    assert any(
        problem.startswith("traceparent:") for problem in problems_of(an_event(traceparent="abc"))
    )

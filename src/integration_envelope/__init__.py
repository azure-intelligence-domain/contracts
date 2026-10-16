"""The integration platform's event envelope: CloudEvents 1.0 + correlation id + business keys.

Producers are conservative: `new_event` builds an envelope and `validate` rejects anything that
does not follow the contract. Consumers are tolerant: `read` ignores attributes it does not know.
(adidas guidelines, Robustness: be conservative in what you send, liberal in what you accept.)
"""

from integration_envelope.envelope import (
    BUSINESS_KEYS,
    SCHEMA,
    SCHEMA_VERSION,
    BusinessKeys,
    EnvelopeError,
    new_event,
    read,
    validate,
)

__all__ = [
    "BUSINESS_KEYS",
    "SCHEMA",
    "SCHEMA_VERSION",
    "BusinessKeys",
    "EnvelopeError",
    "new_event",
    "read",
    "validate",
]

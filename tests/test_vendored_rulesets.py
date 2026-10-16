"""The vendored adidas rulesets stay byte-identical to upstream (rulesets/adidas/README.md).

Adaptations belong in rulesets/azure-intelligence-domain.spectral.yaml, never in these files.
"""

import hashlib
from pathlib import Path

import pytest

VENDORED = Path(__file__).resolve().parents[1] / "rulesets" / "adidas"
UPSTREAM_SHA256 = {
    name: digest
    for digest, name in (
        line.split() for line in (VENDORED / "SHA256SUMS").read_text().splitlines() if line
    )
}


@pytest.mark.parametrize("name", sorted(UPSTREAM_SHA256))
def test_vendored_file_is_unmodified(name):
    digest = hashlib.sha256((VENDORED / name).read_bytes()).hexdigest()
    assert digest == UPSTREAM_SHA256[name], f"{name} differs from upstream; do not edit it"

"""A released contract version is immutable (adidas guidelines: Immutability).

`schemas/envelope/released.json` records the SHA-256 of every released schema version. Changing a
released file fails this test: publish a new version instead.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENVELOPE = ROOT / "schemas" / "envelope"
RELEASED = json.loads((ENVELOPE / "released.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("version", sorted(RELEASED))
def test_released_envelope_versions_are_unchanged(version):
    schema = ENVELOPE / version / "envelope.schema.json"
    assert sha256(schema) == RELEASED[version], (
        f"Envelope {version} is released and must not change. Publish a new version instead."
    )


def test_every_schema_version_is_recorded():
    on_disk = {path.name for path in ENVELOPE.iterdir() if path.is_dir()}
    assert on_disk == set(RELEASED), "Record every envelope version in released.json"


def test_schema_id_matches_its_version():
    for version in RELEASED:
        schema = json.loads(
            (ENVELOPE / version / "envelope.schema.json").read_text(encoding="utf-8")
        )
        # The $id points at the contracts release (tag) that first published this version.
        assert re.search(
            rf"/contracts/v\d+\.\d+\.\d+/schemas/envelope/{re.escape(version)}/envelope\.schema\.json$",
            schema["$id"],
        )


def test_library_ships_the_latest_schema_unchanged():
    from integration_envelope import SCHEMA_VERSION

    packaged = ROOT / "src" / "integration_envelope" / "envelope.schema.json"
    published = ENVELOPE / SCHEMA_VERSION / "envelope.schema.json"
    assert packaged.read_bytes() == published.read_bytes()

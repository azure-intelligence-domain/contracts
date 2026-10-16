"""The contract check gates every deployment: no contract, no deploy; no breaking changes."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "contract_check.py"
PRODUCER = "templates/event-producer.asyncapi.yaml"
REST = "templates/rest-api.openapi.yaml"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository with the templates as its contracts, released as v1.0.0."""
    for folder in ("asyncapi", "schemas", "templates"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    git(tmp_path, "init", "-q", "-b", "main")
    git(
        tmp_path,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "empty",
    )
    git(tmp_path, "add", "-A")
    git(
        tmp_path,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-q",
        "-m",
        "contracts",
    )
    git(tmp_path, "tag", "v1.0.0")
    return tmp_path


def check(repo: Path, *contracts: str, base: str | None = None) -> tuple[int, str]:
    command = [sys.executable, str(CHECK), *contracts]
    if base is not None:
        command += ["--base", base]
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout + result.stderr


def edit(repo: Path, contract: str, change) -> None:
    path = repo / contract
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def bump(document, version="1.1.0"):
    document["info"]["version"] = version


def add_optional_field(document):
    data = document["components"]["schemas"]["stockReservedData"]
    data["properties"]["pickingZone"] = {"type": "string", "description": "Optional zone."}


def change_quantity_type(document):
    data = document["components"]["schemas"]["stockReservedData"]
    data["properties"]["orderLines"]["items"]["properties"]["reservedQuantity"]["type"] = "string"
    example = document["components"]["messages"]["stockReserved"]["examples"][0]
    example["payload"]["data"]["orderLines"][0]["reservedQuantity"] = "12"


def require_new_header(document):
    document["paths"]["/orders/{orderId}"]["get"]["parameters"].append(
        {
            "name": "Tenant-Id",
            "in": "header",
            "required": True,
            "description": "The tenant.",
            "schema": {"type": "string"},
            "example": "acme",
        }
    )


def test_no_contracts_means_no_deploy(repo):
    code, output = check(repo)
    assert code == 1 and "no contract, no deploy" in output


def test_a_missing_contract_fails(repo):
    code, output = check(repo, "asyncapi.yaml")
    assert code == 1 and "asyncapi.yaml: contract exists" in output


def test_unchanged_contracts_pass(repo):
    code, output = check(repo, PRODUCER, REST)
    assert code == 0, output
    assert "unchanged since v1.0.0" in output


def test_without_a_release_only_lint_runs(repo):
    git(repo, "tag", "-d", "v1.0.0")
    code, output = check(repo, PRODUCER)
    assert code == 0, output
    assert "breaking-change check skipped" in output


def test_a_lint_violation_fails(repo):
    edit(repo, PRODUCER, lambda d: d["info"].pop("description"))
    code, output = check(repo, PRODUCER, base="none")
    assert code == 1 and "adidas API guidelines lint" in output


def test_an_optional_field_with_a_new_version_passes(repo):
    edit(repo, PRODUCER, lambda d: (add_optional_field(d), bump(d)))
    code, output = check(repo, PRODUCER)
    assert code == 0, output


def test_a_change_without_a_new_version_fails(repo):
    edit(repo, PRODUCER, add_optional_field)
    code, output = check(repo, PRODUCER)
    assert code == 1 and "must increase" in output


def test_a_breaking_event_change_fails_even_with_a_new_version(repo):
    edit(repo, PRODUCER, lambda d: (change_quantity_type(d), bump(d, "2.0.0")))
    code, output = check(repo, PRODUCER)
    assert code == 1
    assert 'reservedQuantity: type changed from "integer" to "string"' in output


def test_a_breaking_api_change_fails_even_with_a_new_version(repo):
    edit(repo, REST, lambda d: (require_new_header(d), bump(d, "2.0.0")))
    code, output = check(repo, REST)
    assert code == 1
    assert "no breaking changes since v1.0.0" in output

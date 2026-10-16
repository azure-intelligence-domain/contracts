"""Contract check: no contract, no deploy.

Run from the root of the repository whose contracts are checked:

    uv run --project <contracts> python <contracts>/scripts/contract_check.py openapi.yaml

For every contract:
1. It exists.
2. It passes the platform ruleset (adidas API guidelines), warnings included.
3. If it changed since the last release (the latest git tag, or --base), its info.version is
   higher, and it has no breaking change (adidas rules for extending).
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

CONTRACTS = Path(__file__).resolve().parents[1]
RULESET = CONTRACTS / ".spectral.yaml"
SPECTRAL = CONTRACTS / "node_modules" / ".bin" / "spectral"
ASYNCAPI_BREAKING = CONTRACTS / "scripts" / "asyncapi-breaking.mjs"
GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"


def report(ok: bool, contract: str, message: str) -> bool:
    if not ok and GITHUB:
        print(f"::error file={contract}::{message}")
    print(f"{'✅' if ok else '❌'} {contract}: {message}")
    return ok


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=False, **kwargs)


def latest_tag() -> str | None:
    result = run(["git", "describe", "--tags", "--abbrev=0"])
    return result.stdout.strip() if result.returncode == 0 else None


def oasdiff() -> str:
    found = shutil.which("oasdiff") or str(CONTRACTS / ".tools" / "bin" / "oasdiff")
    if not Path(found).exists():
        sys.exit("oasdiff not found: run scripts/install-oasdiff.sh")
    return found


def semver(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in str(version).split("."))


def lint(contract: str) -> bool:
    result = run(
        [
            str(SPECTRAL),
            "lint",
            contract,
            "--ruleset",
            str(RULESET),
            "--fail-severity=warn",
            "--display-only-failures",
        ]
    )
    if result.returncode != 0:
        print(result.stdout.strip())
    return report(result.returncode == 0, contract, "adidas API guidelines lint")


def compare_with_release(contract: str, base: str, release_tree: Path) -> bool:
    released = release_tree / contract
    if not released.exists():
        return report(True, contract, f"new since {base}, nothing to compare")
    if released.read_bytes() == Path(contract).read_bytes():
        return report(True, contract, f"unchanged since {base}")

    old = yaml.safe_load(released.read_text(encoding="utf-8"))
    new = yaml.safe_load(Path(contract).read_text(encoding="utf-8"))
    ok = report(
        semver(new["info"]["version"]) > semver(old["info"]["version"]),
        contract,
        f"info.version {old['info']['version']} -> {new['info']['version']} must increase",
    )

    if "openapi" in new:
        command = [oasdiff(), "breaking", str(released), contract, "--fail-on", "ERR"]
    else:
        command = ["node", str(ASYNCAPI_BREAKING), str(released), contract]
    result = run(command)
    if result.returncode != 0:
        print(result.stdout.strip() or result.stderr.strip())
    return report(result.returncode == 0, contract, f"no breaking changes since {base}") and ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("contracts", nargs="*", help="contract files, relative to the repository")
    parser.add_argument(
        "--base", help="git ref of the last release (default: latest tag; 'none' to skip)"
    )
    args = parser.parse_args()

    if not args.contracts:
        return 0 if report(False, ".", "no contracts given: no contract, no deploy") else 1

    ok = True
    present = [c for c in args.contracts if report(Path(c).is_file(), c, "contract exists")]
    ok &= len(present) == len(args.contracts)
    for contract in present:
        ok &= lint(contract)

    base = latest_tag() if args.base is None else (None if args.base == "none" else args.base)
    if base is None:
        print("ℹ️  No release to compare with: breaking-change check skipped.")
        return 0 if ok else 1

    with tempfile.TemporaryDirectory() as tree:
        added = run(["git", "worktree", "add", "--detach", tree, base])
        if added.returncode != 0:
            sys.exit(f"Cannot check out {base}: {added.stderr.strip()}")
        try:
            for contract in present:
                ok &= compare_with_release(contract, base, Path(tree))
        finally:
            run(["git", "worktree", "remove", "--force", tree])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

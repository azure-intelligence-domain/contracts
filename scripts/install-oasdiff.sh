#!/usr/bin/env bash
# Install a pinned oasdiff release into .tools/bin, verified against its published checksum.
set -euo pipefail

VERSION="1.33.0"
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) ASSET="oasdiff_${VERSION}_linux_amd64.tar.gz" ;;
  Darwin-*)     ASSET="oasdiff_${VERSION}_darwin_all.tar.gz" ;;
  *) echo "Unsupported platform: $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac

DEST="${1:-$(cd "$(dirname "$0")/.." && pwd)/.tools/bin}"
if [ -x "$DEST/oasdiff" ] && "$DEST/oasdiff" --version 2>/dev/null | grep -q "$VERSION"; then
  echo "oasdiff $VERSION already installed in $DEST"; exit 0
fi

BASE="https://github.com/oasdiff/oasdiff/releases/download/v${VERSION}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
curl -fsSL -o "$WORK/$ASSET" "$BASE/$ASSET"
curl -fsSL -o "$WORK/checksums.txt" "$BASE/checksums.txt"
(cd "$WORK" && grep " $ASSET\$" checksums.txt | shasum -a 256 -c -)
mkdir -p "$DEST" && tar -xzf "$WORK/$ASSET" -C "$WORK" oasdiff && mv "$WORK/oasdiff" "$DEST/oasdiff"
echo "Installed oasdiff $VERSION in $DEST"

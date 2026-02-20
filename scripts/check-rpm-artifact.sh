#!/usr/bin/env bash
set -euo pipefail

artifact="${1:-}"
if [ -z "$artifact" ]; then
  echo "Usage: $0 <path-to-rpm>" >&2
  exit 1
fi

if [ ! -f "$artifact" ]; then
  echo "RPM artifact not found: $artifact" >&2
  exit 1
fi

if ! command -v rpm >/dev/null 2>&1; then
  echo "rpm tool is required for RPM verification" >&2
  exit 1
fi

rpm -qpi "$artifact" >/dev/null
rpm -qpl "$artifact" >/dev/null

echo "RPM artifact sanity check passed: $artifact"

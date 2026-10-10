#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

user_site="$(python3.11 -m site --user-site)"
uv pip install --python 3.11 --target "$user_site" --group test .

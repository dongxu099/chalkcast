#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec uv run chalkcast studio "$@"

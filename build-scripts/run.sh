#!/usr/bin/env bash
set -e

echo "Init python"
source .venv/bin/activate

python dist/webserve_bundle.py --program webserve

deactivate

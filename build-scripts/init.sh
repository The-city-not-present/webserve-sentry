#!/usr/bin/env bash
set -e

# pushd ..
if [ ! -d "./dist" ]; then
  mkdir -p "./dist"
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

if [ ! -f "src-make/lib/pinliner/pinliner/pinliner.py" ]; then
  # TODO: confirm is having --remote fine? I think it is. It's something like apt update, it is normal to run this occasionally. I don't see an issue
  git submodule update --init --recursive --remote
fi

python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
# popd

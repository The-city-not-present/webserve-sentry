#!/usr/bin/env bash
set -e

# pushd ..

echo "Clear up \"dist/\"..."

mkdir -p dist
rm -rf dist
mkdir -p dist
echo "done"
echo -
echo -

echo "Init python"
source .venv/bin/activate
echo "done"
echo -
echo -

echo "Update program version"
echo "# updated" > src/_VERSION.py
python -c 'from datetime import datetime; print(f"# {datetime.now()}")' >> src/_VERSION.py
echo "_VERSION = '''" >> src/_VERSION.py
git describe >> src/_VERSION.py
echo "'''" >> src/_VERSION.py
echo "done"
echo -
echo -

echo "Re-build htmler..."
pushd src/endpoints/lib/htmltmpl
if [ -f compiled/html_bundle.py ]; then
  rm -rf compiled/html_bundle.py
fi
make init
make build-only-static
popd
echo "done"
echo -
echo -

echo "Produce \"webserve_bundle.py\""
echo "Calling pinliner..."
# if [ ! -f "src-make/lib/pinliner/pinliner/pinliner.py" ]; then
#   # TODO: confirm is having --remote fine? I think it is. It's something like apt update, it is normal to run this occasionally. I don't see an issue
#   git submodule update --init --recursive --remote
# fi
# comment: please delete .pyc files before every call of the webserve_bundle - this is implemented in my fork of the pinliner
# python src-make/lib/pinliner/pinliner/pinliner.py src -o dist/webserve_bundle.py --verbose
python "src-make/lib/pinliner/pinliner/pinliner.py" src -o dist/webserve_bundle.py
echo "done"
echo "Patching webserve_bundle.py..."
echo "# ..." >> "dist/webserve_bundle.py"
echo "# print('within webserve_bundle')" >> "dist/webserve_bundle.py"
# no need for this, the root package is loaded automatically
# echo "# import webserve_bundle" >> "dist/webserve_bundle.py"
echo "from src import launcher" >> "dist/webserve_bundle.py"
echo "launcher.main()" >> "dist/webserve_bundle.py"
echo "# print('out of webserve_bundle')" >> "dist/webserve_bundle.py"
echo "done"
echo -
echo -


echo "Bring \"static\" files to ./static/"
mkdir -p ./dist/static
rsync -av --exclude='*.py' src/endpoints/lib/htmltmpl/compiled/ ./dist/static/
echo "done"
echo -
echo -

python dist/webserve_bundle.py --program done
deactivate
# popd

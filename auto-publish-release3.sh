#!/usr/bin/env bash
set -eox pipefail
rm -rf dist/ || true
pip3 install pip --upgrade
pip3 install setuptools wheel quantum-native-python twine --upgrade
pip2 install setuptools wheel --upgrade
python3 setup.py sdist bdist_wheel
python2 setup.py bdist_wheel
twine upload --config-file "$jenkinsbot_pypirc" -r artifactory dist/*

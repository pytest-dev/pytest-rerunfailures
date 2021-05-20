#!/bin/bash

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $CURRENT_DIR/..

python3 -m pip install -e .[test] tox quantum-native-python
python3 -m tox

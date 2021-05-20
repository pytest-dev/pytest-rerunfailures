#!/bin/bash

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $CURRENT_DIR/..

python3 -m pip install -e .[test] tox quantum-native-python 'quantum-native-python3<3.8>3.7'
python3 -m tox

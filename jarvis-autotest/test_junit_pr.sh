#!/bin/bash

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $CURRENT_DIR/..

pip install -e .
pytest --junitxml results.xml test_pytest_rerunfailures.py

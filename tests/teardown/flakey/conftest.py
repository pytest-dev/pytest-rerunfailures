import py, pytest
from tests.base import BaseTest

def pytest_runtest_teardown(item, nextitem):
    BaseTest().pass_the_third_time('test_flakey_teardown')

def pytest_runtest_setup(item):
    pass
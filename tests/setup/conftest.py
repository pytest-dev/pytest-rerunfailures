import py, pytest

from tests.base import BaseTest


def pytest_runtest_setup(item):
    BaseTest().pass_the_third_time('test_flakey_setup')

def pytest_runtest_teardown(item):
    pass
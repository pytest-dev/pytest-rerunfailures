import py, pytest

def pytest_runtest_setup(item):
    print "failing setup"
    raise Exception("OMG, a setup failure")

def pytest_runtest_teardown(item):
    pass
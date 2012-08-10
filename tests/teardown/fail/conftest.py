import py, pytest

def pytest_runtest_teardown(item, nextitem):
    print "failing teardown"
    raise Exception("OMG, a teardown failure")

def pytest_runtest_setup(item):
    pass
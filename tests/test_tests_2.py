import pytest

@pytest.fixture(scope='session')
def session_fixture_1():
    print('session_fixture_1 setup')
    yield
    print('session_fixture_1 teardown')


@pytest.fixture(scope='session')
def session_fixture_2(session_fixture_1):
    print('session_fixture_2 setup')
    yield
    print('session_fixture_2 teardown')


@pytest.fixture(scope='session')
def session_fixture_3(session_fixture_1):
    print('session_fixture_3 setup')
    yield
    print('session_fixture_3 teardown')




def test_test_passing_1(session_fixture_1):
    assert True

def test_test_failing(session_fixture_2):
    assert False

def test_test_passing_2(session_fixture_3):
    assert True






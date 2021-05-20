import pytest

FAILURE = """
number_{id} = 0

def test_test_failing_{id}(session_fixture_2):
    global number_{id}
    number_{id} += 1
    assert number_{id} == 1 + {ind}

"""

TESTS = """
import pytest

number_1 = 0

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

{}

def test_test_passing_2(session_fixture_3):
    assert True
"""


def make_simple_pytest_suite(testdir, total_failures=1, expected_reruns=0, has_failure=False):
    failures = ''
    for i in range(total_failures):
        failures += FAILURE.format(id=i, ind=expected_reruns + int(has_failure))
        failures += '\n'
    testdir.makepyfile(
        TESTS.format(TESTS.format(failures))
    )


def assert_outcomes(result, passed=1, skipped=0, failed=0, error=0, xfailed=0,
                    xpassed=0, rerun=0):
    outcomes = result.parseoutcomes()
    assert outcomes.get('passed', 0) == passed
    assert outcomes.get('skipped', 0) == skipped
    assert outcomes.get('failed', 0) == failed
    assert outcomes.get('xfailed', 0) == xfailed
    assert outcomes.get('xpassed', 0) == xpassed
    assert outcomes.get('rerun', 0) == rerun


def temporary_failure(count=1):
    return """import py
            path = py.path.local(__file__).dirpath().ensure('test.res')
            count = path.read() or 1
            if int(count) <= {0}:
                path.write(int(count) + 1)
                raise Exception('Failure: {{0}}'.format(count))""".format(count)

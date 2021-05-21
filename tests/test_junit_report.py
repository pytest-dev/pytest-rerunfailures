import pytest
import xmltodict

from conftest import make_simple_pytest_suite, assert_outcomes, temporary_failure


pytest_plugins = 'pytester'


def test_reruns_junit_all_tests_passed(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, expected_reruns=0, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=3, rerun=0)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        if artifact_data.get('testsuites'):
            artifact_data = artifact_data['testsuites']
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '0'
        assert artifact_data['testsuite']['@tests'] == '3'
        assert len(artifact_data['testsuite']['testcase']) == 3


def test_reruns_junit_all_tests_resolved(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, expected_reruns=1, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=3, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        if artifact_data.get('testsuites'):
            artifact_data = artifact_data['testsuites']
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '0'
        assert artifact_data['testsuite']['@tests'] == '3'
        assert len(artifact_data['testsuite']['testcase']) == 3


def test_reruns_junit_all_tests_failed(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=2, rerun=1, failed=1)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        if artifact_data.get('testsuites'):
            artifact_data = artifact_data['testsuites']
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '1'
        assert artifact_data['testsuite']['@tests'] == '3'
        assert len(artifact_data['testsuite']['testcase']) == 3
        assert artifact_data['testsuite']['testcase'][2]['failure']


def test_reruns_junit_max_reruns_reached(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
        '--max-tests-rerun', '1'
    )
    assert_outcomes(result, passed=2, rerun=0, failed=2)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        if artifact_data.get('testsuites'):
            artifact_data = artifact_data['testsuites']
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '2'
        assert artifact_data['testsuite']['@tests'] == '4'
        assert len(artifact_data['testsuite']['testcase']) == 4
        assert artifact_data['testsuite']['testcase'][2]['failure']
        assert artifact_data['testsuite']['testcase'][3]['failure']


def test_reruns_junit_2_tests_resolved(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=4, rerun=2, failed=0)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        if artifact_data.get('testsuites'):
            artifact_data = artifact_data['testsuites']
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '0'
        assert artifact_data['testsuite']['@tests'] == '4'
        assert len(artifact_data['testsuite']['testcase']) == 4


def test_reruns_junit_2_tests_failed(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=2, rerun=2, failed=2)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        if artifact_data.get('testsuites'):
            artifact_data = artifact_data['testsuites']
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '2'
        assert artifact_data['testsuite']['@tests'] == '4'
        assert len(artifact_data['testsuite']['testcase']) == 4
        assert artifact_data['testsuite']['testcase'][2]['failure']
        assert artifact_data['testsuite']['testcase'][3]['failure']


def test_reruns_junit_after_temporary_setup_resolved(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            {0}""".format(temporary_failure()))
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=1, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        if artifact_data.get('testsuites'):
            artifact_data = artifact_data['testsuites']
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '0'
        assert artifact_data['testsuite']['@tests'] == '1'
        assert artifact_data['testsuite']['testcase']


def test_reruns_junit_after_temporary_setup_failure(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            {0}""".format(temporary_failure(2)))
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=0, error=1, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        if artifact_data.get('testsuites'):
            artifact_data = artifact_data['testsuites']
        assert artifact_data['testsuite']['@errors'] == '1'
        assert artifact_data['testsuite']['@failures'] == '0'
        assert artifact_data['testsuite']['@tests'] == '1'
        assert artifact_data['testsuite']['testcase']
        assert artifact_data['testsuite']['testcase']['error']

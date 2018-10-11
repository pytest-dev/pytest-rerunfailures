import os
import json

import pytest
import xmltodict

from conftest import make_simple_pytest_suite, assert_outcomes, temporary_failure


pytest_plugins = 'pytester'


def test_xdist_all_tests_passed_with_stats(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, expected_reruns=0, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '-n', '2',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=3, rerun=0)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data == {
            'total_reruns': 0,
            'total_failed': 0,
            'total_resolved_by_reruns': 0,
            'rerun_tests': []
        }


def test_xdist_all_tests_resolved_with_stats(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '-n', '2',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=4, rerun=2)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data['total_reruns'] == 2
        assert artifact_data['total_failed'] == 2
        assert artifact_data['total_resolved_by_reruns'] == 2
        assert artifact_data['rerun_tests'][0]['status'] == 'flake'
        assert artifact_data['rerun_tests'][1]['status'] == 'flake'
        assert set([
            artifact_data['rerun_tests'][0]['nodeid'],
            artifact_data['rerun_tests'][1]['nodeid']
        ]) == set([
            'test_xdist_all_tests_resolved_with_stats.py::test_test_failing_1',
            'test_xdist_all_tests_resolved_with_stats.py::test_test_failing_0'
        ])


def test_xdist_all_tests_failed_with_stats(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '-n', '2',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=2, rerun=2, failed=2)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data['total_reruns'] == 2
        assert artifact_data['total_failed'] == 2
        assert artifact_data['total_resolved_by_reruns'] == 0
        assert artifact_data['rerun_tests'][0]['status'] == 'failed'
        assert artifact_data['rerun_tests'][1]['status'] == 'failed'
        assert set([
            artifact_data['rerun_tests'][0]['nodeid'],
            artifact_data['rerun_tests'][1]['nodeid']
        ]) == set([
            'test_xdist_all_tests_failed_with_stats.py::test_test_failing_1',
            'test_xdist_all_tests_failed_with_stats.py::test_test_failing_0'
        ])


def test_xdist_all_tests_max_reruns_with_stats(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '-n', '2', '--dist', 'loadfile',
        '--reruns-artifact-path', artifact_path,
        '--max-tests-rerun', '1'
    )
    assert_outcomes(result, passed=2, rerun=2, failed=2)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data == {
            'total_reruns': 0,
            'total_failed': 0,
            'total_resolved_by_reruns': 0,
            'rerun_tests': []
        }


def test_xdist_after_temporary_setup_resolved_with_stats(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            {0}""".format(temporary_failure()))
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
        '-n', '2', '--dist', 'loadfile',
    )
    assert_outcomes(result, passed=1, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data['total_reruns'] == 1
        assert artifact_data['total_failed'] == 1
        assert artifact_data['total_resolved_by_reruns'] == 1
        assert artifact_data['rerun_tests'][0]['status'] == 'flake'
        assert artifact_data['rerun_tests'][0]['nodeid'] == 'test_xdist_after_temporary_setup_resolved_with_stats.py::test_pass'


def test_xdist_after_temporary_setup_failure_with_stats(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            {0}""".format(temporary_failure(2)))
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
        '-n', '2', '--dist', 'loadfile',
    )
    assert_outcomes(result, passed=0, error=1, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        print(artifact_data)
        assert artifact_data['total_reruns'] == 1
        assert artifact_data['total_failed'] == 1
        assert artifact_data['total_resolved_by_reruns'] == 0
        assert artifact_data['rerun_tests'][0]['status'] == 'failed'
        assert artifact_data['rerun_tests'][0]['nodeid'] == 'test_xdist_after_temporary_setup_failure_with_stats.py::test_pass'


def test_xdist_all_tests_passed_with_junit(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, expected_reruns=0, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '-n', '2',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=3, rerun=0)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '0'
        assert artifact_data['testsuite']['@tests'] == '3'
        assert len(artifact_data['testsuite']['testcase']) == 3


def test_xdist_all_tests_resolved_with_junit(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '-n', '2',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=4, rerun=2)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '0'
        assert artifact_data['testsuite']['@tests'] == '4'
        assert len(artifact_data['testsuite']['testcase']) == 4


def test_xdist_all_tests_failed_with_junit(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '-n', '2',
        '--junitxml', artifact_path,
    )
    assert_outcomes(result, passed=2, rerun=2, failed=2)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '2'
        assert artifact_data['testsuite']['@tests'] == '4'
        assert len(artifact_data['testsuite']['testcase']) == 4
        assert len(
            [t for t in artifact_data['testsuite']['testcase'] if 'failure' in t]
        ) == 2



def test_xdist_all_tests_max_reruns_with_junit(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '-n', '2', '--dist', 'loadfile',
        '--junitxml', artifact_path,
        '--max-tests-rerun', '1'
    )
    assert_outcomes(result, passed=2, rerun=2, failed=2)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '2'
        assert artifact_data['testsuite']['@tests'] == '4'
        assert len(artifact_data['testsuite']['testcase']) == 4
        assert len(
            [t for t in artifact_data['testsuite']['testcase'] if 'failure' in t]
        ) == 2


def test_xdist_after_temporary_setup_resolved_with_junit(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            {0}""".format(temporary_failure()))
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
        '-n', '2', '--dist', 'loadfile',
    )
    assert_outcomes(result, passed=1, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        assert artifact_data['testsuite']['@errors'] == '0'
        assert artifact_data['testsuite']['@failures'] == '0'
        assert artifact_data['testsuite']['@tests'] == '1'
        assert artifact_data['testsuite']['testcase']


def test_xdist_after_temporary_setup_failure_with_junit(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.xml'
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            {0}""".format(temporary_failure(2)))
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--junitxml', artifact_path,
        '-n', '2', '--dist', 'loadfile',
    )
    assert_outcomes(result, passed=0, error=1, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = xmltodict.parse(artifact.read())
        assert artifact_data['testsuite']['@errors'] == '1'
        assert artifact_data['testsuite']['@failures'] == '0'
        assert artifact_data['testsuite']['@tests'] == '1'
        assert artifact_data['testsuite']['testcase']
        assert artifact_data['testsuite']['testcase']['error']

def test_xdist_worker_rerun_stats(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '-n', '2', '--dist', 'loadfile',
        '--reruns-artifact-path', artifact_path,
        '--xdist-worker-reruns-artifact',
    )
    assert_outcomes(result, passed=4, rerun=2)
    if os.path.isfile(testdir.tmpdir.strpath + '/gw0_artifact.json'):
        xdist_artifact_path = testdir.tmpdir.strpath + '/gw0_artifact.json'
    else:
        xdist_artifact_path = testdir.tmpdir.strpath + '/gw1_artifact.json'

    with open(xdist_artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data['total_reruns'] == 2
        assert artifact_data['total_failed'] == 2
        assert artifact_data['total_resolved_by_reruns'] == 2
        assert artifact_data['rerun_tests'][0]['status'] == 'flake'
        assert artifact_data['rerun_tests'][1]['status'] == 'flake'
        assert set([
            artifact_data['rerun_tests'][0]['nodeid'],
            artifact_data['rerun_tests'][1]['nodeid']
        ]) == set([
            'test_xdist_worker_rerun_stats.py::test_test_failing_1',
            'test_xdist_worker_rerun_stats.py::test_test_failing_0'
        ])

import json

import pytest

from conftest import make_simple_pytest_suite, assert_outcomes, temporary_failure


pytest_plugins = 'pytester'


def test_reruns_stats_all_tests_passed(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, expected_reruns=0, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
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


def test_reruns_stats_all_tests_resolved(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, expected_reruns=1, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=3, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data == {
            'total_reruns': 1,
            'total_failed': 1,
            'total_resolved_by_reruns': 1,
            'rerun_tests': [
                {
                    'nodeid': 'test_reruns_stats_all_tests_resolved.py::test_test_failing_0',
                    'status': 'flake',
                    'rerun_trace': {
                        'teardown': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\nsession_fixture_1 setup\nsession_fixture_2 setup\nsession_fixture_2 teardown\nsession_fixture_1 teardown\n',
                            'text_repr': ''
                        },
                        'setup': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\nsession_fixture_1 setup\nsession_fixture_2 setup\n',
                            'text_repr': ''
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\nsession_fixture_1 setup\nsession_fixture_2 setup\n',
                            'text_repr': ''
                        }
                    },
                    'original_trace': {
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\n',
                            'text_repr': 'session_fixture_2 = None\n\n    def test_test_failing_0(session_fixture_2):\n        global number_0\n        number_0 += 1\n>       assert number_0 == 1 + 1\nE       assert 1 == (1 + 1)\n\ntest_reruns_stats_all_tests_resolved.py:60: AssertionError',
                        },
                        'setup': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\n',
                            'text_repr': ''
                        },
                        'teardown': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\n',
                            'text_repr': ''
                        }
                    }
                },
            ]
        }


def test_reruns_stats_all_tests_failed(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=2, rerun=1, failed=1)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data == {
            'total_reruns': 1,
            'total_failed': 1,
            'total_resolved_by_reruns': 0,
            'rerun_tests': [
                {
                    'nodeid': 'test_reruns_stats_all_tests_failed.py::test_test_failing_0',
                    'status': 'failed',
                    'rerun_trace': {
                        'teardown': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\nsession_fixture_1 setup\nsession_fixture_2 setup\nsession_fixture_2 teardown\nsession_fixture_1 teardown\n',
                            'text_repr': ''
                        },
                        'setup': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\nsession_fixture_1 setup\nsession_fixture_2 setup\n',
                            'text_repr': ''
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\nsession_fixture_1 setup\nsession_fixture_2 setup\n',
                            'text_repr': 'session_fixture_2 = None\n\n    def test_test_failing_0(session_fixture_2):\n        global number_0\n        number_0 += 1\n>       assert number_0 == 1 + 2\nE       assert 2 == (1 + 2)\n\ntest_reruns_stats_all_tests_failed.py:60: AssertionError'
                        }
                    },
                    'original_trace': {
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\n',
                            'text_repr': 'session_fixture_2 = None\n\n    def test_test_failing_0(session_fixture_2):\n        global number_0\n        number_0 += 1\n>       assert number_0 == 1 + 2\nE       assert 1 == (1 + 2)\n\ntest_reruns_stats_all_tests_failed.py:60: AssertionError',
                        },
                        'setup': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\n',
                            'text_repr': ''
                        },
                        'teardown': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': 'session_fixture_2 setup\n',
                            'text_repr': ''
                        }
                    }
                },
            ]
        }


def test_reruns_stats_max_reruns_reached(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
        '--max-tests-rerun', '1'
    )
    assert_outcomes(result, passed=2, rerun=0, failed=2)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data == {
            'total_reruns': 0,
            'total_failed': 0,
            'total_resolved_by_reruns': 0,
            'rerun_tests': []
        }


def test_reruns_stats_2_tests_resolved(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=False)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=4, rerun=2, failed=0)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data['total_reruns'] == 2
        assert artifact_data['total_failed'] == 2
        assert artifact_data['total_resolved_by_reruns'] == 2
        assert len(artifact_data['rerun_tests']) == 2
        assert artifact_data['rerun_tests'][0]['status'] == 'flake'
        assert artifact_data['rerun_tests'][1]['status'] == 'flake'


def test_reruns_stats_2_tests_failed(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    make_simple_pytest_suite(testdir, total_failures=2, expected_reruns=1, has_failure=True)
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=2, rerun=2, failed=2)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data['total_reruns'] == 2
        assert artifact_data['total_failed'] == 2
        assert artifact_data['total_resolved_by_reruns'] == 0
        assert len(artifact_data['rerun_tests']) == 2
        assert artifact_data['rerun_tests'][0]['status'] == 'failed'
        assert artifact_data['rerun_tests'][1]['status'] == 'failed'


def test_reruns_stats_after_temporary_setup_resolved(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            {0}""".format(temporary_failure()))
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=1, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data == {
            'total_reruns': 1,
            'total_failed': 1,
            'total_resolved_by_reruns': 1,
            'rerun_tests': [
                {
                    'status': 'flake',
                    'nodeid': 'test_reruns_stats_after_temporary_setup_resolved.py::test_pass',
                    'rerun_trace': {
                        'teardown': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': ''},
                        'setup': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': ''},
                        'call': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': ''}
                    },
                    'original_trace': {
                        'teardown': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': ''},
                        'setup': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': "item = <Function 'test_pass'>\n\n    def pytest_runtest_setup(item):\n        import py\n        path = py.path.local(__file__).dirpath().ensure('test.res')\n        count = path.read() or 1\n        if int(count) <= 1:\n            path.write(int(count) + 1)\n>           raise Exception('Failure: {0}'.format(count))\nE           Exception: Failure: 1\n\nconftest.py:7: Exception"},
                        'call': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': ''}
                    }
                }
            ]
        }


def test_reruns_stats_after_temporary_setup_failure(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            {0}""".format(temporary_failure(2)))
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=0, error=1, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data == {
            'total_reruns': 1,
            'total_failed': 1,
            'total_resolved_by_reruns': 0,
            'rerun_tests': [
                {
                    'nodeid': 'test_reruns_stats_after_temporary_setup_failure.py::test_pass',
                    'status': 'failed',
                    'rerun_trace': {
                        'teardown': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': ''},
                        'setup': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': "item = <Function 'test_pass'>\n\n    def pytest_runtest_setup(item):\n        import py\n        path = py.path.local(__file__).dirpath().ensure('test.res')\n        count = path.read() or 1\n        if int(count) <= 2:\n            path.write(int(count) + 1)\n>           raise Exception('Failure: {0}'.format(count))\nE           Exception: Failure: 2\n\nconftest.py:7: Exception"},
                        'call': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': ''}
                    }, 
                    'original_trace': {
                        'teardown': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': ''},
                        'setup': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': "item = <Function 'test_pass'>\n\n    def pytest_runtest_setup(item):\n        import py\n        path = py.path.local(__file__).dirpath().ensure('test.res')\n        count = path.read() or 1\n        if int(count) <= 2:\n            path.write(int(count) + 1)\n>           raise Exception('Failure: {0}'.format(count))\nE           Exception: Failure: 1\n\nconftest.py:7: Exception"},
                        'call': {'caplog': '', 'capstderr': '', 'capstdout': '', 'text_repr': ''}
                    }
                }
            ]
        }

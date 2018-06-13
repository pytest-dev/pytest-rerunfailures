import json
import random
import time

try:
    import mock
except ImportError:
    from unittest import mock

import pytest

pytest_plugins = 'pytester'


def temporary_failure(count=1):
    return """import py
    path = py.path.local(__file__).dirpath().ensure('test.res')
    count = path.read() or 1
    if int(count) <= {0}:
        path.write(int(count) + 1)
        raise Exception('Failure: {{0}}'.format(count))""".format(count)


def assert_outcomes(result, passed=1, skipped=0, failed=0, error=0, xfailed=0,
                    xpassed=0, rerun=0):
    outcomes = result.parseoutcomes()
    assert outcomes.get('passed', 0) == passed
    assert outcomes.get('skipped', 0) == skipped
    assert outcomes.get('failed', 0) == failed
    assert outcomes.get('xfailed', 0) == xfailed
    assert outcomes.get('xpassed', 0) == xpassed
    assert outcomes.get('rerun', 0) == rerun


def test_error_when_run_with_pdb(testdir):
    testdir.makepyfile('def test_pass(): pass')
    result = testdir.runpytest('--reruns', '1', '--pdb')
    result.stderr.fnmatch_lines_random(
        'ERROR: --reruns incompatible with --pdb')


def test_no_rerun_on_pass(testdir):
    testdir.makepyfile('def test_pass(): pass')
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result)


def test_no_rerun_on_skipif_mark(testdir):
    reason = str(random.random())
    testdir.makepyfile("""
        import pytest
        @pytest.mark.skipif(reason='{0}')
        def test_skip():
            pass
    """.format(reason))
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=0, skipped=1)


def test_no_rerun_on_skip_call(testdir):
    reason = str(random.random())
    testdir.makepyfile("""
        import pytest
        def test_skip():
            pytest.skip('{0}')
    """.format(reason))
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=0, skipped=1)


def test_no_rerun_on_xfail_mark(testdir):
    reason = str(random.random())
    testdir.makepyfile("""
        import pytest
        @pytest.mark.xfail()
        def test_xfail():
            assert False
    """.format(reason))
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=0, xfailed=1)


def test_no_rerun_on_xfail_call(testdir):
    reason = str(random.random())
    testdir.makepyfile("""
        import pytest
        def test_xfail():
            pytest.xfail('{0}')
    """.format(reason))
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=0, xfailed=1)


def test_no_rerun_on_xpass(testdir):
    reason = str(random.random())
    testdir.makepyfile("""
        import pytest
        @pytest.mark.xfail()
        def test_xpass():
            pass
    """.format(reason))
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=0, xpassed=1)


def test_rerun_fails_after_consistent_setup_failure(testdir):
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            raise Exception('Setup failure')""")
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=0, error=1, rerun=1)


def test_rerun_passes_after_temporary_setup_failure(testdir):
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest("""
        def pytest_runtest_setup(item):
            {0}""".format(temporary_failure()))
    result = testdir.runpytest('--reruns', '1', '-r', 'R')
    assert_outcomes(result, passed=1, rerun=1)


def test_rerun_fails_after_consistent_test_failure(testdir):
    testdir.makepyfile('def test_fail(): assert False')
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=0, failed=1, rerun=1)


def test_rerun_passes_after_temporary_test_failure(testdir):
    testdir.makepyfile("""
        def test_pass():
            {0}""".format(temporary_failure()))
    result = testdir.runpytest('--reruns', '1', '-r', 'R')
    assert_outcomes(result, passed=1, rerun=1)


def test_rerun_passes_after_temporary_test_failure_with_flaky_mark(testdir):
    testdir.makepyfile("""
        import pytest
        @pytest.mark.flaky(reruns=2)
        def test_pass():
            {0}""".format(temporary_failure(2)))
    result = testdir.runpytest('-r', 'R')
    assert_outcomes(result, passed=1, rerun=2)


def test_reruns_if_flaky_mark_is_called_without_options(testdir):
    testdir.makepyfile("""
        import pytest
        @pytest.mark.flaky()
        def test_pass():
            {0}""".format(temporary_failure(1)))
    result = testdir.runpytest('-r', 'R')
    assert_outcomes(result, passed=1, rerun=1)


def test_reruns_if_flaky_mark_is_called_with_positional_argument(testdir):
    testdir.makepyfile("""
        import pytest
        @pytest.mark.flaky(2)
        def test_pass():
            {0}""".format(temporary_failure(2)))
    result = testdir.runpytest('-r', 'R')
    assert_outcomes(result, passed=1, rerun=2)


def test_no_extra_test_summary_for_reruns_by_default(testdir):
    testdir.makepyfile("""
        def test_pass():
            {0}""".format(temporary_failure()))
    result = testdir.runpytest('--reruns', '1')
    assert 'RERUN' not in result.stdout.str()
    assert '1 rerun' in result.stdout.str()


def test_extra_test_summary_for_reruns(testdir):
    testdir.makepyfile("""
        def test_pass():
            {0}""".format(temporary_failure()))
    result = testdir.runpytest('--reruns', '1', '-r', 'R')
    result.stdout.fnmatch_lines_random(['RERUN test_*:*'])
    assert '1 rerun' in result.stdout.str()


def test_verbose(testdir):
    testdir.makepyfile("""
        def test_pass():
            {0}""".format(temporary_failure()))
    result = testdir.runpytest('--reruns', '1', '-v')
    result.stdout.fnmatch_lines_random(['test_*:* RERUN*'])
    assert '1 rerun' in result.stdout.str()


def test_no_rerun_on_class_setup_error_without_reruns(testdir):
    testdir.makepyfile("""
        class TestFoo(object):
            @classmethod
            def setup_class(cls):
                assert False

            def test_pass():
                pass""")
    result = testdir.runpytest('--reruns', '0')
    assert_outcomes(result, passed=0, error=1, rerun=0)


def test_rerun_on_class_setup_error_with_reruns(testdir):
    testdir.makepyfile("""
        class TestFoo(object):
            @classmethod
            def setup_class(cls):
                assert False

            def test_pass():
                pass""")
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=0, error=1, rerun=1)


def test_rerun_with_resultslog(testdir):
    testdir.makepyfile("""
        def test_fail():
            assert False""")

    result = testdir.runpytest('--reruns', '2',
                               '--result-log', './pytest.log')

    assert_outcomes(result, passed=0, failed=1, rerun=2)


@pytest.mark.parametrize('delay_time', [-1, 0, 0.0, 1, 2.5])
def test_reruns_with_delay(testdir, delay_time):
    testdir.makepyfile("""
        def test_fail():
            assert False""")

    time.sleep = mock.MagicMock()

    result = testdir.runpytest('--reruns', '3',
                               '--reruns-delay', delay_time)

    if delay_time < 0:
        delay_time = 0

    time.sleep.assert_called_with(delay_time)

    assert_outcomes(result, passed=0, failed=1, rerun=3)


@pytest.mark.parametrize('delay_time', [-1, 0, 0.0, 1, 2.5])
def test_reruns_with_delay_marker(testdir, delay_time):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.flaky(reruns=2, reruns_delay={})
        def test_fail_two():
            assert False""".format(delay_time))

    time.sleep = mock.MagicMock()

    result = testdir.runpytest()

    if delay_time < 0:
        delay_time = 0

    time.sleep.assert_called_with(delay_time)

    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_reruns_with_artifact(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    testdir.makepyfile("""
        def test_pass():
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
                    'nodeid': 'test_reruns_with_artifact.py::test_pass',
                    'status': 'flake',
                    'rerun_trace': {
                        'teardown': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        },
                        'setup': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        }
                    },
                    'original_trace': {
                        'teardown': {
                            'caplog': None,
                            'capstderr': None,
                            'capstdout': None,
                            'text_repr': None
                        },
                        'setup': {
                            'caplog': None,
                            'capstderr': None,
                            'capstdout': None,
                            'text_repr': None
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': "def test_pass():\n        import py\n        path = py.path.local(__file__).dirpath().ensure('test.res')\n        count = path.read() or 1\n        if int(count) <= 1:\n            path.write(int(count) + 1)\n>           raise Exception('Failure: {0}'.format(count))\nE           Exception: Failure: 1\n\ntest_reruns_with_artifact.py:7: Exception"
                        }
                    }
                }
            ]
        }


def test_2_reruns_with_artifact(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    testdir.makepyfile("""
        def test_pass():
            {0}""".format(temporary_failure(2)))
    result = testdir.runpytest(
        '--reruns', '2', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=1, rerun=2)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        assert artifact_data == {
            'total_reruns': 2,
            'total_failed': 1,
            'total_resolved_by_reruns': 1,
            'rerun_tests': [
                {
                    'nodeid': 'test_2_reruns_with_artifact.py::test_pass',
                    'status': 'flake',
                    'rerun_trace': {
                        'teardown': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        },
                        'setup': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': "def test_pass():\n        import py\n        path = py.path.local(__file__).dirpath().ensure('test.res')\n        count = path.read() or 1\n        if int(count) <= 2:\n            path.write(int(count) + 1)\n>           raise Exception('Failure: {0}'.format(count))\nE           Exception: Failure: 2\n\ntest_2_reruns_with_artifact.py:7: Exception"
                        }
                    },
                    'original_trace': {
                        'teardown': {
                            'caplog': None,
                            'capstderr': None,
                            'capstdout': None,
                            'text_repr': None
                        },
                        'setup': {
                            'caplog': None,
                            'capstderr': None,
                            'capstdout': None,
                            'text_repr': None
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': "def test_pass():\n        import py\n        path = py.path.local(__file__).dirpath().ensure('test.res')\n        count = path.read() or 1\n        if int(count) <= 2:\n            path.write(int(count) + 1)\n>           raise Exception('Failure: {0}'.format(count))\nE           Exception: Failure: 1\n\ntest_2_reruns_with_artifact.py:7: Exception"
                        }
                    }
                },
                {
                    'nodeid': 'test_2_reruns_with_artifact.py::test_pass',
                    'status': 'flake',
                    'rerun_trace': {
                        'teardown': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        },
                        'setup': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        }
                    },
                    'original_trace': {
                        'teardown': {
                            'caplog': None,
                            'capstderr': None,
                            'capstdout': None,
                            'text_repr': None
                        },
                        'setup': {
                            'caplog': None,
                            'capstderr': None,
                            'capstdout': None,
                            'text_repr': None
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': "def test_pass():\n        import py\n        path = py.path.local(__file__).dirpath().ensure('test.res')\n        count = path.read() or 1\n        if int(count) <= 2:\n            path.write(int(count) + 1)\n>           raise Exception('Failure: {0}'.format(count))\nE           Exception: Failure: 1\n\ntest_2_reruns_with_artifact.py:7: Exception"
                        }
                    }
                }
            ]
        }

def test_uncuccess_reruns_with_artifact(testdir):
    artifact_path = testdir.tmpdir.strpath + '/artifact.json'
    testdir.makepyfile("""
        def test_pass():
            {0}""".format(temporary_failure(2)))
    result = testdir.runpytest(
        '--reruns', '1', '-r', 'R',
        '--reruns-artifact-path', artifact_path,
    )
    assert_outcomes(result, passed=0, failed=1, rerun=1)
    with open(artifact_path) as artifact:
        artifact_data = json.load(artifact)
        print artifact_data['rerun_tests'][0]['original_trace']['call']
        assert artifact_data == {
            'total_reruns': 1,
            'total_failed': 1,
            'total_resolved_by_reruns': 0,
            'rerun_tests': [
                {
                    'nodeid': 'test_uncuccess_reruns_with_artifact.py::test_pass',
                    'status': 'failed',
                    'rerun_trace': {
                        'teardown': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        },
                        'setup': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': ''
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': "def test_pass():\n        import py\n        path = py.path.local(__file__).dirpath().ensure('test.res')\n        count = path.read() or 1\n        if int(count) <= 2:\n            path.write(int(count) + 1)\n>           raise Exception('Failure: {0}'.format(count))\nE           Exception: Failure: 2\n\ntest_uncuccess_reruns_with_artifact.py:7: Exception"
                        }
                    },
                    'original_trace': {
                        'teardown': {
                            'caplog': None,
                            'capstderr': None,
                            'capstdout': None,
                            'text_repr': None
                        },
                        'setup': {
                            'caplog': None,
                            'capstderr': None,
                            'capstdout': None,
                            'text_repr': None
                        },
                        'call': {
                            'caplog': '',
                            'capstderr': '',
                            'capstdout': '',
                            'text_repr': "def test_pass():\n        import py\n        path = py.path.local(__file__).dirpath().ensure('test.res')\n        count = path.read() or 1\n        if int(count) <= 2:\n            path.write(int(count) + 1)\n>           raise Exception('Failure: {0}'.format(count))\nE           Exception: Failure: 1\n\ntest_uncuccess_reruns_with_artifact.py:7: Exception"
                        }
                    }
                }
            ]
        }

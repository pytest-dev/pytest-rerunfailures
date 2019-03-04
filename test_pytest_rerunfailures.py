import random
import time

try:
    from unittest import mock
except ImportError:
    import mock

import pytest

pytest_plugins = 'pytester'


def temporary_failure(count=1):
    return """
            import py
            path = py.path.local(__file__).dirpath().ensure('test.res')
            count = path.read() or 1
            if int(count) <= {0}:
                path.write(int(count) + 1)
                raise Exception('Failure: {{0}}'.format(count))""".format(
        count)


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
                               '--reruns-delay', str(delay_time))

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


def test_rerun_on_setup_class_with_error_with_reruns(testdir):
    """
     Case: setup_class throwing error on the first execution for parametrized test
    """
    testdir.makepyfile("""
        import pytest

        pass_fixture = False

        class TestFoo(object):
            @classmethod
            def setup_class(cls):
                global pass_fixture
                if not pass_fixture:
                    pass_fixture = True
                    assert False
                assert True
            @pytest.mark.parametrize('param', [1, 2, 3])
            def test_pass(self, param):
                assert param""")
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=3, rerun=1)


def test_rerun_on_class_scope_fixture_with_error_with_reruns(testdir):
    """
    Case: Class scope fixture throwing error on the first execution for parametrized test
    """
    testdir.makepyfile("""
        import pytest

        pass_fixture = False

        class TestFoo(object):

            @pytest.fixture(scope="class")
            def setup_fixture(self):
                global pass_fixture
                if not pass_fixture:
                    pass_fixture = True
                    assert False
                assert True
            @pytest.mark.parametrize('param', [1, 2, 3])
            def test_pass(self, setup_fixture, param):
                assert param""")
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=3, rerun=1)


def test_rerun_on_module_fixture_with_reruns(testdir):
    """
    Case: Module scope fixture is not re-executed when class scope fixture throwing error on the first execution
    for parametrized test
    """
    testdir.makepyfile("""
        import pytest

        pass_fixture = False

        @pytest.fixture(scope='module')
        def module_fixture():
            assert not pass_fixture

        class TestFoo(object):
            @pytest.fixture(scope="class")
            def setup_fixture(self):
                global pass_fixture
                if not pass_fixture:
                    pass_fixture = True
                    assert False
                assert True
            def test_pass_1(self, module_fixture, setup_fixture):
                assert True

            def test_pass_2(self, module_fixture, setup_fixture):
                assert True""")
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=2, rerun=1)


def test_rerun_on_session_fixture_with_reruns(testdir):
    """
    Case: Module scope fixture is not re-executed when class scope fixture throwing error on the first execution
    for parametrized test
    """
    testdir.makepyfile("""
        import pytest

        pass_fixture = False

        @pytest.fixture(scope='session')
        def session_fixture():
            assert not pass_fixture

        class TestFoo(object):
            @pytest.fixture(scope="class")
            def setup_fixture(self):
                global pass_fixture
                if not pass_fixture:
                    pass_fixture = True
                    assert False
                assert True

            def test_pass_1(self, session_fixture, setup_fixture):
                assert True
            def test_pass_2(self, session_fixture, setup_fixture):
                assert True""")
    result = testdir.runpytest('--reruns', '1')
    assert_outcomes(result, passed=2, rerun=1)


def test_execution_count_exposed(testdir):
    testdir.makepyfile('def test_pass(): assert True')
    testdir.makeconftest("""
        def pytest_runtest_teardown(item):
            assert item.execution_count == 3""")
    result = testdir.runpytest('--reruns', '2')
    assert_outcomes(result, passed=3, rerun=2)


def test_rerun_report(testdir):
    testdir.makepyfile('def test_pass(): assert False')
    testdir.makeconftest("""
        def pytest_runtest_logreport(report):
            assert hasattr(report, 'rerun')
            assert isinstance(report.rerun, int)
            assert report.rerun <= 2
        """)
    result = testdir.runpytest('--reruns', '2')
    assert_outcomes(result, failed=1, rerun=2, passed=0)


def test_pytest_runtest_logfinish_is_called(testdir):
    hook_message = "Message from pytest_runtest_logfinish hook"
    testdir.makepyfile('def test_pass(): pass')
    testdir.makeconftest(r"""
        def pytest_runtest_logfinish(nodeid, location):
            print("\n{0}\n")
    """.format(hook_message))
    result = testdir.runpytest('--reruns', '1', '-s')
    result.stdout.fnmatch_lines(hook_message)

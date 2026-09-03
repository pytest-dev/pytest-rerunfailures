import random
import time
from textwrap import indent
from types import SimpleNamespace
from unittest import mock

import pytest

from pytest_rerunfailures import (
    HAS_PYTEST_HANDLECRASHITEM,
    ServerStatusDB,
    SocketDB,
    StatusDB,
    SubtestReport,
    XDistHooks,
)

pytest_plugins = "pytester"

has_xdist = HAS_PYTEST_HANDLECRASHITEM
has_subtests = SubtestReport is not None


def temporary_failure(count=1):
    return f"""
            import py
            path = py.path.local(__file__).dirpath().ensure('test.res')
            count = path.read() or 1
            if int(count) <= {count}:
                path.write(int(count) + 1)
                raise Exception('Failure: {{0}}'.format(count))"""


def temporary_crash(count=1):
    return f"""
            import py
            import os
            path = py.path.local(__file__).dirpath().ensure('test.res')
            count = path.read() or 1
            if int(count) <= {count}:
                path.write(int(count) + 1)
                os._exit(1)"""


def check_outcome_field(outcomes, field_name, expected_value):
    field_value = outcomes.get(field_name, 0)
    assert field_value == expected_value, (
        f"outcomes.{field_name} has unexpected value. "
        f"Expected '{expected_value}' but got '{field_value}'"
    )


def assert_outcomes(
    result,
    passed=1,
    skipped=0,
    failed=0,
    error=0,
    xfailed=0,
    xpassed=0,
    rerun=0,
):
    outcomes = result.parseoutcomes()
    check_outcome_field(outcomes, "passed", passed)
    check_outcome_field(outcomes, "skipped", skipped)
    check_outcome_field(outcomes, "failed", failed)
    field = "errors"
    check_outcome_field(outcomes, field, error)
    check_outcome_field(outcomes, "xfailed", xfailed)
    check_outcome_field(outcomes, "xpassed", xpassed)
    check_outcome_field(outcomes, "rerun", rerun)


def test_error_when_run_with_pdb(testdir):
    testdir.makepyfile("def test_pass(): pass")
    result = testdir.runpytest("--reruns", "1", "--pdb")
    result.stderr.fnmatch_lines_random("ERROR: --reruns incompatible with --pdb")


def test_no_error_when_run_with_pdb_without_reruns(testdir):
    testdir.makepyfile("def test_pass(): pass")
    result = testdir.runpytest("--pdb")
    assert_outcomes(result)


def test_no_error_when_run_with_pdb_and_zero_reruns(testdir):
    testdir.makepyfile("def test_pass(): pass")
    result = testdir.runpytest("--reruns", "0", "--pdb")
    assert_outcomes(result)


def test_error_when_run_with_pdb_and_reruns_ini(testdir):
    testdir.makepyfile("def test_pass(): pass")
    testdir.makeini("[pytest]\nreruns = 1\n")
    result = testdir.runpytest("--pdb")
    result.stderr.fnmatch_lines_random("ERROR: --reruns incompatible with --pdb")


def test_error_when_run_with_pdb_and_force_reruns(testdir):
    testdir.makepyfile("def test_pass(): pass")
    result = testdir.runpytest("--force-reruns", "1", "--pdb")
    result.stderr.fnmatch_lines_random("ERROR: --reruns incompatible with --pdb")


def test_error_when_run_with_pdb_and_flaky_marker(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.flaky(reruns=1)
        def test_pass(): pass
        """
    )
    result = testdir.runpytest("--pdb")
    result.stderr.fnmatch_lines_random("*--reruns incompatible with --pdb")


def test_no_rerun_on_pass(testdir):
    testdir.makepyfile("def test_pass(): pass")
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result)


def test_no_rerun_on_skipif_mark(testdir):
    reason = str(random.random())
    testdir.makepyfile(
        f"""
        import pytest
        @pytest.mark.skipif(reason='{reason}')
        def test_skip():
            pass
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, skipped=1)


def test_no_rerun_on_skip_call(testdir):
    reason = str(random.random())
    testdir.makepyfile(
        f"""
        import pytest
        def test_skip():
            pytest.skip('{reason}')
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, skipped=1)


def test_no_rerun_on_xfail_mark(testdir):
    testdir.makepyfile(
        """
        import pytest
        @pytest.mark.xfail()
        def test_xfail():
            assert False
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, xfailed=1)


def test_no_rerun_on_xfail_call(testdir):
    reason = str(random.random())
    testdir.makepyfile(
        f"""
        import pytest
        def test_xfail():
            pytest.xfail('{reason}')
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, xfailed=1)


def test_no_rerun_on_xpass(testdir):
    testdir.makepyfile(
        """
        import pytest
        @pytest.mark.xfail()
        def test_xpass():
            pass
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, xpassed=1)


def test_rerun_fails_after_consistent_setup_failure(testdir):
    testdir.makepyfile("def test_pass(): pass")
    testdir.makeconftest(
        """
        def pytest_runtest_setup(item):
            raise Exception('Setup failure')"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, error=1, rerun=1)


def test_rerun_passes_after_temporary_setup_failure(testdir):
    testdir.makepyfile("def test_pass(): pass")
    testdir.makeconftest(
        f"""
        def pytest_runtest_setup(item):
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "-r", "R")
    assert_outcomes(result, passed=1, rerun=1)


def test_rerun_fails_after_consistent_test_failure(testdir):
    testdir.makepyfile("def test_fail(): assert False")
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, failed=1, rerun=1)


def test_rerun_passes_after_temporary_test_failure(testdir):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "-r", "R")
    assert_outcomes(result, passed=1, rerun=1)


def test_run_with_fail_on_flaky_fails_with_custom_error_code_after_pass_on_rerun(
    testdir,
):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "--fail-on-flaky")
    assert_outcomes(result, passed=1, rerun=1)
    assert result.ret == 7


def test_run_fails_with_code_1_after_consistent_test_failure_even_with_fail_on_flaky(
    testdir,
):
    testdir.makepyfile("def test_fail(): assert False")
    result = testdir.runpytest("--reruns", "1", "--fail-on-flaky")
    assert_outcomes(result, passed=0, failed=1, rerun=1)
    assert result.ret == 1


def test_run_mark_and_fail_on_flaky_fails_with_custom_error_code_after_pass_on_rerun(
    testdir,
):
    testdir.makepyfile(f"""
        import pytest

        @pytest.mark.flaky(reruns=1)
        def test_fail():
            {temporary_failure()}
    """)
    result = testdir.runpytest("--fail-on-flaky")
    assert_outcomes(result, passed=1, rerun=1)
    assert result.ret == 7


def test_run_fails_with_code_1_after_test_failure_with_fail_on_flaky_and_mark(
    testdir,
):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.flaky(reruns=2)
        def test_fail():
            assert False
    """)
    result = testdir.runpytest("--fail-on-flaky")
    assert_outcomes(result, passed=0, failed=1, rerun=2)
    assert result.ret == 1


def test_run_with_mark_and_fail_on_flaky_succeeds_if_all_tests_pass_without_reruns(
    testdir,
):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.flaky(reruns=2)
        def test_marked_pass():
            assert True

        def test_unmarked_pass():
            assert True
    """)
    result = testdir.runpytest("--fail-on-flaky")
    assert_outcomes(result, passed=2, rerun=0)
    assert result.ret == pytest.ExitCode.OK


def test_run_with_fail_on_flaky_succeeds_if_all_tests_pass_without_reruns(
    testdir,
):
    testdir.makepyfile("def test_pass(): assert True")
    result = testdir.runpytest("--reruns", "1", "--fail-on-flaky")
    assert_outcomes(result, passed=1, rerun=0)
    assert result.ret == pytest.ExitCode.OK


@pytest.mark.skipif(not has_xdist, reason="requires xdist with crashitem")
def test_rerun_passes_after_temporary_test_crash(testdir):
    # note: we need two tests because there is a bug where xdist
    # cannot rerun the last test if it crashes. the bug exists only
    # in xdist is there is no error that causes the bug in this plugin.
    testdir.makepyfile(
        f"""
        def test_crash():
            {temporary_crash()}

        def test_pass():
            pass"""
    )
    result = testdir.runpytest("-p", "xdist", "-n", "1", "--reruns", "1", "-r", "R")
    assert_outcomes(result, passed=2, rerun=1)


@pytest.mark.skipif(not has_xdist, reason="requires xdist with crashitem")
def test_max_suite_reruns_caps_temporary_test_crash(testdir):
    testdir.makepyfile(
        f"""
        def test_crash():
            {temporary_crash(2)}

        def test_pass():
            pass
        """
    )
    result = testdir.runpytest(
        "-p",
        "xdist",
        "-n",
        "1",
        "--reruns",
        "3",
        "--max-suite-reruns",
        "1",
    )
    assert result.ret != pytest.ExitCode.OK
    check_outcome_field(result.parseoutcomes(), "rerun", 1)


def test_xdist_crash_rerun_releases_cap_when_scheduler_rejects():
    db = StatusDB()
    db.get_test_reruns = lambda _: 1
    db.get_test_failures = lambda _: 0

    def mark_test_pending(_):
        raise NotImplementedError

    sched = SimpleNamespace(
        config=SimpleNamespace(
            failures_db=db,
            option=SimpleNamespace(max_suite_reruns=1),
        ),
        mark_test_pending=mark_test_pending,
    )
    report = SimpleNamespace(outcome="failed", longrepr=None)

    XDistHooks().pytest_handlecrashitem("test_crash", report, sched)

    assert report.outcome == "failed"
    assert db.get_suite_reruns() == 0


def test_sock_recv_raises_connection_error_on_eof():
    db = SocketDB.__new__(SocketDB)
    StatusDB.__init__(db)
    connection = mock.MagicMock()
    connection.recv.side_effect = [
        b"",
        AssertionError("recv called again after EOF"),
    ]

    with pytest.raises(
        ConnectionError, match="StatusDB connection closed unexpectedly"
    ):
        db._sock_recv(connection)

    connection.recv.assert_called_once_with(1)


@pytest.mark.parametrize(
    "authentication",
    [
        pytest.param(b"invalid-token", id="incorrect-token"),
        pytest.param(b"\xff", id="invalid-utf8"),
        pytest.param("é".encode(), id="non-ascii"),
    ],
)
def test_statusdb_rejects_unauthenticated_commands(authentication):
    server = ServerStatusDB.__new__(ServerStatusDB)
    StatusDB.__init__(server)
    server.rerunfailures_db = {}
    server.token = str(mock.sentinel.statusdb_token)
    server._set("test", "r", 1)

    connection = mock.MagicMock()
    wire_data = authentication + b"\nset|test|r|2\n"
    connection.recv.side_effect = [bytes((byte,)) for byte in wire_data]

    server.run_connection(connection)

    connection.send.assert_called_once_with(b"0\n")
    assert server._get("test", "r") == 1


def test_statusdb_accepts_64_byte_authentication_token():
    server = ServerStatusDB.__new__(ServerStatusDB)
    StatusDB.__init__(server)
    server.rerunfailures_db = {}
    server.token = "a" * 64

    connection = mock.MagicMock()
    wire_data = server.token.encode() + b"\nset|test|r|1\n"
    connection.recv.side_effect = [bytes((byte,)) for byte in wire_data] + [b""]

    server.run_connection(connection)

    connection.send.assert_called_once_with(b"1\n")
    assert server._get("test", "r") == 1


def test_statusdb_rejects_oversized_authentication():
    server = ServerStatusDB.__new__(ServerStatusDB)
    StatusDB.__init__(server)
    server.rerunfailures_db = {}
    server.token = "a" * 64
    server._set("test", "r", 1)

    connection = mock.MagicMock()
    oversized_authentication = server.token.encode() + b"x"
    wire_data = oversized_authentication + b"\nset|test|r|2\n"
    connection.recv.side_effect = [bytes((byte,)) for byte in wire_data]

    server.run_connection(connection)

    connection.send.assert_called_once_with(b"0\n")
    assert connection.recv.call_count == 65
    assert server._get("test", "r") == 1


def test_xdist_configure_node_passes_statusdb_connection_details():
    failures_db = SimpleNamespace(sock_port=12345, token=mock.sentinel.statusdb_token)
    node = SimpleNamespace(
        config=SimpleNamespace(failures_db=failures_db), workerinput={}
    )

    XDistHooks().pytest_configure_node(node)

    assert node.workerinput == {
        "sock_port": 12345,
        "statusdb_token": mock.sentinel.statusdb_token,
    }


def test_rerun_passes_after_temporary_test_failure_with_flaky_mark(testdir):
    testdir.makepyfile(
        f"""
        import pytest
        @pytest.mark.flaky(reruns=2)
        def test_pass():
            {temporary_failure(2)}"""
    )
    result = testdir.runpytest("-r", "R")
    assert_outcomes(result, passed=1, rerun=2)


def test_reruns_if_flaky_mark_is_called_without_options(testdir):
    testdir.makepyfile(
        f"""
        import pytest
        @pytest.mark.flaky()
        def test_pass():
            {temporary_failure(1)}"""
    )
    result = testdir.runpytest("-r", "R")
    assert_outcomes(result, passed=1, rerun=1)


def test_reruns_if_flaky_mark_is_called_with_positional_argument(testdir):
    testdir.makepyfile(
        f"""
        import pytest
        @pytest.mark.flaky(2)
        def test_pass():
            {temporary_failure(2)}"""
    )
    result = testdir.runpytest("-r", "R")
    assert_outcomes(result, passed=1, rerun=2)


def test_no_extra_test_summary_for_reruns_by_default(testdir):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert "RERUN" not in result.stdout.str()
    assert "1 rerun" in result.stdout.str()


def test_extra_test_summary_for_reruns(testdir):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "-r", "R")
    result.stdout.fnmatch_lines_random(["RERUN test_*:*"])
    assert "1 rerun" in result.stdout.str()


def test_rerun_show_tracebacks_for_eventual_pass(testdir):
    testdir.makepyfile(
        f"""
        def test_eventually_passes():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "--rerun-show-tracebacks")
    assert result.ret == 0
    stdout = result.stdout.str()
    assert "rerun test summary info" in stdout
    assert "RERUN test_rerun_show_tracebacks_for_eventual_pass" in stdout
    assert "Exception: Failure: 1" in stdout
    assert "1 passed" in stdout
    assert "1 rerun" in stdout


def test_rerun_show_tracebacks_off_by_default(testdir):
    testdir.makepyfile(
        f"""
        def test_eventually_passes():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1")
    stdout = result.stdout.str()
    assert "rerun test summary info" not in stdout
    assert "Exception: Failure" not in stdout


def test_rerun_show_tracebacks_with_reportchars(testdir):
    testdir.makepyfile(
        f"""
        def test_eventually_passes():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "--rerun-show-tracebacks", "-rR")
    stdout = result.stdout.str()
    # Only one rerun summary section, not duplicated by the -rR path.
    assert stdout.count("rerun test summary info") == 1
    assert "Exception: Failure: 1" in stdout


def test_verbose(testdir):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "-v")
    result.stdout.fnmatch_lines_random(["test_*:* RERUN*"])
    assert "1 rerun" in result.stdout.str()


def test_no_rerun_on_class_setup_error_without_reruns(testdir):
    testdir.makepyfile(
        """
        class TestFoo(object):
            @classmethod
            def setup_class(cls):
                assert False

            def test_pass():
                pass"""
    )
    result = testdir.runpytest("--reruns", "0")
    assert_outcomes(result, passed=0, error=1, rerun=0)


def test_rerun_on_class_setup_error_with_reruns(testdir):
    testdir.makepyfile(
        """
        class TestFoo(object):
            @classmethod
            def setup_class(cls):
                assert False

            def test_pass():
                pass"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, error=1, rerun=1)


@pytest.mark.parametrize("delay_time", [-1, 0, 0.0, 1, 2.5])
def test_reruns_with_delay(testdir, delay_time):
    testdir.makepyfile(
        """
        def test_fail():
            assert False"""
    )

    time.sleep = mock.MagicMock()

    result = testdir.runpytest("--reruns", "3", "--reruns-delay", str(delay_time))

    if delay_time < 0:
        result.stdout.fnmatch_lines(
            "*UserWarning: Delay time between re-runs cannot be < 0. "
            "Using default value: 0"
        )
        delay_time = 0

    time.sleep.assert_called_with(delay_time)

    assert_outcomes(result, passed=0, failed=1, rerun=3)


@pytest.mark.parametrize("delay_time", [-1, 0, 0.0, 1, 2.5])
def test_reruns_with_delay_marker(testdir, delay_time):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.flaky(reruns=2, reruns_delay={delay_time})
        def test_fail_two():
            assert False"""
    )

    time.sleep = mock.MagicMock()

    result = testdir.runpytest()

    if delay_time < 0:
        result.stdout.fnmatch_lines(
            "*UserWarning: Delay time between re-runs cannot be < 0. "
            "Using default value: 0"
        )
        delay_time = 0

    time.sleep.assert_called_with(delay_time)

    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_reruns_with_delay_backoff_factor(testdir):
    testdir.makepyfile(
        """
        def test_fail():
            assert False"""
    )

    time.sleep = mock.MagicMock()

    result = testdir.runpytest(
        "--reruns",
        "3",
        "--reruns-delay",
        "1",
        "--reruns-delay-backoff-factor",
        "2",
    )

    # delay * factor ** (attempt - 1) -> 1, 2, 4
    assert time.sleep.call_args_list == [mock.call(1), mock.call(2), mock.call(4)]

    assert_outcomes(result, passed=0, failed=1, rerun=3)


def test_reruns_with_delay_backoff_factor_marker(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.flaky(reruns=3, reruns_delay=1, reruns_delay_backoff_factor=2)
        def test_fail():
            assert False"""
    )

    time.sleep = mock.MagicMock()

    result = testdir.runpytest()

    assert time.sleep.call_args_list == [mock.call(1), mock.call(2), mock.call(4)]

    assert_outcomes(result, passed=0, failed=1, rerun=3)


def test_reruns_with_delay_backoff_factor_marker_positional(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.flaky(3, 1, 2)
        def test_fail():
            assert False"""
    )

    time.sleep = mock.MagicMock()

    result = testdir.runpytest()

    assert time.sleep.call_args_list == [mock.call(1), mock.call(2), mock.call(4)]

    assert_outcomes(result, passed=0, failed=1, rerun=3)


def test_reruns_with_negative_delay_backoff_factor(testdir):
    testdir.makepyfile(
        """
        def test_fail():
            assert False"""
    )

    time.sleep = mock.MagicMock()

    result = testdir.runpytest(
        "--reruns",
        "2",
        "--reruns-delay",
        "1",
        "--reruns-delay-backoff-factor",
        "-1",
    )

    result.stdout.fnmatch_lines(
        "*UserWarning: Rerun delay backoff factor cannot be < 0. "
        "Using default value: 1.0"
    )

    # factor falls back to 1.0 -> constant delay of 1
    assert time.sleep.call_args_list == [mock.call(1), mock.call(1)]

    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_rerun_on_setup_class_with_error_with_reruns(testdir):
    """
    Case: setup_class throwing error on the first execution for parametrized test
    """
    testdir.makepyfile(
        """
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
                assert param"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=3, rerun=1)


def test_rerun_on_class_scope_fixture_with_error_with_reruns(testdir):
    """
    Case: Class scope fixture throwing error on the first execution
    for parametrized test
    """
    testdir.makepyfile(
        """
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
                assert param"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=3, rerun=1)


def test_rerun_on_module_fixture_with_reruns(testdir):
    """
    Case: Module scope fixture is not re-executed when class scope fixture throwing
    error on the first execution for parametrized test
    """
    testdir.makepyfile(
        """
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
                assert True"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=2, rerun=1)


def test_rerun_on_session_fixture_with_reruns(testdir):
    """
    Case: Module scope fixture is not re-executed when class scope fixture
    throwing error on the first execution for parametrized test
    """
    testdir.makepyfile(
        """
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
                assert True"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=2, rerun=1)


def test_rerun_recreates_test_class_instance(testdir):
    """
    Case: state stored on ``self`` by a failed attempt must not leak into the
    rerun, i.e. every attempt gets a fresh test class instance
    """
    testdir.makepyfile(
        """
        import pytest

        attempts = 0

        class TestFoo(object):
            @pytest.fixture(autouse=True)
            def counting_fixture(self):
                assert not hasattr(self, 'seen_by_fixture')
                self.seen_by_fixture = True

            @pytest.mark.flaky(reruns=2)
            def test_fresh_instance(self):
                global attempts
                attempts += 1
                assert not hasattr(self, 'seen_by_test')
                self.seen_by_test = True
                assert attempts == 3"""
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=1, rerun=2)


def test_rerun_recreates_instance_without_re_executing_scoped_fixtures(testdir):
    """
    Case: recreating the test class instance for a rerun must not invalidate
    fixtures cached at a higher scope than function
    """
    testdir.makepyfile(
        """
        import pytest

        attempts = 0
        executions = {'session': 0, 'module': 0, 'class': 0}

        @pytest.fixture(scope='session')
        def session_fixture():
            executions['session'] += 1

        @pytest.fixture(scope='module')
        def module_fixture():
            executions['module'] += 1

        @pytest.fixture(scope='class')
        def class_fixture():
            executions['class'] += 1

        class TestFoo(object):
            @pytest.mark.flaky(reruns=2)
            def test_fresh_instance(
                self, session_fixture, module_fixture, class_fixture
            ):
                global attempts
                attempts += 1
                assert executions == {'session': 1, 'module': 1, 'class': 1}
                assert not hasattr(self, 'seen_by_test')
                self.seen_by_test = True
                assert attempts == 3"""
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=1, rerun=2)


def test_execution_count_exposed(testdir):
    testdir.makepyfile("def test_pass(): assert True")
    testdir.makeconftest(
        """
        def pytest_runtest_teardown(item):
            assert item.execution_count == 3"""
    )
    result = testdir.runpytest("--reruns", "2")
    assert_outcomes(result, passed=3, rerun=2)


def test_rerun_report(testdir):
    testdir.makepyfile("def test_pass(): assert False")
    testdir.makeconftest(
        """
        def pytest_runtest_logreport(report):
            assert hasattr(report, 'rerun')
            assert isinstance(report.rerun, int)
            assert report.rerun <= 2
        """
    )
    result = testdir.runpytest("--reruns", "2")
    assert_outcomes(result, failed=1, rerun=2, passed=0)


def test_rerun_report_includes_teardown_from_each_attempt(testdir):
    testdir.makepyfile("def test_fail(): assert False")
    testdir.makeconftest(
        """
        reports = []

        def pytest_runtest_logreport(report):
            reports.append((report.when, report.outcome, report.rerun))

        def pytest_sessionfinish():
            print(f"REPORTS: {reports!r}")
        """
    )

    result = testdir.runpytest("--reruns", "1")

    assert_outcomes(result, failed=1, rerun=1, passed=0)
    expected_reports = (
        "REPORTS: [('setup', 'passed', 0), ('call', 'rerun', 0), "
        "('teardown', 'passed', 0), ('setup', 'passed', 1), "
        "('call', 'failed', 1), ('teardown', 'passed', 1)]"
    )
    assert expected_reports in result.stdout.str()


def test_single_attempt_triggers_at_most_one_rerun(testdir):
    testdir.makepyfile("def test_fail(failing_teardown): assert False")
    testdir.makeconftest(
        """
        import pytest

        attempts = 0
        first_attempt_reports = []

        @pytest.fixture
        def failing_teardown():
            global attempts
            attempts += 1
            yield
            raise RuntimeError("teardown failure")

        def pytest_runtest_logreport(report):
            if report.rerun == 0 and report.when in ("call", "teardown"):
                first_attempt_reports.append((report.when, report.outcome))

        def pytest_sessionfinish():
            print(f"ATTEMPTS: {attempts}")
            print(f"FIRST ATTEMPT REPORTS: {first_attempt_reports!r}")
        """
    )

    result = testdir.runpytest("--reruns", "1")

    stdout = result.stdout.str()
    assert "ATTEMPTS: 2" in stdout
    assert (
        "FIRST ATTEMPT REPORTS: [('call', 'rerun'), ('teardown', 'failed')]" in stdout
    )


def test_pytest_runtest_logfinish_is_called(testdir):
    hook_message = "Message from pytest_runtest_logfinish hook"
    testdir.makepyfile("def test_pass(): pass")
    testdir.makeconftest(
        rf"""
        def pytest_runtest_logfinish(nodeid, location):
            print("\n{hook_message}\n")
    """
    )
    result = testdir.runpytest("--reruns", "1", "-s")
    result.stdout.fnmatch_lines(hook_message)


@pytest.mark.parametrize(
    "only_rerun_texts, should_rerun",
    [
        (["AssertionError"], True),
        (["Assertion*"], True),
        (["Assertion"], True),
        (["ValueError"], False),
        ([""], True),
        (["AssertionError: "], True),
        (["AssertionError: ERR"], True),
        (["ERR"], True),
        (["AssertionError,ValueError"], False),
        (["AssertionError ValueError"], False),
        (["AssertionError", "ValueError"], True),
    ],
)
def test_only_rerun_flag(testdir, only_rerun_texts, should_rerun):
    testdir.makepyfile("""
        def test_only_rerun1():
            raise AssertionError("ERR")

        def test_only_rerun2():
            assert False, "ERR"
    """)

    num_failed = 2
    num_passed = 0
    num_reruns = 2
    num_reruns_actual = num_reruns * 2 if should_rerun else 0

    pytest_args = ["--reruns", str(num_reruns)]
    for only_rerun_text in only_rerun_texts:
        pytest_args.extend(["--only-rerun", only_rerun_text])
    result = testdir.runpytest(*pytest_args)
    assert_outcomes(
        result, passed=num_passed, failed=num_failed, rerun=num_reruns_actual
    )


def test_no_rerun_on_strict_xfail_with_only_rerun_flag(testdir):
    testdir.makepyfile(
        """
        import pytest
        @pytest.mark.xfail(strict=True)
        def test_xfail():
            assert True
    """
    )
    result = testdir.runpytest("--reruns", "1", "--only-rerun", "RuntimeError")
    assert_outcomes(result, passed=0, failed=1, rerun=0)


@pytest.mark.parametrize(
    "rerun_except_texts, should_rerun",
    [
        (["AssertionError"], True),
        (["Assertion*"], True),
        (["Assertion"], True),
        (["ValueError"], False),
        (["AssertionError: "], True),
        (["ERR"], False),
        (["AssertionError", "OSError"], True),
        (["ValueError", "OSError"], False),
    ],
)
def test_rerun_except_flag(testdir, rerun_except_texts, should_rerun):
    testdir.makepyfile('def test_rerun_except(): raise ValueError("ERR")')

    num_failed = 1
    num_passed = 0
    num_reruns = 1
    num_reruns_actual = num_reruns if should_rerun else 0

    pytest_args = ["--reruns", str(num_reruns)]
    for rerun_except_text in rerun_except_texts:
        pytest_args.extend(["--rerun-except", rerun_except_text])
    result = testdir.runpytest(*pytest_args)
    assert_outcomes(
        result, passed=num_passed, failed=num_failed, rerun=num_reruns_actual
    )


def test_rerun_exclude_path_prevents_reruns_in_directory(testdir):
    testdir.makeconftest(
        """
        from pathlib import Path

        def pytest_runtest_call(item):
            with Path("executions").open("a") as execution_log:
                execution_log.write(item.name + "\\n")
    """
    )
    testdir.makepyfile(
        test_normal="""
        def test_normal_failure():
            assert False
    """
    )
    excluded_dir = testdir.mkdir("excluded")
    excluded_dir.join("test_excluded.py").write(
        """
def test_excluded_failure():
    assert False
"""
    )

    result = testdir.runpytest("--reruns", "2", "--rerun-exclude-path", "excluded")

    assert_outcomes(result, passed=0, failed=2, rerun=2)
    executions = testdir.tmpdir.join("executions").read().splitlines()
    assert executions.count("test_normal_failure") == 3
    assert executions.count("test_excluded_failure") == 1


def test_rerun_exclude_path_prevents_reruns_for_file(testdir):
    testdir.makeconftest(
        """
        from pathlib import Path

        def pytest_runtest_call(item):
            with Path("executions").open("a") as execution_log:
                execution_log.write(item.name + "\\n")
    """
    )
    testdir.makepyfile(
        test_normal="""
        def test_normal_failure():
            assert False
    """
    )
    excluded_dir = testdir.mkdir("excluded")
    excluded_dir.join("test_excluded.py").write(
        """
def test_excluded_failure():
    assert False
"""
    )

    result = testdir.runpytest(
        "--reruns",
        "2",
        "--rerun-exclude-path",
        "excluded/test_excluded.py",
    )

    assert_outcomes(result, passed=0, failed=2, rerun=2)
    executions = testdir.tmpdir.join("executions").read().splitlines()
    assert executions.count("test_normal_failure") == 3
    assert executions.count("test_excluded_failure") == 1


def test_rerun_exclude_path_accepts_multiple_paths(testdir):
    testdir.makeconftest(
        """
        from pathlib import Path

        def pytest_runtest_call(item):
            with Path("executions").open("a") as execution_log:
                execution_log.write(item.name + "\\n")
    """
    )
    testdir.makepyfile(
        test_normal="""
        def test_normal_failure():
            assert False
    """
    )
    excluded_a_dir = testdir.mkdir("excluded_a")
    excluded_a_dir.join("test_excluded_a.py").write(
        """
def test_excluded_a_failure():
    assert False
"""
    )
    excluded_b_dir = testdir.mkdir("excluded_b")
    excluded_b_dir.join("test_excluded_b.py").write(
        """
def test_excluded_b_failure():
    assert False
"""
    )

    result = testdir.runpytest(
        "--reruns",
        "2",
        "--rerun-exclude-path",
        "excluded_a",
        "--rerun-exclude-path",
        "excluded_b",
    )

    assert_outcomes(result, passed=0, failed=3, rerun=2)
    executions = testdir.tmpdir.join("executions").read().splitlines()
    assert executions.count("test_normal_failure") == 3
    assert executions.count("test_excluded_a_failure") == 1
    assert executions.count("test_excluded_b_failure") == 1


def test_rerun_exclude_path_prevents_reruns_for_doctest(testdir):
    testdir.makeconftest(
        """
        from pathlib import Path

        def pytest_runtest_call(item):
            with Path("executions").open("a") as execution_log:
                execution_log.write(item.name + "\\n")
    """
    )
    testdir.makepyfile(
        test_normal="""
        def test_normal_failure():
            assert False
    """
    )
    docs_dir = testdir.mkdir("docs")
    docs_dir.join("guide.txt").write(
        """
This example fails:

    >>> 1 + 1
    3
"""
    )

    result = testdir.runpytest(
        "--doctest-glob=*.txt",
        "--reruns",
        "2",
        "--rerun-exclude-path",
        "docs/guide.txt",
    )

    assert_outcomes(result, passed=0, failed=2, rerun=2)
    executions = testdir.tmpdir.join("executions").read().splitlines()
    assert executions.count("test_normal_failure") == 3
    assert executions.count("guide.txt") == 1


@pytest.mark.parametrize(
    "only_rerun_texts, rerun_except_texts, should_rerun",
    [
        # Matches --only-rerun, but not --rerun-except (rerun)
        (["ValueError"], ["Not a Match"], True),
        (["ValueError", "AssertionError"], ["Not a match", "OSError"], True),
        # Matches --only-rerun AND --rerun-except (no rerun)
        (["ValueError"], ["ERR"], False),
        (["OSError", "ValueError"], ["Not a match", "ERR"], False),
        # Matches --rerun-except, but not --only-rerun (no rerun)
        (["OSError", "AssertionError"], ["TypeError", "ValueError"], False),
        # Matches neither --only-rerun nor --rerun-except (no rerun)
        (["AssertionError"], ["OSError"], False),
        # --rerun-except overrides --only-rerun for same arg (no rerun)
        (["ValueError"], ["ValueError"], False),
    ],
)
def test_rerun_except_and_only_rerun(
    testdir, rerun_except_texts, only_rerun_texts, should_rerun
):
    testdir.makepyfile('def test_only_rerun_except(): raise ValueError("ERR")')

    num_failed = 1
    num_passed = 0
    num_reruns = 1
    num_reruns_actual = num_reruns if should_rerun else 0

    pytest_args = ["--reruns", str(num_reruns)]
    for only_rerun_text in only_rerun_texts:
        pytest_args.extend(["--only-rerun", only_rerun_text])
    for rerun_except_text in rerun_except_texts:
        pytest_args.extend(["--rerun-except", rerun_except_text])
    result = testdir.runpytest(*pytest_args)
    assert_outcomes(
        result, passed=num_passed, failed=num_failed, rerun=num_reruns_actual
    )


def test_rerun_except_passes_setup_errors(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture()
        def fixture_setup_fails(non_existent_fixture):
            return 1

        def test_will_not_run(fixture_setup_fails):
            assert fixture_setup_fails == 1"""
    )

    num_reruns = 1
    pytest_args = ["--reruns", str(num_reruns), "--rerun-except", "ValueError"]
    result = testdir.runpytest(*pytest_args)
    assert result.ret != pytest.ExitCode.INTERNAL_ERROR
    assert_outcomes(result, passed=0, error=1, rerun=num_reruns)


@pytest.mark.parametrize(
    "rerun_except, expected_reruns",
    [("ValueError", 0), ("TypeError", 1)],
)
def test_rerun_except_setup_error(testdir, rerun_except, expected_reruns):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture()
        def fixture_setup_fails():
            raise ValueError("setup error")

        def test_will_not_run(fixture_setup_fails):
            pass
        """
    )

    result = testdir.runpytest("--reruns", "1", "--rerun-except", rerun_except)
    assert_outcomes(result, passed=0, error=1, rerun=expected_reruns)


def test_rerun_except_teardown_error_prevents_rerun(testdir):
    """Teardown errors covered by --rerun-except must prevent reruns."""
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture()
        def broken_fixture():
            yield
            raise ValueError("teardown error")

        def test_fail_in_fixture(broken_fixture):
            assert False
    """
    )

    result = testdir.runpytest("--reruns", "1", "--rerun-except", "ValueError")
    assert_outcomes(result, passed=0, failed=1, error=1, rerun=0)


@pytest.mark.parametrize(
    "condition, expected_reruns",
    [
        (1 == 1, 2),
        (1 == 2, 0),
        (True, 2),
        (False, 0),
        (1, 2),
        (0, 0),
        (["list"], 2),
        ([], 0),
        ({"dict": 1}, 2),
        ({}, 0),
        (None, 0),
    ],
)
def test_reruns_with_condition_marker(testdir, condition, expected_reruns):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.flaky(reruns=2, condition={condition})
        def test_fail_two():
            assert False"""
    )

    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=expected_reruns)


@pytest.mark.parametrize(
    "condition, expected_reruns",
    [('sys.platform.startswith("non-exists") == False', 2), ("os.getpid() != -1", 2)],
)
# before evaluating the condition expression, sys&os&platform package has been imported
def test_reruns_with_string_condition(testdir, condition, expected_reruns):
    testdir.makepyfile(
        f"""
           import pytest

           @pytest.mark.flaky(reruns=2, condition='{condition}')
           def test_fail_two():
               assert False"""
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_reruns_with_string_condition_with_global_var(testdir):
    testdir.makepyfile(
        """
              import pytest

              rerunBool = False
              @pytest.mark.flaky(reruns=2, condition='rerunBool')
              def test_fail_two():
                  global rerunBool
                  rerunBool = True
                  assert False"""
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=2)


@pytest.mark.parametrize("scope", ["class", "module", "session"])
def test_falsy_condition_preserves_higher_scope_teardown(testdir, scope):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.fixture(scope="{scope}", autouse=True)
        def higher_scope_fixture():
            yield
            print("{scope} teardown")

        class TestFlaky:
            @pytest.mark.flaky(reruns=2, condition=False)
            def test_fail(self):
                assert False"""
    )

    result = testdir.runpytest("-s")
    assert_outcomes(result, passed=0, failed=1, rerun=0)
    result.stdout.fnmatch_lines(f"*{scope} teardown*")


@pytest.mark.parametrize("condition", ["'os.getpid() == -1'"])
def test_falsy_non_bool_condition_preserves_teardown(testdir, condition):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            yield
            print("module teardown")

        @pytest.mark.flaky(reruns=2, condition={condition})
        def test_fail():
            assert False"""
    )

    result = testdir.runpytest("-s")
    assert_outcomes(result, passed=0, failed=1, rerun=0)
    result.stdout.fnmatch_lines("*module teardown*")


def test_falsy_condition_preserves_teardown_of_earlier_module(testdir):
    testdir.makepyfile(
        test_flaky_module="""
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def flaky_module_fixture():
            yield
            print("flaky module teardown")

        @pytest.mark.flaky(reruns=2, condition=False)
        def test_fail():
            assert False""",
        test_later_module="""
        def test_pass():
            pass""",
    )

    result = testdir.runpytest("-s")
    assert_outcomes(result, passed=1, failed=1, rerun=0)
    result.stdout.fnmatch_lines("*flaky module teardown*")


@pytest.mark.parametrize(
    "marker, args",
    [
        ("@pytest.mark.flaky(reruns=2, condition=True)", []),
        ("", ["--reruns", "2"]),
    ],
)
def test_rerunnable_failure_tears_down_module_fixture_once(testdir, marker, args):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            yield
            print("module teardown")

        {marker}
        def test_fail():
            assert False"""
    )

    result = testdir.runpytest("-s", *args)
    assert_outcomes(result, passed=0, failed=1, rerun=2)
    assert result.stdout.str().count("module teardown") == 1


@pytest.mark.parametrize("scope", ["class", "module", "session"])
def test_terminal_teardown_error_preserves_higher_scope_teardown(testdir, scope):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.fixture(scope="{scope}", autouse=True)
        def higher_scope_fixture():
            yield
            print("{scope} teardown")

        @pytest.fixture
        def broken_fixture():
            yield
            raise ValueError("teardown error")

        class TestFlaky:
            @pytest.mark.flaky(reruns=2, rerun_except=["ValueError"])
            def test_fail(self, broken_fixture):
                assert False"""
    )

    result = testdir.runpytest("-s")
    assert_outcomes(result, passed=0, failed=1, error=1, rerun=0)
    result.stdout.fnmatch_lines(f"*{scope} teardown*")


def test_terminal_teardown_error_preserves_teardown_of_earlier_module(testdir):
    testdir.makepyfile(
        test_flaky_module="""
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def flaky_module_fixture():
            yield
            print("flaky module teardown")

        @pytest.fixture
        def broken_fixture():
            yield
            raise ValueError("teardown error")

        @pytest.mark.flaky(reruns=2, rerun_except=["ValueError"])
        def test_fail(broken_fixture):
            assert False""",
        test_later_module="""
        def test_pass():
            print("later module test")""",
    )

    result = testdir.runpytest("-s")
    assert_outcomes(result, passed=1, failed=1, error=1, rerun=0)
    result.stdout.fnmatch_lines(
        ["*flaky module teardown*", "*later module test*"],
    )


def test_terminal_teardown_error_reports_failing_higher_scope_teardown(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            yield
            raise RuntimeError("module teardown error")

        @pytest.fixture
        def broken_fixture():
            yield
            raise ValueError("teardown error")

        @pytest.mark.flaky(reruns=2, rerun_except=["ValueError"])
        def test_fail(broken_fixture):
            assert False"""
    )

    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, error=1, rerun=0)
    result.stdout.fnmatch_lines(
        ["*RuntimeError: module teardown error*", "*ValueError: teardown error*"],
    )


def test_rerunnable_teardown_error_tears_down_module_fixture_once(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            yield
            print("module teardown")

        @pytest.fixture
        def broken_fixture():
            yield
            raise ValueError("teardown error")

        @pytest.mark.flaky(reruns=2, only_rerun=["AssertionError", "ValueError"])
        def test_fail(broken_fixture):
            assert False"""
    )

    result = testdir.runpytest("-s")
    assert_outcomes(result, passed=0, failed=1, error=3, rerun=2)
    assert result.stdout.str().count("module teardown") == 1


@pytest.mark.parametrize(
    "outcome,skipped,xfailed",
    [("skip", 3, 0), ("xfail", 0, 3)],
)
def test_teardown_error_that_is_not_a_failure_does_not_stop_reruns(
    testdir, outcome, skipped, xfailed
):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            yield
            print("module teardown")

        @pytest.fixture
        def not_failing_fixture():
            yield
            pytest.{outcome}("{outcome} in teardown")

        @pytest.mark.flaky(reruns=2, only_rerun=["AssertionError"])
        def test_fail(not_failing_fixture):
            assert False"""
    )

    result = testdir.runpytest("-s")
    assert_outcomes(
        result, passed=0, skipped=skipped, xfailed=xfailed, failed=1, rerun=2
    )
    assert result.stdout.str().count("module teardown") == 1


def test_terminal_teardown_error_lets_a_higher_scope_teardown_exit(testdir):
    testdir.makepyfile(
        test_flaky_module="""
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            yield
            pytest.exit("exit from teardown")

        @pytest.fixture
        def broken_fixture():
            yield
            raise ValueError("teardown error")

        @pytest.mark.flaky(reruns=2, rerun_except=["ValueError"])
        def test_fail(broken_fixture):
            assert False""",
        test_later_module="""
        def test_pass():
            print("later module test")""",
    )

    result = testdir.runpytest("-s")
    assert result.ret == pytest.ExitCode.INTERRUPTED
    result.stdout.fnmatch_lines("*Exit: exit from teardown*")
    assert "later module test" not in result.stdout.str()


def test_terminal_teardown_error_reports_higher_scope_teardown_without_context(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            yield
            raise RuntimeError("module teardown error")

        @pytest.fixture
        def broken_fixture():
            yield
            raise ValueError("teardown error") from None

        @pytest.mark.flaky(reruns=2, rerun_except=["ValueError"])
        def test_fail(broken_fixture):
            assert False"""
    )

    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, error=1, rerun=0)
    result.stdout.fnmatch_lines(
        ["*RuntimeError: module teardown error*", "*ValueError: teardown error*"],
    )


@pytest.mark.parametrize(
    "marker_only_rerun,cli_only_rerun,should_rerun",
    [
        ("AssertionError", None, True),
        ("AssertionError: ERR", None, True),
        (["AssertionError"], None, True),
        (["AssertionError: ABC"], None, False),
        ("ValueError", None, False),
        (["ValueError"], None, False),
        (["AssertionError", "ValueError"], None, True),
        # CLI override behavior
        ("AssertionError", "ValueError", True),
        ("ValueError", "AssertionError", False),
    ],
)
def test_only_rerun_flag_in_flaky_marker(
    testdir, marker_only_rerun, cli_only_rerun, should_rerun
):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.flaky(reruns=1, only_rerun={marker_only_rerun!r})
        def test_fail():
            raise AssertionError("ERR")
        """
    )
    args = []
    if cli_only_rerun:
        args.extend(["--only-rerun", cli_only_rerun])
    result = testdir.runpytest(*args)
    num_reruns = 1 if should_rerun else 0
    assert_outcomes(result, passed=0, failed=1, rerun=num_reruns)


@pytest.mark.parametrize(
    "filter_kwarg,should_rerun",
    [
        ("only_rerun=[AssertionError]", True),
        ("only_rerun=[ValueError]", False),
        ("rerun_except=[AssertionError]", False),
        ("rerun_except=[ValueError]", True),
    ],
)
def test_rerun_filter_accepts_exception_classes(testdir, filter_kwarg, should_rerun):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.flaky(reruns=1, {filter_kwarg})
        def test_fail():
            raise AssertionError("ERR")
        """
    )
    result = testdir.runpytest()
    num_reruns = 1 if should_rerun else 0
    assert_outcomes(result, passed=0, failed=1, rerun=num_reruns)


@pytest.mark.parametrize(
    "marker_rerun_except,cli_rerun_except,raised_error,should_rerun",
    [
        ("AssertionError", None, "AssertionError", False),
        ("AssertionError: ERR", None, "AssertionError", False),
        (["AssertionError"], None, "AssertionError", False),
        (["AssertionError: ABC"], None, "AssertionError", True),
        ("ValueError", None, "AssertionError", True),
        (["ValueError"], None, "AssertionError", True),
        (["OSError", "ValueError"], None, "AssertionError", True),
        (["OSError", "AssertionError"], None, "AssertionError", False),
        # CLI override behavior
        ("AssertionError", "ValueError", "AssertionError", False),
        ("ValueError", "AssertionError", "AssertionError", True),
        ("CustomFailure", None, "CustomFailure", False),
        ("CustomFailure", None, "AssertionError", True),
    ],
)
def test_rerun_except_flag_in_flaky_marker(
    testdir, marker_rerun_except, cli_rerun_except, raised_error, should_rerun
):
    testdir.makepyfile(
        f"""
        import pytest

        class CustomFailure(Exception):
            pass

        @pytest.mark.flaky(reruns=1, rerun_except={marker_rerun_except!r})
        def test_fail():
            raise {raised_error}("ERR")
        """
    )
    args = []
    if cli_rerun_except:
        args.extend(["--rerun-except", cli_rerun_except])
    result = testdir.runpytest(*args)
    num_reruns = 1 if should_rerun else 0
    assert_outcomes(result, passed=0, failed=1, rerun=num_reruns)


def test_ini_file_parameters(testdir):
    testdir.makepyfile(
        """
        import time
        def test_foo():
            assert False
    """
    )
    testdir.makeini(
        """
        [pytest]
        reruns = 2
        reruns_delay = 3
    """
    )
    time.sleep = mock.MagicMock()
    result = testdir.runpytest()

    time.sleep.assert_called_with(3)
    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_ini_file_parameters_override(testdir):
    testdir.makepyfile(
        """
        import time
        def test_foo():
            assert False
    """
    )
    testdir.makeini(
        """
        [pytest]
        reruns = 2
        reruns_delay = 3
    """
    )
    time.sleep = mock.MagicMock()
    result = testdir.runpytest("--reruns", "4", "--reruns-delay", "5")

    time.sleep.assert_called_with(5)
    assert_outcomes(result, passed=0, failed=1, rerun=4)


def test_run_session_teardown_once_after_reruns(testdir):
    testdir.makepyfile(
        """
        import logging
        import pytest

        from unittest import TestCase

        @pytest.fixture(scope='session', autouse=True)
        def session_fixture():
            logging.info('session setup')
            yield
            logging.info('session teardown')

        @pytest.fixture(scope='class', autouse=True)
        def class_fixture():
            logging.info('class setup')
            yield
            logging.info('class teardown')

        @pytest.fixture(scope='function', autouse=True)
        def function_fixture():
            logging.info('function setup')
            yield
            logging.info('function teardown')

        @pytest.fixture(scope='function')
        def function_skip_fixture():
            logging.info('skip fixture setup')
            pytest.skip('some reason')
            yield
            logging.info('skip fixture teardown')

        @pytest.fixture(scope='function')
        def function_setup_fail_fixture():
            logging.info('fail fixture setup')
            assert False
            yield
            logging.info('fail fixture teardown')

        class TestFirstPassLastFail:

            @staticmethod
            def test_1():
                logging.info("TestFirstPassLastFail 1")

            @staticmethod
            def test_2():
                logging.info("TestFirstPassLastFail 2")
                assert False

        class TestFirstFailLastPass:

            @staticmethod
            def test_1():
                logging.info("TestFirstFailLastPass 1")
                assert False

            @staticmethod
            def test_2():
                logging.info("TestFirstFailLastPass 2")

        class TestSkipFirst:
            @staticmethod
            @pytest.mark.skipif(True, reason='Some reason')
            def test_1():
                logging.info("TestSkipFirst 1")
                assert False

            @staticmethod
            def test_2():
                logging.info("TestSkipFirst 2")
                assert False

        class TestSkipLast:
            @staticmethod
            def test_1():
                logging.info("TestSkipLast 1")
                assert False

            @staticmethod
            @pytest.mark.skipif(True, reason='Some reason')
            def test_2():
                logging.info("TestSkipLast 2")
                assert False

        class TestSkipFixture:
            @staticmethod
            def test_1(function_skip_fixture):
                logging.info("TestSkipFixture 1")

        class TestSetupFailed:
            @staticmethod
            def test_1(function_setup_fail_fixture):
                logging.info("TestSetupFailed 1")

        class TestTestCaseFailFirstFailLast(TestCase):

            @staticmethod
            def test_1():
                logging.info("TestTestCaseFailFirstFailLast 1")
                assert False

            @staticmethod
            def test_2():
                logging.info("TestTestCaseFailFirstFailLast 2")
                assert False

        class TestTestCaseSkipFirst(TestCase):

            @staticmethod
            @pytest.mark.skipif(True, reason='Some reason')
            def test_1():
                logging.info("TestTestCaseSkipFirst 1")
                assert False

            @staticmethod
            def test_2():
                logging.info("TestTestCaseSkipFirst 2")
                assert False

        class TestTestCaseSkipLast(TestCase):

            @staticmethod
            def test_1():
                logging.info("TestTestCaseSkipLast 1")
                assert False

            @staticmethod
            @pytest.mark.skipif(True, reason="Some reason")
            def test_2():
                logging.info("TestTestCaseSkipLast 2")
                assert False"""
    )
    import logging

    logging.info = mock.MagicMock()

    result = testdir.runpytest("--reruns", "2")
    expected_calls = [
        mock.call("session setup"),
        # TestFirstPassLastFail
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestFirstPassLastFail 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstPassLastFail 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstPassLastFail 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstPassLastFail 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestFirstFailLastPass
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestFirstFailLastPass 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstFailLastPass 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstFailLastPass 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstFailLastPass 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestSkipFirst
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestSkipLast
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestSkipLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestSkipLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestSkipLast 1"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestSkipFixture
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("skip fixture setup"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestSetupFailed
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("fail fixture setup"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("fail fixture setup"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("fail fixture setup"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestTestCaseFailFirstFailLast
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestTestCaseSkipFirst
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestTestCaseSkipLast
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipLast 1"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        mock.call("session teardown"),
    ]

    logging.info.assert_has_calls(expected_calls, any_order=False)
    assert_outcomes(result, failed=8, passed=2, rerun=18, skipped=5, error=1)


def test_run_session_teardown_when_fixture_teardown_fails(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope='session', autouse=True)
        def session_fixture():
            yield
            print('session teardown')

        @pytest.fixture(scope='module', autouse=True)
        def module_fixture():
            yield
            print('module teardown')

        @pytest.fixture
        def broken_fixture():
            yield
            raise Exception("fixture teardown error")

        def test_fail_in_fixture(broken_fixture):
            pass

        def test_ok():
            pass
    """
    )

    result = testdir.runpytest("--reruns", "1", "-s")
    result.stdout.fnmatch_lines("*session teardown*")
    result.stdout.fnmatch_lines("*module teardown*")
    assert_outcomes(result, passed=3, rerun=1, error=1)


def test_exception_matches_rerun_except_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="package", autouse=True)
        def package_fixture():
            print("package setup")
            yield "package"
            print("package teardown")

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            print("module setup")
            yield "module"
            print("module teardown")

        @pytest.fixture(scope="class", autouse=True)
        def class_fixture():
            print("class setup")
            yield "class"
            print("class teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, rerun_except=["AssertionError"])
        class TestStuff:
            def test_1(self):
                raise AssertionError("fail")

            def test_2(self):
                raise ValueError("fail")

    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=2, rerun=1)
    result.stdout.fnmatch_lines("session teardown")
    result.stdout.fnmatch_lines("package teardown")
    result.stdout.fnmatch_lines("module teardown")
    result.stdout.fnmatch_lines("class teardown")
    result.stdout.fnmatch_lines("function teardown")


def test_exception_not_match_rerun_except_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, rerun_except="AssertionError")
        def test_1(session_fixture, function_fixture):
            raise ValueError("value")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=1)
    result.stdout.fnmatch_lines("session teardown")


def test_exception_matches_only_rerun_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, only_rerun=["AssertionError"])
        def test_1(session_fixture, function_fixture):
            raise AssertionError("fail")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=1)
    result.stdout.fnmatch_lines("session teardown")


def test_exception_not_match_only_rerun_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, only_rerun=["AssertionError"])
        def test_1(session_fixture, function_fixture):
            raise ValueError("fail")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1)
    result.stdout.fnmatch_lines("session teardown")


def test_exception_match_rerun_except_in_dual_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, rerun_except=["Exception"], only_rerun=["Not"])
        def test_1(session_fixture, function_fixture):
            raise Exception("fail")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1)
    result.stdout.fnmatch_lines("session teardown")


def test_exception_match_only_rerun_in_dual_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, rerun_except=["Not"], only_rerun=["Exception"])
        def test_1(session_fixture, function_fixture):
            raise Exception("fail")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=1)
    result.stdout.fnmatch_lines("session teardown")


@pytest.mark.parametrize("mark_params", ["", "reruns=1"])
def test_force_reruns(testdir, mark_params):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.flaky({mark_params})
        def test_fail():
            assert False
    """
    )

    result = testdir.runpytest("--force-reruns", "3")
    assert_outcomes(result, passed=0, failed=1, rerun=3)


@pytest.mark.parametrize(
    ("pytest_args", "ini", "marker"),
    [
        (("--reruns", "-1"), None, ""),
        ((), "reruns = -1", ""),
        (("--force-reruns", "-1"), None, ""),
        ((), None, "@pytest.mark.flaky(reruns=-1)"),
    ],
)
def test_negative_reruns_does_not_skip_initial_execution(
    testdir, pytest_args, ini, marker
):
    if ini:
        testdir.makeini(f"[pytest]\n{ini}")
    testdir.makepyfile(
        f"""
        import pytest

        {marker}
        def test_fail():
            assert False
        """
    )

    result = testdir.runpytest(*pytest_args)

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    assert_outcomes(result, passed=0, failed=1, rerun=0)


@pytest.mark.skipif(not has_xdist, reason="requires xdist")
def test_xdist_negative_marker_does_not_skip_initial_execution(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.flaky(reruns=-1)
        def test_fail():
            assert False
        """
    )

    result = testdir.runpytest("-p", "xdist", "-n", "1")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    assert_outcomes(result, passed=0, failed=1, rerun=0)


def test_reruns_mode_append_sums_marker_and_cli(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.flaky(reruns=2)
        def test_fail():
            assert False
    """
    )

    result = testdir.runpytest("--reruns", "4", "--reruns-mode", "append")
    assert_outcomes(result, passed=0, failed=1, rerun=6)


def test_reruns_mode_default_is_strict(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.flaky(reruns=2)
        def test_fail():
            assert False
    """
    )

    result = testdir.runpytest("--reruns", "4")
    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_reruns_mode_append_without_marker_uses_global(testdir):
    testdir.makepyfile(
        """
        def test_fail():
            assert False
    """
    )

    result = testdir.runpytest("--reruns", "3", "--reruns-mode", "append")
    assert_outcomes(result, passed=0, failed=1, rerun=3)


def test_reruns_mode_invalid_choice_errors(testdir):
    testdir.makepyfile(
        """
        def test_pass():
            assert True
    """
    )

    result = testdir.runpytest("--reruns-mode", "bogus")
    assert result.ret != 0


def test_max_suite_reruns_caps_total_reruns(testdir):
    """Suite limit stops reruns once the total across all tests is reached."""
    testdir.makepyfile(
        """
        def test_fail_1():
            assert False

        def test_fail_2():
            assert False

        def test_fail_3():
            assert False
    """
    )
    # 3 tests each allowed up to 3 reruns, but suite cap is 4 total
    result = testdir.runpytest("--reruns", "3", "--max-suite-reruns", "4")
    assert_outcomes(result, passed=0, failed=3, rerun=4)


def test_max_suite_reruns_caps_force_reruns(testdir):
    """Suite cap applies after ``--force-reruns`` selection."""
    testdir.makepyfile(
        """
        def test_fail_1():
            assert False

        def test_fail_2():
            assert False
    """
    )
    # Force reruns allows every failing test to rerun, but the suite cap should
    # limit total reruns to one.
    result = testdir.runpytest("--force-reruns", "5", "--max-suite-reruns", "1")
    assert_outcomes(result, passed=0, failed=2, rerun=1)


def test_max_suite_reruns_does_not_limit_when_sufficient(testdir):
    """Suite limit has no effect when total reruns stay below the cap."""
    testdir.makepyfile(
        """
        def test_fail():
            assert False
    """
    )
    result = testdir.runpytest("--reruns", "2", "--max-suite-reruns", "10")
    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_max_suite_reruns_zero_disables_all_reruns(testdir):
    """Suite limit of 0 prevents any reruns from occurring."""
    testdir.makepyfile(
        """
        def test_fail():
            assert False
    """
    )
    result = testdir.runpytest("--reruns", "3", "--max-suite-reruns", "0")
    assert_outcomes(result, passed=0, failed=1, rerun=0)


def test_max_suite_reruns_works_with_passing_tests(testdir):
    """Suite limit only counts actual reruns, not passing test runs."""
    testdir.makepyfile(
        """
        def test_pass():
            assert True

        def test_fail():
            assert False
    """
    )
    result = testdir.runpytest("--reruns", "3", "--max-suite-reruns", "2")
    assert_outcomes(result, passed=1, failed=1, rerun=2)


def test_max_suite_reruns_without_reruns_has_no_effect(testdir):
    """--max-suite-reruns alone (without --reruns) does not break anything."""
    testdir.makepyfile(
        """
        def test_fail():
            assert False
    """
    )
    result = testdir.runpytest("--max-suite-reruns", "5")
    assert_outcomes(result, passed=0, failed=1, rerun=0)


@pytest.mark.skipif(not has_subtests, reason="Only supported on pytest 9.0 and newer")
def test_failing_subtests_are_rerun(testdir):
    testdir.makepyfile(
        f"""
        import pytest

        def test_subtests(subtests):
            with subtests.test("Fails on first attempt"):
                {indent(temporary_failure(), "    ")}
    """
    )

    result = testdir.runpytest("--reruns", "1")
    assert result.ret == 0
    assert_outcomes(result, passed=1, rerun=1)


@pytest.mark.skipif(not has_subtests, reason="Only supported on pytest 9.0 and newer")
def test_too_many_failing_subtests_are_failures(testdir):
    testdir.makepyfile(
        """
        import pytest

        def test_subtests(subtests):
            with subtests.test("Always fails"):
                assert False
    """
    )

    result = testdir.runpytest("--reruns", "1")
    assert result.ret != 0
    assert_outcomes(result, passed=0, failed=2, rerun=1)


@pytest.mark.skipif(not has_subtests, reason="Only supported on pytest 9.0 and newer")
@pytest.mark.parametrize("scope", ["class", "module", "session"])
def test_failing_subtests_keep_higher_scope_fixture_alive(testdir, scope):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.fixture(scope="{scope}", autouse=True)
        def higher_scope_fixture():
            yield
            print("{scope} teardown")

        class TestSubtests:
            def test_subtests(self, subtests):
                with subtests.test("Fails on first attempt"):
                    {indent(temporary_failure(), "        ")}
    """
    )

    result = testdir.runpytest("-s", "--reruns", "1")
    assert_outcomes(result, passed=1, rerun=1)
    assert result.stdout.str().count(f"{scope} teardown") == 1


@pytest.mark.skipif(not has_subtests, reason="Only supported on pytest 9.0 and newer")
def test_failing_subtests_keep_earlier_module_fixture_alive(testdir):
    testdir.makepyfile(
        test_flaky_subtests_module=f"""
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def subtests_module_fixture():
            yield
            print("subtests module teardown")

        def test_subtests(subtests):
            with subtests.test("Fails on first attempt"):
                {indent(temporary_failure(), "    ")}""",
        test_later_module="""
        def test_pass():
            print("later module test")""",
    )

    result = testdir.runpytest("-s", "--reruns", "1")
    assert_outcomes(result, passed=2, rerun=1)
    assert result.stdout.str().count("subtests module teardown") == 1
    result.stdout.fnmatch_lines(
        ["*subtests module teardown*", "*later module test*"],
    )


@pytest.mark.skipif(not has_subtests, reason="Only supported on pytest 9.0 and newer")
def test_xfail_after_failing_subtest_restores_module_fixture(testdir):
    testdir.makepyfile(
        test_early_xfail_module="""
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def xfail_module_fixture():
            yield
            print("xfail module teardown")

        def test_xfail_after_subtest(subtests):
            with subtests.test("Fails"):
                assert False
            pytest.xfail("known issue")""",
        test_later_module="""
        def test_pass():
            print("later module test")""",
    )

    result = testdir.runpytest("-s", "--reruns", "2")
    assert_outcomes(result, passed=1, failed=1, xfailed=1, rerun=0)
    assert result.stdout.str().count("xfail module teardown") == 1
    result.stdout.fnmatch_lines(
        ["*xfail module teardown*", "*later module test*"],
    )


@pytest.mark.skipif(not has_subtests, reason="Only supported on pytest 9.0 and newer")
def test_too_many_failing_subtests_tear_down_module_fixture_once(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            yield
            print("module teardown")

        def test_subtests(subtests):
            with subtests.test("Always fails"):
                assert False
    """
    )

    result = testdir.runpytest("-s", "--reruns", "1")
    assert_outcomes(result, passed=0, failed=2, rerun=1)
    assert result.stdout.str().count("module teardown") == 1


@pytest.mark.skipif(
    not has_subtests or not has_xdist,
    reason="Requires pytest 9.0 or newer and xdist",
)
def test_failing_subtests_are_rerun_with_xdist(testdir):
    testdir.makepyfile(
        f"""
        import pytest

        def test_subtests(subtests):
            with subtests.test("Fails on first attempt"):
                {indent(temporary_failure(), "    ")}
    """
    )

    result = testdir.runpytest("-p", "xdist", "-n", "1", "--reruns", "1")
    assert result.ret == pytest.ExitCode.OK
    assert_outcomes(result, passed=1, failed=0, rerun=1)


@pytest.mark.skipif(
    not has_subtests or not has_xdist,
    reason="Requires pytest 9.0 or newer and xdist",
)
def test_too_many_failing_subtests_are_failures_with_xdist(testdir):
    testdir.makepyfile(
        """
        import pytest

        def test_subtests(subtests):
            with subtests.test("Always fails"):
                assert False
    """
    )

    result = testdir.runpytest("-p", "xdist", "-n", "1", "--reruns", "1")
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    assert_outcomes(result, passed=0, failed=2, rerun=1)


@pytest.mark.skipif(
    not has_subtests or not has_xdist,
    reason="Requires pytest 9.0 or newer and xdist",
)
def test_xdist_subtest_cleanup_is_scoped_to_worker(testdir):
    testdir.makepyfile(
        """
        import pytest

        def test_subtests(subtests):
            with subtests.test("Always fails"):
                assert False
    """
    )

    result = testdir.runpytest("-p", "xdist", "-n", "2", "--dist=each", "--reruns", "1")
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    assert_outcomes(result, passed=0, failed=4, rerun=2)


@pytest.mark.skipif(
    not has_subtests or not has_xdist,
    reason="Requires pytest 9.0 or newer and xdist",
)
def test_xdist_subtest_cleanup_is_scoped_to_item_index(testdir):
    test_file = testdir.makepyfile(
        """
        import pytest

        def test_subtests(subtests):
            with subtests.test("Always fails"):
                assert False
    """
    )

    result = testdir.runpytest(
        "-p",
        "xdist",
        "-n",
        "1",
        "--keep-duplicates",
        test_file,
        test_file,
        "--reruns",
        "1",
    )
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    assert_outcomes(result, passed=0, failed=4, rerun=2)


def test_max_suite_reruns_caps_flaky_marker_reruns(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.mark.flaky(reruns=3)
        def test_fail():
            assert False
        """
    )
    result = testdir.runpytest("--max-suite-reruns", "2")
    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_max_suite_reruns_rejects_negative_without_reruns(testdir):
    testdir.makepyfile("def test_pass(): pass")
    result = testdir.runpytest("--max-suite-reruns", "-1")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines("*--max-suite-reruns must be >= 0*")

    collect_result = testdir.runpytest("--collect-only", "--max-suite-reruns", "-1")
    assert collect_result.ret == pytest.ExitCode.USAGE_ERROR
    collect_result.stderr.fnmatch_lines("*--max-suite-reruns must be >= 0*")


def test_max_suite_reruns_preserves_fixture_teardown_when_exhausted(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            yield
            print("module teardown")

        def test_fail():
            assert False
        """
    )
    result = testdir.runpytest("-s", "--reruns", "1", "--max-suite-reruns", "0")
    result.stdout.fnmatch_lines("*module teardown*")

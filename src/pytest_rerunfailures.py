import hashlib
import importlib.metadata
import os
import platform
import re
import socket
import sys
import threading
import time
import traceback
import warnings
from contextlib import suppress

import pytest
from _pytest.outcomes import fail
from _pytest.runner import runtestprotocol
from packaging.version import parse as parse_version

try:
    from _pytest.subtests import SubtestReport, failed_subtests_key
except ImportError:
    if pytest.version_tuple >= (9, 0, 0):
        raise
    failed_subtests_key = None
    SubtestReport = None

try:
    from xdist.newhooks import pytest_handlecrashitem

    HAS_PYTEST_HANDLECRASHITEM = True
    del pytest_handlecrashitem
except ImportError:
    HAS_PYTEST_HANDLECRASHITEM = False


def works_with_current_xdist():
    """Return compatibility with installed pytest-xdist version.

    When running tests in parallel using pytest-xdist < 1.20.0, the first
    report that is logged will finish and terminate the current node rather
    rerunning the test. Thus we must skip logging of intermediate results under
    these circumstances, otherwise no test is rerun.

    """
    try:
        d = importlib.metadata.distribution("pytest-xdist")
    except importlib.metadata.PackageNotFoundError:
        return None
    else:
        return parse_version(d.version) >= parse_version("1.20")


RERUNS_DESC = "number of times to re-run failed tests. defaults to 0."
RERUNS_DELAY_DESC = "add time (seconds) delay between reruns."
RERUNS_DELAY_BACKOFF_FACTOR_DESC = (
    "multiply the rerun delay by this factor after each attempt, for an "
    "exponential backoff (delay * factor ** (attempt - 1)). defaults to 1.0, "
    "i.e. a constant delay."
)


# command line options
def pytest_addoption(parser):
    group = parser.getgroup(
        "rerunfailures", "re-run failing tests to eliminate flaky failures"
    )
    group._addoption(
        "--force-reruns",
        action="store",
        dest="force_reruns",
        type=int,
        help="Force rerunning all tests the specified number of times,"
        " irrespective of individual test markers.",
    )
    group._addoption(
        "--only-rerun",
        action="append",
        dest="only_rerun",
        type=str,
        default=None,
        help="If passed, only rerun errors matching the regex provided. "
        "Pass this flag multiple times to accumulate a list of regexes "
        "to match",
    )
    group._addoption(
        "--reruns",
        action="store",
        dest="reruns",
        type=int,
        help=RERUNS_DESC,
    )
    group._addoption(
        "--reruns-delay",
        action="store",
        dest="reruns_delay",
        type=float,
        help="add time (seconds) delay between reruns.",
    )
    group._addoption(
        "--reruns-delay-backoff-factor",
        action="store",
        dest="reruns_delay_backoff_factor",
        type=float,
        help=RERUNS_DELAY_BACKOFF_FACTOR_DESC,
    )
    group._addoption(
        "--rerun-except",
        action="append",
        dest="rerun_except",
        type=str,
        default=None,
        help="If passed, only rerun errors other than matching the "
        "regex provided. Pass this flag multiple times to accumulate a list "
        "of regexes to match",
    )
    group._addoption(
        "--reruns-mode",
        action="store",
        dest="reruns_mode",
        type=str,
        choices=("strict", "append"),
        default="strict",
        help="How to combine marker reruns with the global --reruns/reruns "
        "ini setting. 'strict' (default) gives the marker priority over the "
        "global setting. 'append' sums the marker and global counts so the "
        "two are additive.",
    )
    group._addoption(
        "--fail-on-flaky",
        action="store_true",
        dest="fail_on_flaky",
        help="Fail the test run with exit code 7 if a flaky test passes on a rerun.",
    )
    group._addoption(
        "--rerun-show-tracebacks",
        action="store_true",
        dest="rerun_show_tracebacks",
        help="Show tracebacks for failed attempts that were retried, including "
        "tests that eventually passed. Tracebacks are appended to the "
        "'rerun test summary info' section, which is emitted automatically "
        "when this flag is set.",
    )

    arg_type = "string"
    parser.addini("reruns", RERUNS_DESC, type=arg_type)
    parser.addini("reruns_delay", RERUNS_DELAY_DESC, type=arg_type)
    parser.addini(
        "reruns_delay_backoff_factor",
        RERUNS_DELAY_BACKOFF_FACTOR_DESC,
        type=arg_type,
    )


# making sure the options make sense
# should run before / at the beginning of pytest_cmdline_main
def check_options(config):
    val = config.getvalue
    if not val("collectonly"):
        if config.option.reruns != 0:
            if config.option.usepdb:  # a core option
                raise pytest.UsageError("--reruns incompatible with --pdb")


def _get_marker(item):
    return item.get_closest_marker("flaky")


def _get_global_reruns(item):
    reruns = item.session.config.getvalue("reruns")
    if reruns is not None:
        return reruns

    reruns = None
    with suppress(TypeError, ValueError):
        reruns = int(item.session.config.getini("reruns"))
    return reruns


def get_reruns_count(item):
    reruns = item.session.config.getvalue("force_reruns")
    if reruns is not None:
        return reruns

    rerun_marker = _get_marker(item)
    # use the marker as a priority over the global setting.
    if rerun_marker is not None:
        if "reruns" in rerun_marker.kwargs:
            # check for keyword arguments
            marker_reruns = rerun_marker.kwargs["reruns"]
        elif len(rerun_marker.args) > 0:
            # check for arguments
            marker_reruns = rerun_marker.args[0]
        else:
            marker_reruns = 1

        if item.session.config.getvalue("reruns_mode") == "append":
            global_reruns = _get_global_reruns(item)
            if global_reruns is not None:
                return marker_reruns + global_reruns
        return marker_reruns

    return _get_global_reruns(item)


def get_reruns_delay(item):
    rerun_marker = _get_marker(item)

    if rerun_marker is not None:
        if "reruns_delay" in rerun_marker.kwargs:
            delay = rerun_marker.kwargs["reruns_delay"]
        elif len(rerun_marker.args) > 1:
            # check for arguments
            delay = rerun_marker.args[1]
        else:
            delay = 0
    else:
        delay = item.session.config.getvalue("reruns_delay")
        if delay is None:
            try:
                delay = float(item.session.config.getini("reruns_delay"))
            except (TypeError, ValueError):
                delay = 0

    if delay < 0:
        delay = 0
        warnings.warn(
            "Delay time between re-runs cannot be < 0. Using default value: 0"
        )

    return delay


def get_reruns_delay_backoff_factor(item):
    rerun_marker = _get_marker(item)

    if rerun_marker is not None:
        if "reruns_delay_backoff_factor" in rerun_marker.kwargs:
            factor = rerun_marker.kwargs["reruns_delay_backoff_factor"]
        elif len(rerun_marker.args) > 2:
            # check for arguments
            factor = rerun_marker.args[2]
        else:
            factor = 1.0
    else:
        factor = item.session.config.getvalue("reruns_delay_backoff_factor")
        if factor is None:
            try:
                factor = float(
                    item.session.config.getini("reruns_delay_backoff_factor")
                )
            except (TypeError, ValueError):
                factor = 1.0

    if factor < 0:
        factor = 1.0
        warnings.warn(
            "Rerun delay backoff factor cannot be < 0. Using default value: 1.0"
        )

    return factor


def get_reruns_condition(item):
    rerun_marker = _get_marker(item)

    condition = True
    if rerun_marker is not None and "condition" in rerun_marker.kwargs:
        condition = evaluate_condition(
            item, rerun_marker, rerun_marker.kwargs["condition"]
        )

    return condition


def evaluate_condition(item, mark, condition: object) -> bool:
    # copy from python3.8 _pytest.skipping.py

    result = False
    # String condition.
    if isinstance(condition, str):
        globals_ = {
            "os": os,
            "sys": sys,
            "platform": platform,
            "config": item.config,
        }
        if hasattr(item, "obj"):
            globals_.update(item.obj.__globals__)  # type: ignore[attr-defined]
        try:
            filename = f"<{mark.name} condition>"
            condition_code = compile(condition, filename, "eval")
            result = eval(condition_code, globals_)  # noqa: S307
        except SyntaxError as exc:
            msglines = [
                f"Error evaluating {mark.name!r} condition",
                "    " + condition,
                "    " + " " * (exc.offset or 0) + "^",
                "SyntaxError: invalid syntax",
            ]
            fail("\n".join(msglines), pytrace=False)
        except Exception as exc:
            msglines = [
                f"Error evaluating {mark.name!r} condition",
                "    " + condition,
                *traceback.format_exception_only(type(exc), exc),
            ]
            fail("\n".join(msglines), pytrace=False)

    # Boolean condition.
    else:
        try:
            result = bool(condition)
        except Exception as exc:
            msglines = [
                f"Error evaluating {mark.name!r} condition as a boolean",
                *traceback.format_exception_only(type(exc), exc),
            ]
            fail("\n".join(msglines), pytrace=False)
    return result


def _remove_cached_results_from_failed_fixtures(item):
    """Note: remove all cached_result attribute from every fixture."""
    cached_result = "cached_result"
    fixture_info = getattr(item, "_fixtureinfo", None)
    for fixture_def_str in getattr(fixture_info, "name2fixturedefs", ()):
        fixture_defs = fixture_info.name2fixturedefs[fixture_def_str]
        for fixture_def in fixture_defs:
            if getattr(fixture_def, cached_result, None) is not None:
                result, _, err = getattr(fixture_def, cached_result)
                if err:  # Deleting cached results for only failed fixtures
                    setattr(fixture_def, cached_result, None)
                    # Clear finalizers registered during the failed execution
                    # so the fixture can be re-executed cleanly (pytest >= 9
                    # asserts _finalizers is empty before executing a fixture).
                    if hasattr(fixture_def, "_finalizers"):
                        fixture_def._finalizers.clear()


def _remove_failed_setup_state_from_session(item):
    """
    Clean up setup state.

    Note: remove only the current item, not higher-scoped items
    """
    setup_state = item.session._setupstate
    if item in setup_state.stack:
        del setup_state.stack[item]


def _remove_failed_subtests_from_report(item, report):
    """
    Clean up failed subtests stash entry.

    Note: This function does nothing on pytest versions without subtests support.
    """
    if failed_subtests_key is None:
        return

    failed_subtests = item.config.stash.get(failed_subtests_key, None)
    if failed_subtests is not None and report.nodeid in failed_subtests:
        del failed_subtests[report.nodeid]


def _remove_failed_subtest_reports_from_stats(item):
    """
    Remove already-logged SubtestReports for this item from the terminal reporter's
    stats buckets.

    SubtestReports are logged immediately during runtestprotocol (independent of
    log=False), so when a rerun is triggered they must be retroactively removed
    from all stat categories to avoid double-counting on the subsequent run.

    Concretely:
    - Failed SubtestReports land in tr.stats["failed"].
    - Passed SubtestReports land in tr.stats["subtests passed"].
    Both must be removed so the final tally only reflects the last (successful) run.

    Note: This function does nothing on pytest versions without subtests support.
    """
    if SubtestReport is None:
        return

    tr = item.config.pluginmanager.get_plugin("terminalreporter")
    if tr is None:
        return

    def _remove_subtest_reports(key):
        """
        Remove SubtestReports for item.nodeid from tr.stats[key].

        Returns the number of removed reports, and deletes the key entirely when
        the list becomes empty, because some code just checks the presence of
        the 'failed' key, but doesn't check the content.
        """
        if key not in tr.stats:
            return 0

        num_items_before = len(tr.stats[key])
        tr.stats[key] = [
            r
            for r in tr.stats[key]
            if not isinstance(r, SubtestReport) or r.nodeid != item.nodeid
        ]
        num_items_removed = num_items_before - len(tr.stats[key])

        if not tr.stats[key]:
            del tr.stats[key]

        return num_items_removed

    failed_removed = _remove_subtest_reports("failed")
    if failed_removed > 0:
        # Decrement session.testsfailed which was incremented when the
        # SubtestReport was originally logged via pytest_runtest_logreport.
        item.session.testsfailed = max(0, item.session.testsfailed - failed_removed)

    # When a test is rerun, subtests that already passed on the first attempt
    # will run again and produce a second SUBPASSED report. Remove the first
    # run's SUBPASSED entries so the count reflects each subtest exactly once.
    _remove_subtest_reports("subtests passed")


def _get_num_failed_subtests(item, report):
    """
    Return the number of failed subtests.

    Note: Returns 0 on pytest versions without subtests support.
    """
    if failed_subtests_key is None:
        return 0

    failed_subtests = item.config.stash.get(failed_subtests_key, None)
    if failed_subtests is not None:
        return failed_subtests.get(report.nodeid, 0)

    return 0


def _get_rerun_filter_regex(item, regex_name):
    rerun_marker = _get_marker(item)

    if rerun_marker is not None and regex_name in rerun_marker.kwargs:
        regex = rerun_marker.kwargs[regex_name]
        if isinstance(regex, str):
            regex = [regex]
    else:
        regex = getattr(item.session.config.option, regex_name)

    return regex


def _matches_any_rerun_error(rerun_errors, excinfo):
    return _try_match_error(rerun_errors, excinfo)


def _matches_any_rerun_except_error(rerun_except_errors, excinfo):
    return _try_match_error(rerun_except_errors, excinfo)


def _try_match_error(rerun_errors, excinfo):
    if excinfo:
        err = f"{excinfo.type.__name__}: {excinfo.value}"
        for rerun_error in rerun_errors:
            if isinstance(rerun_error, type) and issubclass(rerun_error, BaseException):
                if issubclass(excinfo.type, rerun_error):
                    return True
            elif re.search(rerun_error, err):
                return True
    return False


def _should_hard_fail_on_error(item, report, excinfo):
    if report.outcome != "failed":
        return False

    rerun_errors = _get_rerun_filter_regex(item, "only_rerun")
    rerun_except_errors = _get_rerun_filter_regex(item, "rerun_except")

    if (not rerun_errors) and (not rerun_except_errors):
        # Using neither --only-rerun nor --rerun-except
        return False

    elif rerun_errors and (not rerun_except_errors):
        # Using --only-rerun but not --rerun-except
        return not _matches_any_rerun_error(rerun_errors, excinfo)

    elif (not rerun_errors) and rerun_except_errors:
        # Using --rerun-except but not --only-rerun
        return _matches_any_rerun_except_error(rerun_except_errors, excinfo)

    else:
        # Using both --only-rerun and --rerun-except
        matches_rerun_only = _matches_any_rerun_error(rerun_errors, excinfo)
        matches_rerun_except = _matches_any_rerun_except_error(
            rerun_except_errors, excinfo
        )
        return (not matches_rerun_only) or matches_rerun_except


def _should_not_rerun(item, report, reruns):
    xfail = hasattr(report, "wasxfail")
    is_terminal_error = item._terminal_errors[report.when]
    condition = get_reruns_condition(item)
    has_failed_subtests = (
        report.when == "call" and _get_num_failed_subtests(item, report) > 0
    )

    return (
        item.execution_count > reruns
        or (not report.failed and not has_failed_subtests)
        or xfail
        or is_terminal_error
        or not condition
    )


def is_master(config):
    return not (hasattr(config, "workerinput") or hasattr(config, "slaveinput"))


def pytest_configure(config):
    # add flaky marker
    config.addinivalue_line(
        "markers",
        "flaky(reruns=1, reruns_delay=0, reruns_delay_backoff_factor=1.0): mark "
        "test to re-run up to 'reruns' times. Add a delay of 'reruns_delay' "
        "seconds between re-runs, multiplied by 'reruns_delay_backoff_factor' "
        "after each attempt for an exponential backoff.",
    )

    if config.pluginmanager.hasplugin("xdist") and HAS_PYTEST_HANDLECRASHITEM:
        config.pluginmanager.register(XDistHooks())
        if is_master(config):
            config.failures_db = ServerStatusDB()
        else:
            config.failures_db = ClientStatusDB(config.workerinput["sock_port"])
    else:
        config.failures_db = StatusDB()  # no-op db


class XDistHooks:
    def pytest_configure_node(self, node):
        """Configure xdist hook for node sock_port."""
        node.workerinput["sock_port"] = node.config.failures_db.sock_port

    def pytest_handlecrashitem(self, crashitem, report, sched):
        """Return the crashitem from pending and collection."""
        db = sched.config.failures_db
        reruns = db.get_test_reruns(crashitem)
        if db.get_test_failures(crashitem) < reruns:
            try:
                sched.mark_test_pending(crashitem)
                report.outcome = "rerun"
            except NotImplementedError:
                # Some schedulers (like LoadScopeScheduling) don't implement
                # mark_test_pending
                # In this case, we can't reschedule the crashed test for rerun
                # Mark it as failed with a clear message about why it couldn't be rerun
                report.outcome = "failed"
                if not hasattr(report, "longrepr") or report.longrepr is None:
                    error_msg = (
                        "Test crashed and could not be rescheduled for rerun."
                        f" The scheduler '{sched.__class__.__name__}' does not support"
                        " rescheduling crashed tests"
                        " (mark_test_pending not implemented)."
                        f" Remaining reruns: {reruns - db.get_test_failures(crashitem)}"
                    )
                    report.longrepr = error_msg

        db.add_test_failure(crashitem)


# An in-memory db residing in the master that records
# the number of reruns (set before test setup)
# and failures (set after each failure or crash)
# accessible from both the master and worker
class StatusDB:
    def __init__(self):
        self.delim = b"\n"
        self.hmap = {}

    def _hash(self, crashitem: str) -> str:
        if crashitem not in self.hmap:
            self.hmap[crashitem] = hashlib.sha1(crashitem.encode()).hexdigest()[:10]  # noqa: S324

        return self.hmap[crashitem]

    def add_test_failure(self, crashitem):
        hash = self._hash(crashitem)
        failures = self._get(hash, "f")
        failures += 1
        self._set(hash, "f", failures)

    def get_test_failures(self, crashitem):
        hash = self._hash(crashitem)
        return self._get(hash, "f")

    def set_test_reruns(self, crashitem, reruns):
        hash = self._hash(crashitem)
        self._set(hash, "r", reruns)

    def get_test_reruns(self, crashitem):
        hash = self._hash(crashitem)
        return self._get(hash, "r")

    # i is a hash of the test name, t_f.py::test_t
    # k is f for failures or r for reruns
    # v is the number of failures or reruns (an int)
    def _set(self, i: str, k: str, v: int):
        pass

    def _get(self, i: str, k: str) -> int:
        return 0


class SocketDB(StatusDB):
    def __init__(self):
        super().__init__()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(1)

    def _sock_recv(self, conn) -> str:
        buf = b""
        while True:
            b = conn.recv(1)
            if b == self.delim:
                break
            buf += b

        return buf.decode()

    def _sock_send(self, conn, msg: str):
        conn.send(msg.encode() + self.delim)


class ServerStatusDB(SocketDB):
    def __init__(self):
        super().__init__()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.rerunfailures_db = {}
        t = threading.Thread(target=self.run_server, daemon=True)
        t.start()

    @property
    def sock_port(self):
        return self.sock.getsockname()[1]

    def run_server(self):
        self.sock.listen()
        while True:
            conn, _ = self.sock.accept()
            t = threading.Thread(target=self.run_connection, args=(conn,), daemon=True)
            t.start()

    def run_connection(self, conn):
        with suppress(ConnectionError):
            while True:
                op, i, k, v = self._sock_recv(conn).split("|")
                if op == "set":
                    self._set(i, k, int(v))
                elif op == "get":
                    self._sock_send(conn, str(self._get(i, k)))

    def _set(self, i: str, k: str, v: int):
        if i not in self.rerunfailures_db:
            self.rerunfailures_db[i] = {}
        self.rerunfailures_db[i][k] = v

    def _get(self, i: str, k: str) -> int:
        try:
            return self.rerunfailures_db[i][k]
        except KeyError:
            return 0


class ClientStatusDB(SocketDB):
    def __init__(self, sock_port):
        super().__init__()
        self.sock.connect(("127.0.0.1", sock_port))

    def _set(self, i: str, k: str, v: int):
        self._sock_send(self.sock, "|".join(("set", i, k, str(v))))

    def _get(self, i: str, k: str) -> int:
        self._sock_send(self.sock, "|".join(("get", i, k, "")))
        return int(self._sock_recv(self.sock))


suspended_finalizers = {}


def pytest_runtest_teardown(item, nextitem):
    reruns = get_reruns_count(item)
    if reruns is None:
        # global setting is not specified, and this test is not marked with
        # flaky
        return

    if not hasattr(item, "execution_count"):
        # pytest_runtest_protocol hook of this plugin was not executed
        # -> teardown needs to be skipped as well
        return

    _test_failed_statuses = getattr(item, "_test_failed_statuses", {})

    # Only remove non-function level actions from the stack if the test is to be re-run
    # Exceeding re-run limits, being free of failue statuses, and encountering
    # allowable exceptions indicate that the test is not to be re-ran.
    if (
        item.execution_count <= reruns
        and any(_test_failed_statuses.values())
        and not any(item._terminal_errors.values())
    ):
        # clean cached results from any level of setups
        _remove_cached_results_from_failed_fixtures(item)

        if item in item.session._setupstate.stack:
            for key in list(item.session._setupstate.stack.keys()):
                if key != item:
                    # only the first finalizer contains the correct teardowns
                    if key not in suspended_finalizers:
                        suspended_finalizers[key] = item.session._setupstate.stack[key]
                    del item.session._setupstate.stack[key]
    else:
        # restore suspended finalizers
        item.session._setupstate.stack.update(suspended_finalizers)
        suspended_finalizers.clear()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    result = outcome.get_result()
    if result.when == "setup":
        # clean failed statuses at the beginning of each test/rerun
        setattr(item, "_test_failed_statuses", {})

        # create a dict to store error-check results for each stage
        setattr(item, "_terminal_errors", {})

    _test_failed_statuses = getattr(item, "_test_failed_statuses", {})
    _test_failed_statuses[result.when] = result.failed
    item._test_failed_statuses = _test_failed_statuses
    item._terminal_errors[result.when] = _should_hard_fail_on_error(
        item, result, call.excinfo
    )


def pytest_runtest_protocol(item, nextitem):
    """
    Run the test protocol.

    Note: when teardown fails, two reports are generated for the case, one for
    the test case and the other for the teardown error.
    """
    reruns = get_reruns_count(item)
    if reruns is None:
        # global setting is not specified, and this test is not marked with
        # flaky
        return

    # while this doesn't need to be run with every item, it will fail on the
    # first item if necessary
    check_options(item.session.config)
    delay = get_reruns_delay(item)
    delay_backoff_factor = get_reruns_delay_backoff_factor(item)
    parallel = not is_master(item.config)
    db = item.session.config.failures_db
    item.execution_count = db.get_test_failures(item.nodeid)
    db.set_test_reruns(item.nodeid, reruns)

    if item.execution_count > reruns:
        return True

    need_to_run = True
    while need_to_run:
        item.execution_count += 1
        item.ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
        reports = runtestprotocol(item, nextitem=nextitem, log=False)

        for report in reports:  # 3 reports: setup, call, teardown
            report.rerun = item.execution_count - 1
            if _should_not_rerun(item, report, reruns):
                # last run or no failure detected, log normally
                item.ihook.pytest_runtest_logreport(report=report)
            else:
                # failure detected and reruns not exhausted, since i < reruns
                report.outcome = "rerun"
                time.sleep(delay * delay_backoff_factor ** (item.execution_count - 1))

                if not parallel or works_with_current_xdist():
                    # will rerun test, log intermediate result
                    item.ihook.pytest_runtest_logreport(report=report)

                # cleanin item's cashed results from any level of setups
                _remove_cached_results_from_failed_fixtures(item)
                _remove_failed_setup_state_from_session(item)
                _remove_failed_subtests_from_report(item, report)
                _remove_failed_subtest_reports_from_stats(item)

                break  # trigger rerun
        else:
            need_to_run = False

        item.ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)

    return True


def pytest_report_teststatus(report):
    # Adapted from https://pytest.org/latest/_modules/_pytest/skipping.html
    if report.outcome == "rerun":
        return "rerun", "R", ("RERUN", {"yellow": True})


def pytest_terminal_summary(terminalreporter):
    # Adapted from https://pytest.org/latest/_modules/_pytest/skipping.html
    tr = terminalreporter
    show_tracebacks = tr.config.getoption("rerun_show_tracebacks", False)
    if not show_tracebacks and not any(c in "rR" for c in tr.reportchars):
        return

    lines = show_rerun(terminalreporter, show_tracebacks=show_tracebacks)
    if lines:
        tr._tw.sep("=", "rerun test summary info")
        for line in lines:
            tr._tw.line(line)


def show_rerun(terminalreporter, show_tracebacks=False):
    lines = []
    for rep in terminalreporter.stats.get("rerun", []):
        lines.append(f"RERUN {rep.nodeid}")
        if show_tracebacks and rep.longrepr:
            lines.extend(str(rep.longrepr).splitlines())
    return lines


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    if exitstatus != 0:
        return

    if session.config.option.fail_on_flaky:
        for item in session.items:
            if not hasattr(item, "execution_count"):
                # no rerun requested
                continue
            if item.execution_count > 1:
                session.exitstatus = 7
                break

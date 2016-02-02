import pytest

from _pytest.runner import runtestprotocol


# command line options
def pytest_addoption(parser):
    group = parser.getgroup(
        "rerunfailures",
        "re-run failing tests to eliminate flaky failures")
    group._addoption(
        '--reruns',
        action="store",
        dest="reruns",
        type="int",
        default=0,
        help="number of times to re-run failed tests. defaults to 0.")


def pytest_configure(config):
    # add flaky marker
    config.addinivalue_line(
        "markers", "flaky(reruns=1): mark test to re-run up to 'reruns' times")


# making sure the options make sense
# should run before / at the begining of pytest_cmdline_main
def check_options(config):
    val = config.getvalue
    if not val("collectonly"):
        if config.option.reruns != 0:
            if config.option.usepdb:   # a core option
                raise pytest.UsageError("--reruns incompatible with --pdb")


def pytest_runtest_protocol(item, nextitem):
    """
    Note: when teardown fails, two reports are generated for the case, one for
    the test case and the other for the teardown error.
    """
    rerun_marker = item.get_marker("flaky")
    # use the marker as a priority over the global setting.
    if rerun_marker is not None:
        if "reruns" in rerun_marker.kwargs:
            # check for keyword arguments
            reruns = rerun_marker.kwargs["reruns"]
        elif len(rerun_marker.args) > 0:
            # check for arguments
            reruns = rerun_marker.args[0]
    elif item.session.config.option.reruns is not None:
        # default to the global setting
        reruns = item.session.config.option.reruns
    else:
        # global setting is not specified, and this test is not marked with
        # flaky
        return

    # while this doesn't need to be run with every item, it will fail on the
    # first item if necessary
    check_options(item.session.config)

    for i in range(reruns + 1):  # ensure at least one run of each item
        item.ihook.pytest_runtest_logstart(nodeid=item.nodeid,
                                           location=item.location)
        reports = runtestprotocol(item, nextitem=nextitem, log=False)

        for report in reports:  # 3 reports: setup, test, teardown
            report.rerun = i
            xfail = hasattr(report, 'wasxfail')
            if i == reruns or not report.failed or xfail:
                # last run or no failure detected, log normally
                item.ihook.pytest_runtest_logreport(report=report)
            else:
                # failure detected and reruns not exhausted, since i < reruns
                report.outcome = 'rerun'

                # When running tests in parallel using pytest-xdist the first
                # report that is logged will finish and terminate the current
                # node rather rerunning the test. Thus we must skip logging of
                # intermediate results when running in parallel, otherwise no
                # test is rerun.
                # See: https://github.com/pytest-dev/pytest/issues/1193
                parallel_testing = hasattr(item.config, 'slaveinput')
                if not parallel_testing:
                    # will rerun test, log intermediate result
                    item.ihook.pytest_runtest_logreport(report=report)

                break  # trigger rerun
        else:
            return True  # no need to rerun

    return True


def pytest_report_teststatus(report):
    """Adapted from https://pytest.org/latest/_modules/_pytest/skipping.html
    """
    if report.outcome == 'rerun':
        return 'rerun', 'R', ('RERUN', {'yellow': True})


def pytest_terminal_summary(terminalreporter):
    """Adapted from https://pytest.org/latest/_modules/_pytest/skipping.html
    """
    tr = terminalreporter
    if not tr.reportchars:
        return

    lines = []
    for char in tr.reportchars:
        if char in 'rR':
            show_rerun(terminalreporter, lines)

    if lines:
        tr._tw.sep("=", "rerun test summary info")
        for line in lines:
            tr._tw.line(line)


def show_rerun(terminalreporter, lines):
    rerun = terminalreporter.stats.get("rerun")
    if rerun:
        for rep in rerun:
            pos = rep.nodeid
            lines.append("RERUN %s" % (pos,))

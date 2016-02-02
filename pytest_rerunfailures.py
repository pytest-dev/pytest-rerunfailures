import sys, time
import py, pytest

from _pytest.runner import runtestprotocol

# command line options
def pytest_addoption(parser):
    group = parser.getgroup("rerunfailures", "re-run failing tests to eliminate flakey failures")
    group._addoption('--reruns',
        action="store",
        dest="reruns",
        type="int",
        default=0,
        help="number of times to re-run failed tests. defaults to 0.")
        

def pytest_configure(config):
    #Add flaky marker
    config.addinivalue_line("markers", "flaky(reruns=1): mark test to re-run up to 'reruns' times")

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
    Note: when teardown fails, two reports are generated for the case, one for the test
    case and the other for the teardown error.

    Note: in some versions of py.test, when setup fails on a test that has been marked with xfail, 
    it gets an XPASS rather than an XFAIL 
    (https://bitbucket.org/hpk42/pytest/issue/160/an-exception-thrown-in)
    fix should be released in version 2.2.5
    """

    if not hasattr(item, 'get_marker'):
        # pytest < 2.4.2 doesn't support get_marker
        rerun_marker = None
        val = item.keywords.get("flaky", None)
        if val is not None:
            from _pytest.mark import MarkInfo, MarkDecorator
            if isinstance(val, (MarkDecorator, MarkInfo)):
                rerun_marker = val
    else:
        #In pytest 2.4.2, we can do this pretty easily.
        rerun_marker = item.get_marker("flaky")

    #Use the marker as a priority over the global setting.
    if rerun_marker is not None:
        if "reruns" in rerun_marker.kwargs:
            #Check for keyword arguments
            reruns = rerun_marker.kwargs["reruns"]
        elif len(rerun_marker.args) > 0:
            #Check for arguments
            reruns = rerun_marker.args[0]
    elif item.session.config.option.reruns is not None:
        #Default to the global setting
        reruns = item.session.config.option.reruns
    else:
        #Global setting is not specified, and this test is not marked with flaky
        return
    
    # while this doesn't need to be run with every item, it will fail on the first 
    # item if necessary
    check_options(item.session.config)

    item.ihook.pytest_runtest_logstart(
        nodeid=item.nodeid, location=item.location,
    )

    for i in range(reruns+1):  # ensure at least one run of each item
        reports = runtestprotocol(item, nextitem=nextitem, log=False)
        # break if setup and call pass
        if reports[0].passed and reports[1].passed:
            break

        # break if test marked xfail
        evalxfail = getattr(item, '_evalxfail', None)
        if evalxfail:
            break

    for report in reports:
        if report.when in ("call"):
            if i > 0:
                report.rerun = i
        item.ihook.pytest_runtest_logreport(report=report)

    # pytest_runtest_protocol returns True
    return True


def pytest_report_teststatus(report):
    """ adapted from
    https://bitbucket.org/hpk42/pytest/src/a5e7a5fa3c7e/_pytest/skipping.py#cl-170
    """
    if report.when in ("call"):
        if hasattr(report, "rerun") and report.rerun > 0:
            if report.outcome == "failed":
                return "failed", "F", "FAILED"
            if report.outcome == "passed":
                return "rerun", "R", "RERUN"


def pytest_terminal_summary(terminalreporter):
    """ adapted from
    https://bitbucket.org/hpk42/pytest/src/a5e7a5fa3c7e/_pytest/skipping.py#cl-179
    """
    tr = terminalreporter
    if not tr.reportchars:
        return

    lines = []
    for char in tr.reportchars:
        if char in "rR":
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

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

# making sure the options make sense
# should run before / at the begining of pytest_cmdline_main
def check_options(config):
    val = config.getvalue
    if not val("collectonly"):
        if config.option.reruns != 0:
            if config.option.usepdb:   # a core option
                raise pytest.UsageError("--reruns incompatible with --pdb")

flakey_tests = []

def pytest_runtest_protocol(item, nextitem):
    """
    Note: when teardown fails, two reports are generated for the case, one for the test
    case and the other for the teardown error.

    Note: in some versions of py.test, when setup fails on a test that has been marked with xfail, 
    it gets an XPASS rather than an XFAIL 
    (https://bitbucket.org/hpk42/pytest/issue/160/an-exception-thrown-in)
    fix should be released in version 2.2.5
    """
    reruns = item.session.config.option.reruns
    if reruns == 0:
        return
    # while this doesn't need to be run with every item, it will fail on the first 
    # item if necessary
    check_options(item.session.config)

    item.ihook.pytest_runtest_logstart(
        nodeid=item.nodeid, location=item.location,
    )

    for i in range(reruns+1):  # ensure at least one run of each item
        reports = runtestprotocol(item, nextitem=nextitem, log=False)
        #XXX: xfail?
        failures = [ x for x in reports if not x.passed]
        if failures:
            #XXX: local node state not passed on
            flakey_tests.extend(failures)
        else:
            break
   
    for report in reports:
        if i > 0:
            report.flakey = i
        item.ihook.pytest_runtest_logreport(report=report)
    # pytest_runtest_protocol returns True
    return True

def pytest_terminal_summary(terminalreporter):
    config = terminalreporter.config
    if not flakey_tests or config.option.quiet or config.option.reruns == 0:
        return

    tw = terminalreporter._tw
    tw.sep('-', '%s failed tests rerun' % len(flakey_tests))

    if config.option.verbose > 0:
        for test in flakey_tests:
            tw.line('%s: %s' % (test.nodeid, test.outcome.upper()))


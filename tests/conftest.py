import sys, time
import py, pytest

############################## the plugin #############################
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
        if val("reruns"):
            if config.option.usepdb:  # a core option
                raise pytest.UsageError("--pdb incompatible with --reruns.")

def pytest_configure(config):
    """extending https://bitbucket.org/hpk42/pytest/src/fa6a843aa98b/_pytest/main.py#cl-61"""
    py.test.config = config # compatibiltiy
    if config.option.exitfirst:
        config.option.maxfail = 1

    check_options(config)

def pytest_runtest_protocol(item, nextitem):
    """
    A mishmash of
    https://bitbucket.org/hpk42/pytest/src/fa6a843aa98b/_pytest/runner.py#cl-57
    https://bitbucket.org/hpk42/pytest/src/fa6a843aa98b/_pytest/runner.py#cl-64

    Note: when teardown fails, two reports are generated for the case, one for the test
    case and the other for the teardown error.

    Note: in some versions of py.test, when setup fails on a test that has been marked with xfail, 
    it gets an XPASS rather than an XFAIL 
    (https://bitbucket.org/hpk42/pytest/issue/160/an-exception-thrown-in)
    fix should be released in version 2.2.5
    """
    item.ihook.pytest_runtest_logstart(
        nodeid=item.nodeid, location=item.location,
    )
    reruns = item.session.config.option.reruns
    i = -1
    reports = None
    log = False
    while i < reruns:  # ensure at least one run of each item
        reports = []
        setup_rep = call_and_report(item, "setup")
        reports = [setup_rep]
        teardown_rep = None

        if setup_rep.passed:
            # print "setup passed %s" % i
            call_rep = call_and_report(item, "call")
            reports.append(call_rep)
            if call_rep.passed:
                # print "test call passed %s" % i
                teardown_rep = call_and_report(item, "teardown",
                    nextitem=nextitem)
                reports.append(teardown_rep)
                break  # passing case, break the loop
            else:  # test call failed
                # print "test call failed %s" % i
                teardown_rep = call_and_report(item, "teardown",
                    nextitem=item)
                reports.append(teardown_rep)
        else:  # setup failed
            print "setup failed %s" % i
            teardown_rep = call_and_report(item, "teardown", nextitem=None)

        i += 1

    # runtestprotocol returns reports, but
    # pytest_runtest_protocol returns True
    return True

################## methods copied to make other methods work #################

def call_and_report(item, when, log=True, **kwds):
    """ Copied from https://bitbucket.org/hpk42/pytest/src/fa6a843aa98b/_pytest/runner.py#cl-96 """
    call = call_runtest_hook(item, when, **kwds)
    hook = item.ihook
    report = hook.pytest_runtest_makereport(item=item, call=call)
    if log:
        hook.pytest_runtest_logreport(report=report)
    return report

def call_runtest_hook(item, when, **kwds):
    """ Copied from https://bitbucket.org/hpk42/pytest/src/fa6a843aa98b/_pytest/runner.py#cl-104 """
    hookname = "pytest_runtest_" + when
    ihook = getattr(item.ihook, hookname)
    return CallInfo(lambda: ihook(item=item, **kwds), when=when)

class CallInfo:
    """ Copied from https://bitbucket.org/hpk42/pytest/src/fa6a843aa98b/_pytest/runner.py#cl-109 """
    #: None or ExceptionInfo object.
    excinfo = None
    def __init__(self, func, when):
        #: context of invocation: one of "setup", "call",
        #: "teardown", "memocollect"
        self.when = when
        self.start = time.time()
        try:
            try:
                self.result = func()
            except KeyboardInterrupt:
                raise
            except:
                self.excinfo = py.code.ExceptionInfo()
        finally:
            self.stop = time.time()

    def __repr__(self):
        if self.excinfo:
            status = "exception: %s" % str(self.excinfo.value)
        else:
            status = "result: %r" % (self.result,)
        return "<CallInfo when=%r %s>" % (self.when, status)

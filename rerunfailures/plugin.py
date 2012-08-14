import sys, time
import py, pytest

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
            elif config.option.usepdb:   # a core option
                raise pytest.UsageError("--reruns incompatible with --pdb")

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

    # while this doesn't need to be run with every item, it will fail on the first 
    # item if necessary
    check_options(item.session.config)

    item.ihook.pytest_runtest_logstart(
        nodeid=item.nodeid, location=item.location,
    )

    reruns = item.session.config.option.reruns
    i = -1
    while i < reruns:  # ensure at least one run of each item
        i += 1
        setup_rep = call_and_report(item, "setup")
        call_rep = None
        teardown_rep = None

        if setup_rep.passed:
            call_rep = call_and_report(item, "call")
            if call_rep.passed:
                teardown_rep = call_and_report(item, "teardown",
                    nextitem=nextitem)
                break  # passing case, break the loop
            else:  # test call failed
                teardown_rep = call_and_report(item, "teardown",
                    nextitem=item)
        else:  # setup failed
            teardown_rep = call_and_report(item, "teardown", nextitem=None)


    # publish reports only from the last run
    publish_reports(item, setup_rep, call_rep, teardown_rep)

    # pytest_runtest_protocol returns True
    return True

def publish_reports(item, setup_rep, call_rep, teardown_rep):
    item.ihook.pytest_runtest_logreport(report=setup_rep)
    if call_rep:
        item.ihook.pytest_runtest_logreport(report=call_rep)
    item.ihook.pytest_runtest_logreport(report=teardown_rep)

def call_and_report(item, when, **kwds):
    """ Modified from https://bitbucket.org/hpk42/pytest/src/fa6a843aa98b/_pytest/runner.py#cl-96 """
    call = call_runtest_hook(item, when, **kwds)
    hook = item.ihook
    report = hook.pytest_runtest_makereport(item=item, call=call)
    return report

################## methods copied to make other methods work #################

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


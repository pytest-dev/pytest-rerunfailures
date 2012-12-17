import sys, time
import py, pytest

from _pytest.runner import runtestprotocol
# from _pytest.python import Class, xunitsetup
# from _pytest.unittest import UnitTestCase

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
                return "failed", "F", "failed"
            if report.outcome == "passed":
                return "rerun", "R", "rerun"

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

# for interoperability with unittest's setup_class

# class PythonUnitTestCase(Class):
#     def setup(self):
#         print 'PythonUnitTestCase.setup()'
#         setup_class = xunitsetup(self.obj, 'setup_class')
#         reruns = self.session.config.option.reruns
#         if setup_class is not None:
#             setup_class = getattr(setup_class, 'im_func', setup_class)
#             setup_class = getattr(setup_class, '__func__', setup_class)
#             # setup_class(self.obj)

#             attempt = -1
#             e = None
#             print 'attempt: %s, retries: %s' % (attempt, reruns)
#             while attempt < reruns:
#                 try:
#                     print 'trying setup method'
#                     setup_class(self.obj)
#                     return
#                 except Exception as e:
#                     print 'had setup failure'
#                 finally:
#                     attempt += 1
#             if e:
#                 raise e
#             assert False, 'should have failed already'


# def pytest_pycollect_makeitem(collector, name, obj):
#     unittest = sys.modules.get('unittest')
#     if unittest is None:
#         return # nobody can have derived unittest.TestCase
#     try:
#         isunit = issubclass(obj, unittest.TestCase)
#     except KeyboardInterrupt:
#         raise
#     except Exception:
#         pass
#     else:
#         if isunit:
#             return UnitTestCase(name, parent=collector)
#         else:
#             return PythonUnitTestCase(name, parent=collector)


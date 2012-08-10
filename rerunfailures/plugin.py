import sys
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
        if val("reruns"):
            if config.option.usepdb:  # a core option
                raise pytest.UsageError("--pdb incompatible with --reruns.")

def pytest_runtest_protocol(item, nextitem):
    reruns = item.session.config.option.reruns
    i = -1
    reports = None
    while i < reruns:  # ensure at least one run of each item
        reports = []
        setup_rep = call_and_report(item, "setup", log)
        reports = [rep]
        if setup_rep.passed:
            call_rep = call_and_report(item, "call", log)
            reports.append(call_rep)
            teardown_rep = None
            if call_rep.passed:
                teardown_rep = call_and_report(item, "teardown", log,
                    nextitem=nextitem)
                reports.append(teardown_rep)
                continue  # passing case, break the loop
            else:
                teardown_rep = call_and_report(item, "teardown", log,
                    nextitem=item)
                reports.append(teardown_rep)
                # print the report to the terminal only
        else:
            teardown_rep = call_and_report(item, "teardown", log, nextitem=item)
            # print the report to the terminal only
        i++

    if i > 0:
        print "test was re-run %s times" % i
    return reports

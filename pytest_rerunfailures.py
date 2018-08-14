import copy
import json
import pkg_resources
import time
import warnings
from contextlib import contextmanager

import pytest

from _pytest.resultlog import ResultLog
from _pytest.runner import runtestprotocol


def works_with_current_xdist():
    """
    Pytest hook

    Returns compatibility with installed pytest-xdist version.

    When running tests in parallel using pytest-xdist < 1.20.0, the first
    report that is logged will finish and terminate the current node rather
    rerunning the test. Thus we must skip logging of intermediate results under
    these circumstances, otherwise no test is rerun.

    Returns
    -------
    result : bool || None
    """
    try:
        d = pkg_resources.get_distribution('pytest-xdist')
        return d.parsed_version >= pkg_resources.parse_version('1.20')
    except pkg_resources.DistributionNotFound:
        return None


def check_options(config):
    """
    Making sure the options make sense
    should run before / at the begining of pytest_cmdline_main

    Parameters
    ----------
    config : _pytest.config.Config
    """
    val = config.getvalue
    if not val("collectonly"):
        if config.option.reruns != 0:
            if config.option.usepdb:   # a core option
                raise pytest.UsageError("--reruns incompatible with --pdb")


def pytest_addoption(parser):
    """
    Added rerunfailed related flags to pytest_addoption hook

    Parameters
    ----------
    parser : _pytest.config.Parser
    """
    group = parser.getgroup(
        "rerunfailures",
        "re-run failing tests with fixtures invalidation to eliminate flaky failures")
    group._addoption(
        '--reruns',
        action="store",
        dest="reruns",
        type=int,
        default=0,
        help="number of times to re-run failed tests. defaults to 0.")
    group._addoption(
        '--reruns-delay',
        action='store',
        dest='reruns_delay',
        type=float,
        default=0,
        help='add time (seconds) delay between reruns.'
    )
    group._addoption(
        '--reruns-artifact-path',
        action='store',
        dest='reruns_artifact_path',
        type=str,
        default='',
        help='provide path to export reruns artifact.'
    )
    group._addoption(
        '--max-tests-rerun',
        action='store',
        dest='max_tests_rerun',
        type=int,
        default=None,
        help='max amount of failures at which reruns would be executed'
    )


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """
    Defined appropriate plugins selection in pytest_configure hook

    Parameters
    ----------
    config : _pytest.config.Config
    """
    config.addinivalue_line(
        "markers", "flaky(reruns=1, reruns_delay=0): mark test to re-run up "
                   "to 'reruns' times. Add a delay of 'reruns_delay' seconds "
                   "between re-runs.")

    check_options(config)

    plugin = RerunPlugin()
    config.pluginmanager.register(plugin, 'RerunPlugin')

    resultlog = getattr(config, '_resultlog', None)
    if resultlog:
        logfile = resultlog.logfile
        config.pluginmanager.unregister(resultlog)
        config._resultlog = RerunResultLog(config, logfile)
        config.pluginmanager.register(config._resultlog)


class RerunPlugin(object):
    """Pytest plugin implements rerun failed functionality"""

    def __init__(self):
        self.tests_to_rerun = set([])
        self.mainrun_stats = {}
        self.rerun_stats = {
            'rerun_tests': [],
            'total_failed': 0,
            'total_reruns': 0,
            'total_resolved_by_reruns': 0
        }
        # resolving xdist worker object
        self.xdist_worker = next(iter(filter(
            lambda x: x.__class__.__name__ == 'WorkerInteractor', 
            pytest.config.pluginmanager.get_plugins()
        )), None)
        self.reruns_time = 0
        self.test_reports = {}

    def _failed_test(self, nodeid):
        """
        Template format for failed test stat

        Returns
        -------
        dict
        """
        default_stat = {'nodeid': nodeid, 'status': 'failed'}
        default_stat.update(self._test_traces())
        stat = self.mainrun_stats.get(nodeid, default_stat)
        self.mainrun_stats[nodeid] = stat
        return stat

    def _rerun_test(self, nodeid):
        """
        Template format for rerun test stat

        Returns
        -------
        dict
        """
        stat = {
            'nodeid': nodeid,
            'status': 'failed',
            'rerun_trace': self._test_traces(),
            'original_trace': {
                'setup': self.mainrun_stats[nodeid]['setup'],
                'call': self.mainrun_stats[nodeid]['call'],
                'teardown': self.mainrun_stats[nodeid]['teardown'],
            }
        }
        self.rerun_stats['rerun_tests'].append(stat)
        return stat

    def _test_traces(self):
        """Default traces structures"""
        return {
            'setup': {
                'caplog': None,
                'capstderr': None,
                'capstdout': None,
                'text_repr': None
            },
            'call': {
                'caplog': None,
                'capstderr': None,
                'capstdout': None,
                'text_repr': None
            },
            'teardown': {
                'caplog': None,
                'capstderr': None,
                'capstdout': None,
                'text_repr': None
            }
        }

    def pytest_runtest_protocol(self, item, nextitem):
        """
        Pytest hook

        Note: when teardown fails, two reports are generated for the case, one for
        the test case and the other for the teardown error.

        Parameters
        ----------
        item : _pytest.main.Item
        nextitem : _pytest.main.Item || None
        """
        item.ihook.pytest_runtest_logstart(
            nodeid=item.nodeid, location=item.location)
        reports = runtestprotocol(item, nextitem=nextitem, log=False)
        reruns = self._get_reruns_count(item)
        
        self.test_reports[item.nodeid] = copy.deepcopy(reports)

        for report in reports:  # 3 reports: setup, call, teardown
            xfail = hasattr(report, 'wasxfail')
            if report.failed and not xfail and reruns > 0:
                # failure detected
                stat = self._failed_test(item.nodeid)
                stat[report.when]['caplog'] = report.caplog
                stat[report.when]['capstderr'] = report.capstderr
                stat[report.when]['capstdout'] = report.capstdout
                stat[report.when]['text_repr'] = report.longreprtext

                self.tests_to_rerun.add(item)
                report.outcome = 'rerun'

            item.ihook.pytest_runtest_logreport(report=report)

        # Last test of a testrun was performed
        if nextitem == None:
            max_tests_reruns = item.config.option.max_tests_rerun
            if max_tests_reruns and len(self.tests_to_rerun) > max_tests_reruns:
                self._skip_reruns(
                    max_tests_reruns,
                    item.config.pluginmanager.getplugin("terminalreporter")
                )
                return True
            rerun_start = time.time()
            self._execute_reruns()
            self._save_reruns_artifact(item.session)
            self.reruns_time = time.time() - rerun_start
        return True

    def _skip_reruns(self, max_tests_reruns, terminalreporter):
        """
        Skip reruns and republish reports
        """
        msg = "Too many failed test: %s with threshold of %s. Restore failures without reruns" % (
            len(self.tests_to_rerun), max_tests_reruns
        )
        markup = {'red': True, "bold": True}
        terminalreporter.write_sep("=", msg, **markup)

        for item in self.tests_to_rerun:
            for report in self.test_reports[item.nodeid]:
                item.ihook.pytest_runtest_logreport(report=report)

        self.tests_to_rerun = []

    def _execute_reruns(self):
        """
        Perform reruns for failed tests
        """
        for item in self.tests_to_rerun:
            self._invalidate_fixtures(item)

        self.rerun_stats['total_failed'] = len(self.tests_to_rerun)
        for item in self.tests_to_rerun:
            reruns = self._get_reruns_count(item)
            if reruns is None:
                continue

            with self._prepare_xdist(item):
                self._rerun_item(item, reruns)

        for rerun in self.rerun_stats['rerun_tests']:
            rerun['status'] = self.mainrun_stats[rerun['nodeid']]['status']

    def _rerun_item(self, item, reruns):
        """
        Perform reruns for single test items

        Parameters
        ----------
        item : _pytest.main.Item
        """
        delay = self._get_reruns_delay(item)
        parallel = hasattr(item.config, 'slaveinput')

        for i in range(reruns):
            time.sleep(delay)
            item.ihook.pytest_runtest_logstart(
                nodeid=item.nodeid, location=item.location)
            reports = runtestprotocol(item, nextitem=None, log=False)
            rerun_status = True
            stat = self._rerun_test(item.nodeid)
            for report in reports:
                xfail = hasattr(report, 'wasxfail')
                report.rerun = i
                rerun_status = rerun_status and (not report.failed or xfail)
                if report.failed and (i != reruns - 1):
                    report.outcome = 'rerun'
                if not parallel or works_with_current_xdist():
                    # will log intermediate result
                    item.ihook.pytest_runtest_logreport(report=report)

                stat['rerun_trace'][report.when]['caplog'] = report.caplog
                stat['rerun_trace'][report.when]['capstderr'] = report.capstderr
                stat['rerun_trace'][report.when]['capstdout'] = report.capstdout
                stat['rerun_trace'][report.when]['text_repr'] = report.longreprtext

            self.rerun_stats['total_reruns'] += 1

            if rerun_status:
                self.rerun_stats['total_resolved_by_reruns'] += 1
                self.mainrun_stats[item.nodeid]['status'] = 'flake'
                break

    def _invalidate_fixtures(self, item):
        """
        Invalidate fixtures related to test item

        Parameters
        ----------
        item : _pytest.main.Item
        """
        # collect all item related fixtures and call finalizers for them
        fixturemanager = item.session._fixturemanager
        fixtures = set(item.fixturenames)
        fixtures.update(fixturemanager._getautousenames(item.nodeid))
        fixtures.update(item._fixtureinfo.argnames)
        usefixtures = getattr(item.function, 'usefixtures', None)
        if usefixtures:
            fixtures.update(usefixtures.args)

        for fixt in fixtures:
            for fixtdef in fixturemanager.getfixturedefs(fixt, item.nodeid) or []:
                item._initrequest()
                fixtdef.finish(item._request)

    def pytest_report_teststatus(self, report):
        """
        Pytest hook

        Handle of report rerun outcome
        Adapted from https://docs.pytest.org/en/latest/skipping.html

        Parameters
        ----------
        report : _pytest.runner.TestReport
        """
        if report.outcome == 'rerun':
            return 'rerun', 'R', ('RERUN', {'yellow': True})

    def pytest_terminal_summary(self, terminalreporter):
        """
        Pytest hook

        Handle rerun terminal summary report
        Adapted from https://docs.pytest.org/en/latest/skipping.html

        Parameters
        ----------
        terminalreporter : _pytest.terminal.TerminalReporter
        """
        tr = terminalreporter
        if not tr.reportchars:
            return

        lines = []
        for char in tr.reportchars:
            if char in 'rR':
                self._show_rerun(terminalreporter, lines)

        if lines:
            tr._tw.sep("=", "rerun test summary info")
            for line in lines:
                tr._tw.line(line)

        msg = "Performed %s reruns in %2f seconds" % (len(self.tests_to_rerun), self.reruns_time)
        markup = {'yellow': True, "bold": True}
        tr.write_sep("=", msg, **markup)
        if len(self.tests_to_rerun) == 0:
            tr.stats['rerun'] = []

    def _show_rerun(self, terminalreporter, lines):
        """
        Format reruned tests to be market as RERUN in output
        Adapted from https://docs.pytest.org/en/latest/skipping.html

        Parameters
        ----------
        terminalreporter : _pytest.terminal.TerminalReporter
        lines : list[Item]
        """
        rerun = terminalreporter.stats.get("rerun")
        if rerun:
            for rep in rerun:
                pos = rep.nodeid
                lines.append("RERUN %s" % (pos,))

    def _get_reruns_count(self, item):
        """
        Retrive amount of reruns setuped for test item

        Parameters
        ----------
        item : _pytest.main.Item

        Returns
        -------
        reruns : int
        """
        rerun_marker = item.get_marker("flaky")
        reruns = None

        # use the marker as a priority over the global setting.
        if rerun_marker is not None:
            if "reruns" in rerun_marker.kwargs:
                # check for keyword arguments
                reruns = rerun_marker.kwargs["reruns"]
            elif len(rerun_marker.args) > 0:
                # check for arguments
                reruns = rerun_marker.args[0]
            else:
                reruns = 1
        elif item.session.config.option.reruns:
            # default to the global setting
            reruns = item.session.config.option.reruns

        return reruns

    def _get_reruns_delay(self, item):
        """
        Retrive rerun delay setuped for test item

        Parameters
        ----------
        item : _pytest.main.Item

        Returns
        -------
        reruns : int
        """
        rerun_marker = item.get_marker("flaky")

        if rerun_marker is not None:
            if "reruns_delay" in rerun_marker.kwargs:
                delay = rerun_marker.kwargs["reruns_delay"]
            elif len(rerun_marker.args) > 1:
                # check for arguments
                delay = rerun_marker.args[1]
            else:
                delay = 0
        else:
            delay = item.session.config.option.reruns_delay

        if delay < 0:
            delay = 0
            warnings.warn('Delay time between re-runs cannot be < 0. '
                          'Using default value: 0')

        return delay

    def _save_reruns_artifact(self, session):
        """Save reruns artifact as json if path to artifact provided."""
        artifact_path = session.config.option.reruns_artifact_path
        if not artifact_path:
            return

        if self.xdist_worker:
            # Adding xdist worker prefix to filepath to avoid stats overwrite
            path = artifact_path.split('/')
            path[-1] = self.xdist_worker.workerid + '_' + path[-1]
            artifact_path = '/'.join(path)

        with open(artifact_path, 'w') as artifact:
            json.dump(self.rerun_stats, artifact)

    @contextmanager
    def _prepare_xdist(self, item):
        """
        Explicitly changing current working test for xdist worker with rollback
        to keep messaging flow safe
        """
        if self.xdist_worker:
            current_index = self.xdist_worker.item_index
            self.xdist_worker.item_index = self.xdist_worker.session.items.index(item)
            yield
            self.xdist_worker.item_index = current_index
        else:
            yield

class RerunResultLog(ResultLog):
    """ResultLog wrapper for support rerun capabilities"""

    def __init__(self, config, logfile):
        ResultLog.__init__(self, config, logfile)

    def pytest_runtest_logreport(self, report):
        """
        Pytest hook

        Adds support for rerun report fix for issue:
        https://github.com/pytest-dev/pytest-rerunfailures/issues/28

        Parameters
        ----------
        report : _pytest.runner.TestReport
        """
        if report.when != "call" and report.passed:
            return
        res = self.config.hook.pytest_report_teststatus(report=report)
        code = res[1]
        if code == 'x':
            longrepr = str(report.longrepr)
        elif code == 'X':
            longrepr = ''
        elif report.passed:
            longrepr = ""
        elif report.failed:
            longrepr = str(report.longrepr)
        elif report.skipped:
            longrepr = str(report.longrepr[2])
        elif report.outcome == 'rerun':
            longrepr = str(report.longrepr)

        self.log_outcome(report, code, longrepr)

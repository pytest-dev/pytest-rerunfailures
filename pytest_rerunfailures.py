import sys
import copy
import json
import pkg_resources
import time
import warnings
from contextlib import contextmanager

import pytest

from _pytest.resultlog import ResultLog
from _pytest.runner import runtestprotocol
from _pytest.junitxml import LogXML


LOWEST_SUPPORTED_XDIST = '1.23.2'


def works_with_current_xdist():
    """
    Pytest hook

    Returns compatibility with installed pytest-xdist version.

    When running tests in parallel using pytest-xdist < LOWEST_SUPPORTED_XDIST,
    the first report that is logged will finish and terminate the current node rather
    rerunning the test. Thus we must skip logging of intermediate results under
    these circumstances, otherwise no test is rerun.

    Returns
    -------
    result : bool || None
    """
    try:
        d = pkg_resources.get_distribution('pytest-xdist')
        return d.parsed_version >= pkg_resources.parse_version(LOWEST_SUPPORTED_XDIST)
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
        '--xdist-worker-reruns-artifact',
        action='store_true',
        dest='xdist_worker_reruns_artifact',
        default=False,
        help='save artifact for each xdist worker separetly for details'
    )
    group._addoption(
        '--max-tests-rerun',
        action='store',
        dest='max_tests_rerun',
        type=int,
        default=None,
        help='max amount of failures at which reruns would be executed. ' +\
             'If xdist used - max amount of failures per worker' 
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

    if not works_with_current_xdist():
        t_writer = config.pluginmanager.getplugin('terminalreporter')
        # terminalreporter exists only in master process
        if t_writer:
            msg = 'Reruns initialization failure: ' + \
                'Unsupported xdist version. Xdist is supported from %s.' % (
                    LOWEST_SUPPORTED_XDIST
                )
            markup = {'red': True, "bold": True}
            t_writer.write_sep("=", msg, **markup)
        return

    check_options(config)

    # We should treat usual execution/xdist worker execution and xdist master execution differently
    if config.pluginmanager.getplugin('dsession'):
        plugin = XdistRerunsAggregator()
        config.pluginmanager.register(plugin, 'XdistRerunsAggregator')
    else:
        plugin = RerunPlugin()
        config.pluginmanager.register(plugin, 'RerunPlugin')

    # If xmlpath provided to config - junit report will be generated
    # For correct interaction with reruns tests it should be replaced by rerun junit wrapper 
    if config.option.xmlpath:
        log_xml_plugins = [p for p in config.pluginmanager.get_plugins() if isinstance(p, LogXML)]
        if log_xml_plugins:
            junit_plugin = log_xml_plugins[0]
            config.pluginmanager.unregister(plugin=junit_plugin)
            rerun_junit_plugin = RerunLogXML(
                logfile=junit_plugin.logfile,
                prefix=junit_plugin.prefix,
                suite_name=junit_plugin.suite_name,
                logging=junit_plugin.logging
            )
            config.pluginmanager.register(rerun_junit_plugin, 'RerunLogXML')

    resultlog = getattr(config, '_resultlog', None)
    if resultlog:
        logfile = resultlog.logfile
        config.pluginmanager.unregister(resultlog)
        config._resultlog = RerunResultLog(config, logfile)
        config.pluginmanager.register(config._resultlog)


class RerunLogXML(LogXML):

    def reporter_id(self, report):
        # Partially copies self.node_reporter
        nodeid = getattr(report, "nodeid", report)
        # local hack to handle xdist report order
        slavenode = getattr(report, "node", None)
        return (nodeid, slavenode)

    def was_reported(self, report):
        """
        Check if test from report was already tarcked
        """
        return self.reporter_id(report) in self.node_reporters

    def pytest_runtest_logreport(self, report):
        """handle a setup/call/teardown report, generating the appropriate
        xml tags as necessary.
        note: due to plugins like xdist, this hook may be called in interlaced
        order with reports from other nodes. for example:
        usual call order:
            -> setup node1
            -> call node1
            -> teardown node1
            -> setup node2
            -> call node2
            -> teardown node2
        possible call order in xdist:
            -> setup node1
            -> call node1
            -> setup node2
            -> call node2
            -> teardown node2
            -> teardown node1

        Function copies parent implementation with selected rerun status 
        """
        close_report = None
        # Do not report reruns
        if report.outcome == "rerun":
            # If some previous report for current test was tracked - remove it
            if self.was_reported(report):
                reporter = self.node_reporters[self.reporter_id(report)]
                self.node_reporters_ordered.remove(reporter)
                del self.node_reporters[self.reporter_id(report)]
            return
        # Skip finilization if no previous reports were tracked
        elif report.when == "teardown" and not self.was_reported(report):
            return
        # Continue with usual junit flow 
        super(RerunLogXML, self).pytest_runtest_logreport(report)


class RerunStats(object):
    """Represents rerun stats"""

    def __init__(self):
        self._tracked_nodes = {}
        self.rerun_stats = {
            'rerun_tests': [],
            'total_failed': 0,
            'total_reruns': 0,
            'total_resolved_by_reruns': 0
        }

    def _failure_entry(self, nodeid):
        """
        Add failure entry
        We assume that failure for test could appear once per run which mean that
        tests are executed without repetition in main run 
        """
        if nodeid not in self._tracked_nodes:
            self._tracked_nodes[nodeid] = self._stat_entry(nodeid)
            self.rerun_stats['total_failed'] += 1
        return self._tracked_nodes[nodeid]   

    def _rerun_entry(self, nodeid):
        """
        Add rerun entry
        Rerun could be added several times
        """
        if nodeid not in self._tracked_nodes:
            self._tracked_nodes[nodeid] = self._stat_entry(nodeid)
        self.rerun_stats['total_reruns'] += 1
        return self._tracked_nodes[nodeid]   

    def _stat_entry(self, nodeid):
        """Default entry structure"""
        return {
            'nodeid': nodeid,
            'status': 'failed',
            'original_trace': self._test_traces(),
            'rerun_trace': self._test_traces()
        }

    def _test_traces(self):
        """Default traces structures"""
        return {
            'setup': {
                'caplog': '',
                'capstderr': '',
                'capstdout': '',
                'text_repr': ''
            },
            'call': {
                'caplog': '',
                'capstderr': '',
                'capstdout': '',
                'text_repr': ''
            },
            'teardown': {
                'caplog': '',
                'capstderr': '',
                'capstdout': '',
                'text_repr': ''
            }
        }

    def add_failure(self, *reports):
        """
        Add failure appeared during run

        Parameters
        ----------
        reports : list[_pytest.runner.TestReport]
        """
        if not reports:
            return
        failure = self._failure_entry(reports[0].nodeid)
        for report in reports:
            failure['original_trace'][report.when]['caplog'] = report.caplog
            failure['original_trace'][report.when]['capstderr'] = report.capstderr
            failure['original_trace'][report.when]['capstdout'] = report.capstdout
            failure['original_trace'][report.when]['text_repr'] = report.longreprtext

    def add_rerun(self, success, *reports):
        """
        Add failure appeared during run

        Parameters
        ----------
        success : bool
        reports : list[_pytest.runner.TestReport]
        """
        if not reports:
            return
        rerun = self._rerun_entry(reports[0].nodeid)
        self.rerun_stats['total_resolved_by_reruns'] += int(success)
        rerun['status'] = 'flake' if success else 'failed'
        for report in reports:
            rerun['rerun_trace'][report.when]['caplog'] = report.caplog
            rerun['rerun_trace'][report.when]['capstderr'] = report.capstderr
            rerun['rerun_trace'][report.when]['capstdout'] = report.capstdout
            rerun['rerun_trace'][report.when]['text_repr'] = report.longreprtext

    def dump_artifact(self, artifact_path):
        self.rerun_stats['rerun_tests'] = list(self._tracked_nodes.values())
        with open(artifact_path, 'w') as artifact:
            json.dump(self.rerun_stats, artifact)

    def remove_node(self, nodeid):
        node = self._tracked_nodes[nodeid]
        del self._tracked_nodes[nodeid]


class XdistRerunsAggregator(object):
    """Simple rerun stats aggregator aimed to be attached to xdist master process"""

    def __init__(self):
        self.rerun_stats = RerunStats()
        self.failure_rerun_map = {}
        self.reports_aggregation = {}

    def pytest_runtest_logreport(self, report):
        nodeid = report.nodeid
        if report.when == 'setup':
            self.reports_aggregation[nodeid] = [report]
        elif report.when == 'teardown':
            self.reports_aggregation[nodeid].append(report)
            if any([r.outcome == 'rerun' for r in self.reports_aggregation[nodeid]]):
                self.rerun_stats.add_failure(*self.reports_aggregation[nodeid])
                self.failure_rerun_map[nodeid] = False
            elif nodeid in self.failure_rerun_map:
                success = not any([r.failed for r in self.reports_aggregation[nodeid]])
                self.rerun_stats.add_rerun(success, *self.reports_aggregation[nodeid])
                self.failure_rerun_map[nodeid] = not report.restored
        else:
            self.reports_aggregation[nodeid].append(report)

    def pytest_unconfigure(self, config):
        artifact_path = config.option.reruns_artifact_path
        if not artifact_path:
            return

        uncompleted_tests = [i for i, j in  self.failure_rerun_map.items() if not j]
    
        for t in uncompleted_tests:
            self.rerun_stats.remove_node(t)
            self.rerun_stats.rerun_stats['total_failed'] -= 1
            self.rerun_stats.rerun_stats['total_reruns'] -= 1

        self.rerun_stats.dump_artifact(artifact_path)

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


class RerunPlugin(object):
    """Pytest plugin implements rerun failed functionality"""

    def __init__(self):
        self.tests_to_rerun = set([])
        self.rerun_stats = RerunStats()
        # resolving xdist worker object
        self.xdist_worker = next(iter(filter(
            lambda x: x.__class__.__name__ == 'WorkerInteractor',
            pytest.config.pluginmanager.get_plugins()
        )), None)
        self.reruns_time = 0
        self.test_reports = {}

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
            setattr(report, 'restored', False)
            if report.failed and not xfail and reruns > 0:
                # failure detected
                self.tests_to_rerun.add(item)
                report.outcome = 'rerun'

            item.ihook.pytest_runtest_logreport(report=report)

        # Add all related reports to rerun report in case if item failed
        if item in self.tests_to_rerun:
            self.rerun_stats.add_failure(*reports)

        # Last test of a testrun was performed
        if nextitem == None:
            max_tests_reruns = item.config.option.max_tests_rerun
            tests_failed = len(self.tests_to_rerun)
            if max_tests_reruns and max_tests_reruns > 0 and tests_failed > max_tests_reruns:
                self._skip_reruns(
                    max_tests_reruns,
                    item.config.pluginmanager.getplugin("terminalreporter")
                )
                self.rerun_stats = RerunStats()
                self._save_reruns_artifact(item.session)
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
        # terminalreporter exists only in xdist master process
        if not terminalreporter:
            msg = '\n[%s] %s' % (self.xdist_worker.workerid, msg)
            print >> sys.stderr, msg
        else:
            markup = {'red': True, "bold": True}
            terminalreporter.write_sep("=", msg, **markup)

        for item in self.tests_to_rerun:
            with self._prepare_xdist(item):
                for report in self.test_reports[item.nodeid]:
                    setattr(report, 'restored', True)
                    item.ihook.pytest_runtest_logreport(report=report)

        self.tests_to_rerun = []

    def _execute_reruns(self):
        """
        Perform reruns for failed tests
        """
        for item in self.tests_to_rerun:
            self._invalidate_fixtures(item)

        for item in self.tests_to_rerun:
            reruns = self._get_reruns_count(item)
            if reruns is None:
                continue

            with self._prepare_xdist(item):
                self._rerun_item(item, reruns)

    def _rerun_item(self, item, reruns):
        """
        Perform reruns for single test items

        Parameters
        ----------
        item : _pytest.main.Item
        """
        delay = self._get_reruns_delay(item)

        for i in range(reruns):
            time.sleep(delay)
            item.ihook.pytest_runtest_logstart(
                nodeid=item.nodeid, location=item.location
            )

            reports = runtestprotocol(item, nextitem=None, log=False)
            rerun_status = True
            for report in reports:
                xfail = hasattr(report, 'wasxfail')
                report.rerun = i
                rerun_status = rerun_status and (not report.failed or xfail)
                if report.failed and (i != reruns - 1):
                    report.outcome = 'rerun'
                setattr(report, 'restored', False)
                item.ihook.pytest_runtest_logreport(report=report)

            self.rerun_stats.add_rerun(rerun_status, *reports)

            if rerun_status:
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
            if not session.config.option.xdist_worker_reruns_artifact:
                return
            # Adding xdist worker prefix to filepath to avoid stats overwrite
            path = artifact_path.split('/')
            path[-1] = self.xdist_worker.workerid + '_' + path[-1]
            artifact_path = '/'.join(path)

        self.rerun_stats.dump_artifact(artifact_path)

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

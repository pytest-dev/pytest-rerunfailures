import json
from xml.etree import ElementTree

import pytest

pytest_plugins = "pytester"


@pytest.mark.parametrize("distributed", [False, True], ids=["serial", "xdist"])
def test_junitxml_records_only_final_attempts(pytester, monkeypatch, distributed):
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    args = ["-p", "pytest_rerunfailures", "--junitxml=report.xml"]
    if distributed:
        pytest.importorskip("xdist")
        # Exercise worker report forwarding without the crash-recovery socket.
        args += ["-p", "xdist.plugin", "-n", "2"]

    pytester.makeconftest(
        """
        import json
        from collections import defaultdict
        from pathlib import Path

        reports = defaultdict(list)

        def pytest_runtest_logreport(report):
            name = report.nodeid.split('::')[-1]
            reports[name].append((report.when, report.outcome))

        def pytest_sessionfinish(session):
            if not hasattr(session.config, 'workerinput'):
                Path('reports.json').write_text(json.dumps(reports))
        """
    )
    pytester.makepyfile(
        """
        import pytest

        def test_normal():
            pass

        @pytest.mark.flaky(reruns=2)
        def test_eventual_pass(request):
            assert request.node.execution_count == 3

        @pytest.mark.flaky(reruns=2)
        def test_permanent_failure():
            assert False

        @pytest.fixture
        def setup_error():
            raise RuntimeError('setup error')

        @pytest.mark.flaky(reruns=2)
        def test_setup_error(setup_error):
            pass

        @pytest.fixture
        def flaky_teardown(request):
            yield
            assert request.node.execution_count == 3

        @pytest.mark.flaky(reruns=2)
        def test_teardown_retry(flaky_teardown):
            pass
        """
    )

    result = pytester.runpytest_subprocess(*args)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    assert result.parseoutcomes()["rerun"] == 8

    report = ElementTree.parse(pytester.path / "report.xml")  # noqa: S314
    suite = report.find("testsuite")
    assert suite is not None
    assert suite.attrib["tests"] == "5"
    assert suite.attrib["failures"] == suite.attrib["errors"] == "1"
    cases = [(case.attrib["name"], [child.tag for child in case]) for case in suite]
    assert sorted(cases) == [
        ("test_eventual_pass", []),
        ("test_normal", []),
        ("test_permanent_failure", ["failure"]),
        ("test_setup_error", ["error"]),
        ("test_teardown_retry", []),
    ]

    passed = [["setup", "passed"], ["call", "passed"], ["teardown", "passed"]]
    call_rerun = [passed[0], ["call", "rerun"], passed[2]]
    assert json.loads((pytester.path / "reports.json").read_text()) == {
        "test_normal": passed,
        "test_eventual_pass": call_rerun * 2 + passed,
        "test_permanent_failure": call_rerun * 2
        + [passed[0], ["call", "failed"], passed[2]],
        "test_setup_error": [["setup", "rerun"], passed[2]] * 2
        + [["setup", "failed"], passed[2]],
        "test_teardown_retry": [*passed[:2], ["teardown", "rerun"]] * 2 + passed,
    }

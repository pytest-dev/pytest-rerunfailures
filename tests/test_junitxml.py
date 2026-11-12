import json
from xml.etree import ElementTree

import pytest

from pytest_rerunfailures import HAS_PYTEST_HANDLECRASHITEM

pytest_plugins = "pytester"

workers = pytest.mark.parametrize(
    "workers",
    [
        0,
        pytest.param(
            2,
            marks=pytest.mark.skipif(
                not HAS_PYTEST_HANDLECRASHITEM, reason="requires pytest-xdist"
            ),
        ),
    ],
)


def run_junit(pytester, workers, *args):
    parallel = ["-n", str(workers)] if workers else []
    result = pytester.runpytest(
        "-p", "no:randomly", "--junitxml=result.xml", *parallel, *args
    )
    suite = ElementTree.parse(pytester.path / "result.xml").getroot()[0]  # noqa: S314
    return result, suite


@workers
@pytest.mark.parametrize("family", ["xunit1", "xunit2"])
@pytest.mark.parametrize(
    "phase, final_outcome",
    [
        ("call", "passed"),
        ("call", "failed"),
        ("call", "skipped"),
        ("setup", "passed"),
        ("setup", "failed"),
        ("setup", "skipped"),
        ("teardown", "passed"),
        ("teardown", "failed"),
    ],
)
def test_junitxml_only_records_final_attempt(
    pytester, workers, family, phase, final_outcome
):
    pytester.makeconftest(
        f"""
        import pytest

        def fail_attempt(request):
            if request.node.name != "test_flaky":
                return
            if request.node.execution_count < 3 or {final_outcome!r} == "failed":
                pytest.fail("{phase} failure")
            if {final_outcome!r} == "skipped":
                pytest.skip("final attempt skipped")

        @pytest.fixture
        def attempt(request):
            if {phase!r} == "setup":
                fail_attempt(request)
            yield
            if {phase!r} == "teardown":
                fail_attempt(request)
        """
    )
    pytester.makepyfile(
        f"""
        from conftest import fail_attempt

        def test_flaky(request, attempt):
            if {phase!r} == "call":
                fail_attempt(request)

        def test_unrelated():
            pass
        """
    )
    result, suite = run_junit(
        pytester, workers, "--reruns", "2", "-o", f"junit_family={family}"
    )
    assert result.ret == (1 if final_outcome == "failed" else 0)
    cases = suite.findall("testcase")
    assert len(cases) == 2
    by_name = {case.get("name"): case for case in cases}
    assert len(by_name) == 2
    assert len(by_name["test_unrelated"]) == 0
    flaky = by_name["test_flaky"]
    expected_tag = {
        "passed": None,
        "failed": "failure" if phase == "call" else "error",
        "skipped": "skipped",
    }[final_outcome]
    assert [child.tag for child in flaky] == ([expected_tag] if expected_tag else [])
    assert suite.get("failures") == str(int(expected_tag == "failure"))
    assert suite.get("errors") == str(int(expected_tag == "error"))
    assert suite.get("skipped") == str(int(expected_tag == "skipped"))
    # Older pytest versions count a passed call and its failed teardown separately.
    expected_tests = 2
    if phase == "teardown" and final_outcome == "failed":
        assert suite.get("tests") in ("2", "3")
    else:
        assert suite.get("tests") == str(expected_tests)


@workers
def test_junitxml_keeps_final_call_and_teardown_failures(pytester, workers):
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def broken_teardown():
            yield
            pytest.fail("teardown failure")

        def test_failure(broken_teardown):
            pytest.fail("call failure")
        """
    )
    result, suite = run_junit(pytester, workers, "--reruns", "2")
    assert result.ret == 1
    cases = suite.findall("testcase")
    assert len(cases) == 2
    assert sorted(child.tag for case in cases for child in case) == ["error", "failure"]
    # Keep pytest's own counting of a final call failure plus teardown error.
    _, without_reruns = run_junit(pytester, workers, "--reruns", "0")
    assert suite.get("tests") == without_reruns.get("tests")
    assert suite.get("failures") == "1"
    assert suite.get("errors") == "1"


@workers
@pytest.mark.parametrize("duration_report, duration", [("total", 9), ("call", 3)])
def test_junitxml_preserves_duration_output_and_properties(
    pytester, workers, duration_report, duration
):
    pytester.makeconftest(
        """
        import json
        from pathlib import Path
        import pytest

        reports = []

        @pytest.hookimpl(wrapper=True)
        def pytest_runtest_makereport(item, call):
            report = yield
            report.duration = 1.0
            return report

        def pytest_runtest_logreport(report):
            reports.append((report.when, report.outcome, report.rerun))

        def pytest_sessionfinish(session):
            if not hasattr(session.config, "workerinput"):
                Path("reports.json").write_text(json.dumps(reports))
        """
    )
    pytester.makepyfile(
        """
        def test_flaky(request):
            attempt = request.node.execution_count
            request.node.user_properties.append(("attempt", attempt))
            print("attempt", request.node.execution_count)
            assert request.node.execution_count == 3
        """
    )
    result, suite = run_junit(
        pytester,
        workers,
        "--reruns",
        "2",
        "-o",
        f"junit_duration_report={duration_report}",
        "-o",
        "junit_logging=system-out",
    )
    assert result.parseoutcomes() == {"passed": 1, "rerun": 2}
    cases = suite.findall("testcase")
    assert len(cases) == 1
    assert float(cases[0].get("time")) == duration
    assert "attempt 3" in cases[0].find("system-out").text
    properties = cases[0].findall("properties/property")
    assert [(prop.get("name"), prop.get("value")) for prop in properties] == [
        ("attempt", "1"),
        ("attempt", "2"),
        ("attempt", "3"),
    ]
    reports = json.loads((pytester.path / "reports.json").read_text())
    assert reports == [
        ["setup", "passed", 0],
        ["call", "rerun", 0],
        ["teardown", "passed", 0],
        ["setup", "passed", 1],
        ["call", "rerun", 1],
        ["teardown", "passed", 1],
        ["setup", "passed", 2],
        ["call", "passed", 2],
        ["teardown", "passed", 2],
    ]


@pytest.mark.skipif(not HAS_PYTEST_HANDLECRASHITEM, reason="requires pytest-xdist")
def test_junitxml_keeps_same_test_on_each_worker(pytester):
    pytester.makepyfile(
        """
        def test_flaky(request):
            assert request.node.execution_count == 3
        """
    )
    result, suite = run_junit(pytester, 2, "--reruns", "2", "--dist=each")
    assert result.parseoutcomes() == {"passed": 2, "rerun": 4}
    cases = suite.findall("testcase")
    assert len(cases) == 2
    assert [case.get("name") for case in cases] == ["test_flaky", "test_flaky"]
    assert suite.get("tests") == "2"
    assert suite.get("failures") == "0"
    assert suite.get("errors") == "0"


@workers
@pytest.mark.parametrize("reruns", [None, 0])
def test_junitxml_without_reruns(pytester, workers, reruns):
    pytester.makepyfile(
        """
        def test_pass():
            pass

        def test_fail():
            assert False
        """
    )
    args = ["--reruns", str(reruns)] if reruns is not None else []
    result, suite = run_junit(pytester, workers, *args)
    result.assert_outcomes(passed=1, failed=1)
    cases = suite.findall("testcase")
    assert len(cases) == 2
    assert sum(len(case.findall("failure")) for case in cases) == 1
    assert suite.get("tests") == "2"

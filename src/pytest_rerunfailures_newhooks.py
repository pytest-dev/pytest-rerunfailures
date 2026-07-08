"""Hook specifications added by the smith fork of pytest-rerunfailures.

Kept in a dedicated module so ``PluginManager.add_hookspecs`` registers only these
specs and not the plugin's own ``pytest_*`` hook implementations (pytest treats any
``pytest_``-prefixed function in a namespace as a hookspec).
"""

import pytest


@pytest.hookspec(firstresult=True)
def pytest_rerunfailures_rerun_policy(item, report, call):
    """Return a ``RerunPolicy`` for a test's first failure, or ``None`` for default.

    Called once per test, on its first failing report (setup or call). Lets a plugin
    give a specific failure class (e.g. provider-infra errors) its own rerun count /
    semantics and an outcome tag, without affecting how other failures are rerun. The
    first non-None result wins.

    Args:
        item: The test item that failed.
        report: The failing ``TestReport`` (``.when`` is ``"setup"`` or ``"call"``).
        call: The ``CallInfo`` (``call.excinfo`` carries the exception).

    Returns:
        A ``pytest_rerunfailures.RerunPolicy``, or ``None`` for default behavior.
    """

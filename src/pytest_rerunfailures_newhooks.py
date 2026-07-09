"""Hook specifications added by the smith fork of pytest-rerunfailures.

Kept in a dedicated module so ``PluginManager.add_hookspecs`` registers only these
specs and not the plugin's own ``pytest_*`` hook implementations (pytest treats any
``pytest_``-prefixed function in a namespace as a hookspec).
"""

import pytest


@pytest.hookspec(firstresult=True)
def pytest_rerunfailures_rerun_policy(item, report, call):
    """Return a ``RerunPolicy`` for a test's first failure, or ``None`` for default.

    Consulted once per test, on its first failing report (``.when`` may be ``"setup"``,
    ``"call"``, or ``"teardown"``). The returned policy is locked to the item's WHOLE rerun
    sequence -- it is not recomputed on later attempts, so a differently-classed failure on
    a rerun inherits this policy (the rerun count / mode is fixed by the first failure). Lets
    a plugin give a specific failure class (e.g. provider-infra errors) its own rerun count /
    semantics, without affecting how other failures are rerun. The first non-None result wins.

    Args:
        item: The test item that failed.
        report: The first failing ``TestReport`` (``.when`` is ``"setup"``, ``"call"``,
            or ``"teardown"``).
        call: The ``CallInfo`` (``call.excinfo`` carries the exception).

    Returns:
        A ``pytest_rerunfailures.RerunPolicy``, or ``None`` for default behavior.
    """

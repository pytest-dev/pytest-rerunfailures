pytest-rerunfailures
====================

pytest-rerunfailures is a plugin for `py.test <http://pytest.org>`_ that
re-runs tests to eliminate intermittent failures.

.. image:: https://img.shields.io/badge/license-MPL%202.0-blue.svg
   :target: https://github.com/pytest-dev/pytest-rerunfailures/blob/master/LICENSE
   :alt: License
.. image:: https://img.shields.io/pypi/v/pytest-rerunfailures.svg
   :target: https://pypi.python.org/pypi/pytest-rerunfailures/
   :alt: PyPI
.. image:: https://img.shields.io/travis/pytest-dev/pytest-rerunfailures.svg
   :target: https://travis-ci.org/pytest-dev/pytest-rerunfailures/
   :alt: Travis

Requirements
------------

You will need the following prerequisites in order to use pytest-rerunfailures:

- Python 3.5, up to 3.8, or PyPy3
- pytest 5.0 or newer

This package is currently tested against the last 5 minor pytest releases. In
case you work with an older version of pytest you should consider updating or
use one of the earlier versions of this package.

Installation
------------

To install pytest-rerunfailures:

.. code-block:: bash

  $ pip install pytest-rerunfailures

Re-run all failures
-------------------

To re-run all test failures, use the ``--reruns`` command line option with the
maximum number of times you'd like the tests to run:

.. code-block:: bash

  $ pytest --reruns 5

Failed fixture or setup_class will also be re-executed.

To add a delay time between re-runs use the ``--reruns-delay`` command line
option with the amount of seconds that you would like wait before the next
test re-run is launched:

.. code-block:: bash

   $ pytest --reruns 5 --reruns-delay 1

Re-run all failures matching certain expressions
------------------------------------------------

To re-run only those failures that match a certain list of expressions, use the
``--only-rerun`` flag and pass it a regular expression. For example, the following would
only rerun those errors that match ``AssertionError``:

.. code-block:: bash

   $ pytest --reruns 5 --only-rerun AssertionError

Passing the flag multiple times accumulates the arguments, so the following would only rerun
those errors that match ``AssertionError`` or ``ValueError``:

.. code-block:: bash

   $ pytest --reruns 5 --only-rerun AssertionError --only-rerun ValueError

Re-run individual failures
--------------------------

To mark individual tests as flaky, and have them automatically re-run when they
fail, add the ``flaky`` mark with the maximum number of times you'd like the
test to run:

.. code-block:: python

  @pytest.mark.flaky(reruns=5)
  def test_example():
      import random
      assert random.choice([True, False])

Note that when teardown fails, two reports are generated for the case, one for
the test case and the other for the teardown error.

You can also specify the re-run delay time in the marker:

.. code-block:: python

  @pytest.mark.flaky(reruns=5, reruns_delay=2)
  def test_example():
      import random
      assert random.choice([True, False])

Output
------

Here's an example of the output provided by the plugin when run with
``--reruns 2`` and ``-r aR``::

  test_report.py RRF

  ================================== FAILURES ==================================
  __________________________________ test_fail _________________________________

      def test_fail():
  >       assert False
  E       assert False

  test_report.py:9: AssertionError
  ============================ rerun test summary info =========================
  RERUN test_report.py::test_fail
  RERUN test_report.py::test_fail
  ============================ short test summary info =========================
  FAIL test_report.py::test_fail
  ======================= 1 failed, 2 rerun in 0.02 seconds ====================

Note that output will show all re-runs. Tests that fail on all the re-runs will
be marked as failed.

Compatibility
-------------

* This plugin may *not* be used with class, module, and package level fixtures.
* This plugin is *not* compatible with pytest-xdist's --looponfail flag.
* This plugin is *not* compatible with the core --pdb flag.

Resources
---------

- `Issue Tracker <http://github.com/pytest-dev/pytest-rerunfailures/issues>`_
- `Code <http://github.com/pytest-dev/pytest-rerunfailures/>`_

Development
-----------

* Test execution count can be retrieved from the ``execution_count`` attribute in test ``item``'s object. Example:

  .. code-block:: python

    @hookimpl(tryfirst=True)
    def pytest_runtest_makereport(item, call):
        print(item.execution_count)

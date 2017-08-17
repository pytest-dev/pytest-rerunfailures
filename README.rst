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

- Python 2.7, 3.4, 3.5, 3.6, PyPy, or PyPy3
- py.test 2.7.3 or newer

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

  $ py.test --rerun 5

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
be marked as failed. Due to a
`current limitation in pytest-xdist <https://github.com/pytest-dev/pytest/issues/1193>`_,
when running tests in parallel only the final result will be included in the output.

Compatibility
-------------

* This plugin may *not* be used with class, module, and package level fixtures.
* This plugin is *not* compatible with pytest-xdist's --looponfail flag.
* This plugin is *not* compatible with the core --pdb flag.

Resources
---------

- `Issue Tracker <http://github.com/pytest-dev/pytest-rerunfailures/issues>`_
- `Code <http://github.com/pytest-dev/pytest-rerunfailures/>`_

Quickstart
==========

Basic Usage
-----------

To re-run all test failures, use the :option:`--reruns` option with the maximum number of times you'd like the tests to re-run:

.. code-block:: bash

   pytest --reruns 3

This command will execute the test suite, and any failed tests will be retried up to 3 times.

Delay Between Re-runs
---------------------

To add a delay between re-runs, use the :option:`--reruns-delay` option:

.. code-block:: bash

   pytest --reruns 3 --reruns-delay 2

This will retry failed tests up to 3 times with a 2-second delay between each retry.

Re-run Specific Failures
------------------------

To re-run only specific types of failures, use the :option:`--only-rerun` option with a regular expression. For example:

.. code-block:: bash

   pytest --reruns 3 --only-rerun AssertionError

This will re-run failed tests only if they match the error type ``AssertionError``.

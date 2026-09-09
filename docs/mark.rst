Mark Specific Tests as Flaky
============================

The ``@pytest.mark.flaky`` decorator allows you to mark individual tests as flaky and configure them to
automatically re-run a specified number of times upon failure. This is particularly useful for specific tests
that are intermittently failing due to non-deterministic conditions (e.g., network latency, race conditions).
That mark also allows to override global settings specified via :doc:`command-line options </cli>`.

Basic Usage
-----------

To use the ``@pytest.mark.flaky`` decorator, include it in your test function and specify the number of retries using the ``reruns`` argument:

.. code-block:: python

   @pytest.mark.flaky(reruns=3)
   def test_example():
       import random
       assert random.choice([True, False])

In this example, ``test_example`` will automatically re-run up to 3 times if it fails.

Additional Options
------------------

The ``@pytest.mark.flaky`` decorator supports the following optional arguments:

``reruns_delay``
^^^^^^^^^^^^^^^^

Specify a delay (in seconds) between re-runs.

.. code-block:: python

   @pytest.mark.flaky(reruns=5, reruns_delay=2)
   def test_example():
       import random
       assert random.choice([True, False])

This will retry the test 5 times with a 2-second pause between attempts.

``condition``
^^^^^^^^^^^^^

Re-run the test only if a specified condition is met. The condition can be a
boolean, a string to be evaluated, or a callable.

Boolean conditions are evaluated directly:

.. code-block:: python

   import sys

   @pytest.mark.flaky(reruns=3, condition=sys.platform.startswith("win32"))
   def test_example():
       import random
       assert random.choice([True, False])

In this example, the test will only be re-run if the operating system is Windows.

A callable condition that accepts one argument receives the exception that
caused a failed test phase. Existing zero-argument callables remain supported.
This allows a re-run decision to use exception attributes rather than only its
type or message:

.. code-block:: python

   class TemporaryError(Exception):
       def __init__(self, status):
           self.status = status

   @pytest.mark.flaky(
       reruns=3,
       condition=lambda error: error.status in {429, 503},
   )
   def test_service_request():
       raise TemporaryError(429)

A string condition can inspect the same exception through the reserved
``error`` name. Its evaluation context also contains ``os``, ``sys``,
``platform``, ``config`` (the pytest config object), and the test function's
globals:

.. code-block:: python

   @pytest.mark.flaky(reruns=3, condition="error.status in {429, 503}")
   def test_service_request():
       raise TemporaryError(429)

When more than one test phase fails in an attempt, the test is re-run if the
condition matches any of those failures. Each failure is evaluated at most
once. If a callable or string condition raises an exception, pytest emits a
warning and does not re-run for that failure.


``only_rerun``
^^^^^^^^^^^^^^

Re-run the test only for specific exception types or patterns.
That overrides the :option:`--only-rerun` command-line option.

.. code-block:: python

   @pytest.mark.flaky(reruns=5, only_rerun=["AssertionError", "ValueError"])
   def test_example():
       raise AssertionError()

``rerun_except``
^^^^^^^^^^^^^^^^

Exclude specific exception types or patterns from triggering a re-run.
That overrides the :option:`--rerun-except` command-line option.

.. code-block:: python

   @pytest.mark.flaky(reruns=5, rerun_except="AssertionError")
   def test_example():
       raise ValueError()

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

**Boolean condition:**

The simplest condition is a boolean value.

.. code-block:: python

   import sys

   @pytest.mark.flaky(reruns=3, condition=sys.platform.startswith("win32"))
   def test_example():
       import random
       assert random.choice([True, False])

In this example, the test will only be re-run if the operating system is Windows.

**String condition:**

The condition can be a string that will be evaluated. The evaluation context
contains the following objects: ``os``, ``sys``, ``platform``, ``config`` (the
pytest config object), and ``error`` (the exception instance that caused the
test failure).

.. code-block:: python

   class MyError(Exception):
       def __init__(self, code):
           self.code = code

   @pytest.mark.flaky(reruns=2, condition="error.code == 123")
   def test_fail_with_my_error():
       raise MyError(123)

**Callable condition:**

The condition can be a callable (e. g., a function or a lambda) that will be
passed the exception instance that caused the test failure. The test will be
rerun only if the callable returns ``True``.

.. code-block:: python

   def should_rerun(err):
       return isinstance(err, ValueError)

   @pytest.mark.flaky(reruns=2, condition=should_rerun)
   def test_fail_with_value_error():
       raise ValueError("some error")

   @pytest.mark.flaky(reruns=2, condition=lambda e: isinstance(e, NameError))
   def test_fail_with_name_error():
       raise NameError("some other error")

If the callable itself raises an exception, it will be caught, a warning
will be issued, and the test will not be rerun.


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

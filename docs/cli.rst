Command Line Interface Options
==============================

.. option:: --only-rerun

   **Description**:
       Specify regex patterns for errors to rerun. Use this option multiple times to accumulate a list of regexes.

   **Type**:
       String (repeatable)

   **Default**:
       None

   **Example**:
       .. code-block:: bash

           pytest --only-rerun AssertionError --only-rerun ValueError

.. option:: --reruns

   **Description**:
       The number of times to rerun failing tests.

   **Type**:
       Integer

   **Default**:
       Not set (must be provided)

   **Example**:
       .. code-block:: bash

           pytest --reruns 5

.. option:: --reruns-delay

   **Description**:
       Delay in seconds between reruns.

   **Type**:
       Float

   **Default**:
       Not set (must be provided)

   **Example**:
       .. code-block:: bash

           pytest --reruns 5 --reruns-delay 1

.. option:: --rerun-except

   **Description**:
       Specify regex patterns for errors to exclude from reruns. Use this option multiple times to accumulate a list of regexes.

   **Type**:
       String (repeatable)

   **Default**:
       None

   **Example**:
       .. code-block:: bash

           pytest --reruns 5 --rerun-except AssertionError --rerun-except OSError

.. option:: --fail-on-flaky

   **Description**:
       If set, the test run will fail with exit code 7 if a flaky test passes on rerun.

   **Type**:
       Boolean flag

   **Default**:
       False

   **Example**:
       .. code-block:: bash

           pytest --fail-on-flaky

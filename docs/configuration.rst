Configuration
=============

The ``pytest.ini`` configuration file allows you to set default values for the plugin's options,
enabling a consistent test execution environment without the need to specify :doc:`command-line options </cli>` every time.

Available ``pytest.ini`` Options
--------------------------------

Below are the ``pytest.ini`` options supported by the plugin:

``reruns``
^^^^^^^^^^

- **Description**: Sets the default number of times to rerun failed tests. If not set, you must provide the :option:`--reruns` option on the command line.
- **Type**: String
- **Default**: Not set (must be provided as a CLI argument if not configured).
- **Example**:

  .. code-block:: ini

     [pytest]
     reruns = 3

``reruns_delay``
^^^^^^^^^^^^^^^^

- **Description**: Sets the default delay (in seconds) between reruns of failed tests.
- **Type**: String
- **Default**: Not set (optional).
- **Example**:

  .. code-block:: ini

     [pytest]
     reruns_delay = 2.5

Example
-------

To configure your test environment for consistent retries and delays, add the following options to your ``pytest.ini`` file:

.. code-block:: ini

   [pytest]
   reruns = 3
   reruns_delay = 2.0

This setup ensures that:

- Failed tests will be retried up to 3 times.
- There will be a 2-second delay between each retry.

Overriding ``pytest.ini`` Options
---------------------------------

Command-line arguments always override ``pytest.ini`` settings. For example:

.. code-block:: bash

   pytest --reruns 5 --reruns-delay 1.5

This will retry tests 5 times with a 1.5-second delay, regardless of the values set in ``pytest.ini``.

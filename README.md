pytest-rerunfailures
====================

a py.test plugin that re-runs failed tests up to -n times to eliminate flakey failures

Notes:
======

    when teardown fails, two reports are generated for the case, one for the test
    case and the other for the teardown error.

    in some versions of py.test, when setup fails on a test that has been marked with xfail, 
    it gets an XPASS rather than an XFAIL 
    (https://bitbucket.org/hpk42/pytest/issue/160/an-exception-thrown-in)
    fix should be released in version 2.2.5

Expected Results for test run
=============================

running the plugin's tests with --reruns=1
    py.test -p "no:mozwebqa" --reruns=1 -v tests/
should result in:
    platform darwin -- Python 2.6.1 -- pytest-2.2.4 -- /usr/bin/python
    collected 7 items 

    tests/test_method_states.py:8: TestMethodStates.test_method_passes PASSED
    tests/test_method_states.py:11: TestMethodStates.test_method_fails xfail
    tests/test_method_states.py:16: TestMethodStates.test_method_flakey FAILED
    tests/setup/test_flakey_setup.py:6: TestFlakeySetup.test_flakey_setup ERROR
    tests/setup/fail/test_setup_failures.py:6: TestSetupFailure.test_setup_failure XPASS
    tests/teardown/fail/test_teardown_failures.py:7: TestTeardownFailure.test_teardown_failure PASSED
    tests/teardown/fail/test_teardown_failures.py:7: TestTeardownFailure.test_teardown_failure ERROR
    tests/teardown/flakey/test_flkey_teardown.py:7: TestFlakeyTeardown.test_flakey_teardown PASSED
    tests/teardown/flakey/test_flkey_teardown.py:7: TestFlakeyTeardown.test_flakey_teardown ERROR

running the plugin's tests with --reruns=2 (or greater)
    py.test -p "no:mozwebqa" --reruns=2 -v tests/
should result in:
    ======================================= test session starts =======================================
    platform darwin -- Python 2.6.1 -- pytest-2.2.4 -- /usr/bin/python
    collected 7 items 

    tests/test_method_states.py:8: TestMethodStates.test_method_passes PASSED
    tests/test_method_states.py:11: TestMethodStates.test_method_fails xfail
    tests/test_method_states.py:16: TestMethodStates.test_method_flakey PASSED
    tests/setup/test_flakey_setup.py:6: TestFlakeySetup.test_flakey_setup PASSED
    tests/setup/fail/test_setup_failures.py:6: TestSetupFailure.test_setup_failure XPASS
    tests/teardown/fail/test_teardown_failures.py:7: TestTeardownFailure.test_teardown_failure PASSED
    tests/teardown/fail/test_teardown_failures.py:7: TestTeardownFailure.test_teardown_failure ERROR
    tests/teardown/flakey/test_flkey_teardown.py:7: TestFlakeyTeardown.test_flakey_teardown PASSED
    tests/teardown/flakey/test_flkey_teardown.py:7: TestFlakeyTeardown.test_flakey_teardown ERROR



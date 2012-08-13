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

    The tests for this plugin may not be run with the pytest-mozwebqa plugin installed.
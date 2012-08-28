pytest-rerunfailures
====================

A py.test plugin that re-runs failed tests up to X times to eliminate flakey failures

Installation:
============
    (sudo) pip install git+https://github.com/klrmn/pytest-rerunfailures.git

Parameters:
===========
* --reruns=N    reruns failing tests N times (default 0)
* --verbose     lists which tests were rerun
* -q            supresses rerun count report

Notes:
======

When teardown fails, two reports are generated for the case, one for the test
case and the other for the teardown error.

In some versions of py.test, when setup fails on a test that has been marked with xfail, 
it gets an XPASS rather than an XFAIL 
(https://bitbucket.org/hpk42/pytest/issue/160/an-exception-thrown-in)
fix should be released in version 2.2.5

Compatibility:
==============

While this plugin is compatible with pytest-mozwebqa, the tests for this plugin may not be run with the pytest-mozwebqa plugin installed.

This plugin is *not* compatible with pytest-xdist's --looponfail flag.

This plugin is also not compatible with the core --pdb flag.

Continuous Integration
----------------------
[![Build Status](https://secure.travis-ci.org/klrmn/pytest-rerunfailures.png?branch=master)](http://travis-ci.org/klrmn/pytest-rerunfailures)

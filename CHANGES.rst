===================================
Change log for pytest-rerunfailures
===================================


1.0.0 (unreleased)
==================

- Rewrite to use newer API of pytest >= 2.3.0

- Improve support for pytest-xdist by only logging the final result.
  (Logging intermediate results will finish the test rather rerunning it.)
Changelog
---------


2.0.0 (2016-04-06)
==================

- Drop support for Python 3.2, since supporting it became too much of a hassle.
  (Reason: Virtualenv 14+ / PIP 8+ do not support Python 3.2 anymore.)

1.0.2 (2016-03-29)
==================

- Add support for `--resultlog` option by parsing reruns accordingly. (#28)


1.0.1 (2016-02-02)
==================

- Improve package description and include CHANGELOG into description.


1.0.0 (2016-02-02)
==================

- Rewrite to use newer API of pytest >= 2.3.0

- Improve support for pytest-xdist by only logging the final result.
  (Logging intermediate results will finish the test rather rerunning it.)
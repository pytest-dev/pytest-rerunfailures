Changelog
---------


4.1 (2018-05-23)
================

- Add support for pytest 3.6 by using ``Node.get_closest_marker()`` (Thanks to
  `@The-Compiler`_ for the PR).

.. _@The-Compiler: https://github.com/The-Compiler

4.0 (2017-12-23)
================

- Added option to add a delay time between test re-runs (Thanks to `@Kanguros`_
  for the PR).

- Added support for pytest >= 3.3.

- Drop support for pytest < 2.8.7.

.. _@Kanguros: https://github.com/Kanguros


3.1 (2017-08-29)
================

- Restored compatibility with pytest-xdist. (Thanks to `@davehunt`_ for the PR)

.. _@davehunt: https://github.com/davehunt


3.0 (2017-08-17)
================

- Add support for Python 3.6.

- Add support for pytest 2.9 up to 3.2

- Drop support for Python 2.6 and 3.3.

- Drop support for pytest < 2.7.


2.2 (2017-06-23)
================

- Ensure that other plugins can run after this one, in case of a global setting
  ``--rerun=0``. (Thanks to `@sublee`_ for the PR)

.. _@sublee: https://github.com/sublee

2.1.0 (2016-11-01)
==================

- Add default value of ``reruns=1`` if ``pytest.mark.flaky()`` is called
  without arguments.

- Also offer a distribution as universal wheel. (Thanks to `@tltx`_ for the PR)

.. _@tltx: https://github.com/tltx


2.0.1 (2016-08-10)
==================

- Prepare CLI options to pytest 3.0, to avoid a deprecation warning.

- Fix error due to missing CHANGES.rst when creating the source distribution
  by adding a MANIFEST.in.


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

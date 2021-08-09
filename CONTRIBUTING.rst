============================
Contribution getting started
============================

Contributions are highly welcomed and appreciated.
Every little bit of help counts, so do not hesitate!

.. contents::
   :depth: 2
   :backlinks: none


Preparing Pull Requests
-----------------------

#. Fork the repository.

#. Enable and install `pre-commit <https://pre-commit.com>`_ to ensure style-guides and code checks are followed::

   $ pip install --user pre-commit
   $ pre-commit install

   Afterwards ``pre-commit`` will run whenever you commit.

   Note that this is automatically done when running ``tox -e linting``.

   https://pre-commit.com/ is a framework for managing and maintaining multi-language pre-commit hooks
   to ensure code-style and code formatting is consistent.

#. Install `tox <https://tox.readthedocs.io/en/latest/>`_:

   Tox is used to run all the tests and will automatically setup virtualenvs
   to run the tests in. Implicitly https://virtualenv.pypa.io/ is used::

    $ pip install tox
    $ tox -e linting,py37

#. Follow **PEP-8** for naming and `black <https://github.com/psf/black>`_ for formatting.

#. Add a line item to the current **unreleased** version in ``CHANGES.rst``,
   unless the change is trivial.

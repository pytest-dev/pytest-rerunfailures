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

   tox is used to run all the tests and will automatically setup virtualenvs
   to run the tests in. Implicitly https://virtualenv.pypa.io/ is used::

    $ pip install tox
    $ tox -e linting,py312

#. Follow **PEP 8** for naming and `black <https://github.com/psf/black>`_ for formatting.

#. Add a change log entry, unless the change is trivial. Do **not** edit
   ``CHANGES.rst`` -- it is generated at release time. Instead create a file in
   the ``changes/`` directory named after the GitHub issue or pull request
   number, with an extension naming the kind of change, for example
   ``changes/270.bugfix.rst``. See `changes/README.rst
   <https://github.com/pytest-dev/pytest-rerunfailures/blob/master/changes/README.rst>`_
   for the available types and the expected style.


Making a release
----------------

Releases are made with `zest.releaser
<https://zestreleaser.readthedocs.io/>`_ together with the
``zestreleaser.towncrier`` plugin, which runs ``towncrier build`` at the right
moment so ``CHANGES.rst`` is assembled from the files in ``changes/``::

    $ pip install --group release
    $ fullrelease

``pip install --group release`` requires pip 25.1 or newer; with an older pip
use ``pip install "zest.releaser[recommended]" zestreleaser.towncrier``
instead.

To preview the change log for the next release without writing anything::

    $ towncrier build --draft --version 17.0

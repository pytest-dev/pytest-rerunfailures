from setuptools import setup

setup(name='pytest-rerunfailures',
      version='2.0.0',
      description='pytest plugin to re-run tests to eliminate flaky failures',
      long_description=(
          open('README.rst').read() +
          '\n\n' +
          open('CHANGES.rst').read()),
      author='Leah Klearman',
      author_email='lklrmn@gmail.com',
      url='https://github.com/pytest-dev/pytest-rerunfailures',
      py_modules=['pytest_rerunfailures'],
      entry_points={'pytest11': ['rerunfailures = pytest_rerunfailures']},
      install_requires=['pytest >= 2.4.2'],
      license='Mozilla Public License 2.0 (MPL 2.0)',
      keywords='py.test pytest rerun failures flaky',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Framework :: Pytest',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
          'Operating System :: POSIX',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: MacOS :: MacOS X',
          'Topic :: Software Development :: Quality Assurance',
          'Topic :: Software Development :: Testing',
          'Topic :: Utilities',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
      ])

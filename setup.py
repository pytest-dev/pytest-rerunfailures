from setuptools import setup

test_deps = [
    'xmltodict==0.11.0',
    'pytest<7',
    'pytest-xdist==1.23.2',
    'pytest-forked==1.0.1',
    'py',
]

release_deps = [
    'twine>=1.6.5,<=1.11.0',
]

setup(name='pytest-rerunfailures',
      version='4.1.dr8',
      description='pytest plugin to re-run tests with fixture invalidation to eliminate flaky failures',
      long_description=(
          open('README.rst').read() +
          '\n\n' +
          open('CHANGES.rst').read()),
      author='Leah Klearman, DataRobot',
      url='https://github.com/datarobot/pytest-rerunfailures',
      py_modules=['pytest_rerunfailures'],
      entry_points={'pytest11': ['rerunfailures = pytest_rerunfailures']},
      install_requires=['pytest>=3.5<7', 'mock>=1.0.1'],
      tests_require=test_deps,
      extras_require={
          'test': test_deps,
          'dev': test_deps + release_deps
        },
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
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: Implementation :: CPython',
          'Programming Language :: Python :: Implementation :: PyPy',
      ])

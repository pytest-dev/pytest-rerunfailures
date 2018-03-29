from setuptools import setup

setup(name='pytest-cleanrerun',
      version='0.9',
      description='pytest plugin to re-run tests with fixture invalidation to eliminate flaky failures',
      long_description=(
          open('README.rst').read() +
          '\n\n' +
          open('CHANGES.rst').read()),
      author='Leah Klearman, DataRobot',
      url='https://github.com/datarobot/pytest-rerunfailures',
      py_modules=['pytest-cleanrerun'],
      entry_points={'pytest11': ['cleanrerun = pytest_cleanrerun']},
      install_requires=['pytest >= 2.8.7'],
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

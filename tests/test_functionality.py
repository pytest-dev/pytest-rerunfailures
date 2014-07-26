import py, pytest


class TestFunctionality(object):

    pass_the_third_time = """
                import os
                import py
                path = py.path.local(__file__).dirpath().ensure('test.res')
                state = path.read()

                print path, state

                if state == '':
                    path.write('fail')
                    raise Exception("Failing the first time")
                elif state == 'fail':
                    path.write('pass')
                    raise Exception("Failing the second time")
                elif state == 'pass':
                    path.remove() # delete the file
                    return  # pass the method
                else:
                    raise Exception("unexpected data in file %s: %s" % (filename, state))
    """

    passing_test = """
            import pytest
            @pytest.mark.nondestructive
            def test_fake_pass():
                assert True
        """

    failing_test = """
            import pytest
            @pytest.mark.nondestructive
            def test_fake_fail():
                raise Exception("OMG! failing test!")
        """

    skipped_test = """
            import pytest
            @pytest.mark.skipIf(True)
            def test_skip():
                assert False
        """

    flakey_test = """
            import pytest
            @pytest.mark.nondestructive
            def test_flaky_test():
    """ + pass_the_third_time
    
    flaky_test_with_1xmarker = """
            import pytest
            @pytest.mark.nondestructive
            @pytest.mark.flaky(reruns=1)
            def test_flaky_test_with_marker():
    """ + pass_the_third_time
    
    flaky_test_with_2xmarker = """
            import pytest
            @pytest.mark.nondestructive
            @pytest.mark.flaky(reruns=2)
            def test_flaky_test_with_marker():
    """ + pass_the_third_time

    flakey_setup_conftest = """
        import py, pytest
        def pytest_runtest_setup(item):
        """ + pass_the_third_time

    failing_setup_conftest = """
            import py, pytest
            def pytest_runtest_setup(item):
                raise Exception("OMG! setup failure!")
        """

    flakey_teardown_conftest = """
        import py, pytest
        def pytest_runtest_teardown(item):
        """ + pass_the_third_time

    failing_teardown_conftest = """
        import py, pytest
        def pytest_runtest_teardown(item):
            raise Exception("OMG! teardown failure!")
        """

    # passing tests
    def test_can_pass_with_reruns_enabled(self, testdir):
        test_file = testdir.makepyfile(self.passing_test)

        reprec = testdir.inline_run('--reruns=2', test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 0
        assert len(skipped) == 0
        assert len(passed) == 1

    def test_can_pass_with_reruns_disabled(self, testdir):
        test_file = testdir.makepyfile(self.passing_test)

        reprec = testdir.inline_run(test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 0
        assert len(skipped) == 0
        assert len(passed) == 1

    def test_skipped_test_not_rerun(self, testdir):
        test_file = testdir.makepyfile(self.skipped_test)

        reprec = testdir.inline_run(test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 0
        assert len(skipped) == 1
        assert len(passed) == 0

    # setup
    def test_fails_with_flakey_setup_if_rerun_not_used(self, testdir):
        test_file = testdir.makepyfile(self.passing_test)
        conftest_file = testdir.makeconftest(self.flakey_setup_conftest)

        reprec = testdir.inline_run(test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'Exception: Failing the first time'

    def test_fails_with_flakey_setup_if_rerun_only_once(self, testdir):
        test_file = testdir.makepyfile(self.passing_test)
        conftest_file = testdir.makeconftest(self.flakey_setup_conftest)

        reprec = testdir.inline_run('--reruns=1', test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'Exception: Failing the second time'

    def test_passes_with_flakey_setup_if_run_two_times(self, testdir):
        test_file = testdir.makepyfile(self.passing_test)
        conftest_file = testdir.makeconftest(self.flakey_setup_conftest)

        reprec = testdir.inline_run('--reruns=2', test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(passed) == 1

    def test_fails_with_failing_setup_even_if_rerun_three_times(self, testdir):
        test_file = testdir.makepyfile(self.passing_test)
        conftest_file = testdir.makeconftest(self.failing_setup_conftest)

        reprec = testdir.inline_run('--reruns=3', test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'Exception: OMG! setup failure!'

    # the test itself
    def test_flaky_test_fails_if_rerun_not_used(self, testdir):
        test_file = testdir.makepyfile(self.flakey_test)

        reprec = testdir.inline_run(test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'Exception: Failing the first time'

    def test_flaky_test_fails_if_run_only_once(self, testdir):
        test_file = testdir.makepyfile(self.flakey_test)

        reprec = testdir.inline_run('--reruns=1', test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'Exception: Failing the second time'
        
    def test_flaky_test_with_1x_marker(self, testdir):
        test_file = testdir.makepyfile(self.flaky_test_with_1xmarker)

        reprec = testdir.inline_run(test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        #
        # result = testdir.runpytest(test_file)
        # assert u'E           Exception: Failing the first time' in result.outlines
        
    def test_flaky_test_with_2x_marker(self, testdir):
        test_file = testdir.makepyfile(self.flaky_test_with_2xmarker)

        reprec = testdir.inline_run(test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(passed) == 1
        
    def test_flakey_test_passes_if_run_two_times(self, testdir):
        test_file = testdir.makepyfile(self.flakey_test)

        reprec = testdir.inline_run('--reruns=2', test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(passed) == 1

    def test_failing_test_fails_if_rerun_three_times(self, testdir):
        test_file = testdir.makepyfile(self.failing_test)

        reprec = testdir.inline_run('--reruns=3', test_file)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'Exception: OMG! failing test!'

    # teardown

    ### Tests are no longer re-run if their teardown fails, but their setup and call pass

    # reporting using -r R
    def variety_of_tests(self, testdir):
        tests = testdir.makepyfile("""
            import pytest

            @pytest.mark.nondestructive
            def test_fake_pass():
                pass

            @pytest.mark.nondestructive
            def test_fake_fail():
                raise Exception, "OMG! fake test failure!"

            @pytest.mark.nondestructive
            @pytest.mark.xfail(reason="this will fail")
            def test_xfail():
                raise Exception("OMG! failing test!")

            @pytest.mark.xfail(reason="this will pass")
            @pytest.mark.nondestructive
            def test_xpass():
                pass

            @pytest.mark.nondestructive
            @pytest.mark.skipIf(True)
            def test_skip():
                assert False

            @pytest.mark.nondestructive
            def test_flaky_test():
            """ + self.pass_the_third_time
        )

    # flakey test reporting
    def test_report_off_with_reruns(self, testdir):
        test_file = self.variety_of_tests(testdir)

        result = testdir.runpytest('--reruns=2')

        assert self._substring_in_output('.FxXR', result.outlines)

        assert self._substring_in_output('1 passed', result.outlines)

        assert self._substring_in_output('1 failed', result.outlines)
        assert not self._substring_in_output('FAIL test_report_off_with_reruns.py::test_fake_fail', result.outlines)

        assert self._substring_in_output('1 xpassed', result.outlines)
        assert not self._substring_in_output('XPASS test_report_off_with_reruns.py::test_xpass', result.outlines)

        assert self._substring_in_output('1 xfailed', result.outlines)
        assert not self._substring_in_output('XFAIL test_report_off_with_reruns.py::test_xfail', result.outlines)

        assert not self._substring_in_output('RERUN test_report_off_with_reruns.py::test_flaky_test', result.outlines)
        assert self._substring_in_output('1 rerun', result.outlines)

    def test_report_on_with_reruns(self, testdir):
        test_file = self.variety_of_tests(testdir)

        result = testdir.runpytest('--reruns=2', '-r fsxXR')

        assert self._substring_in_output('.FxXR', result.outlines)

        assert self._substring_in_output(' 1 passed', result.outlines)

        assert self._substring_in_output('1 failed', result.outlines)
        assert self._substring_in_output('FAIL test_report_on_with_reruns.py::test_fake_fail', result.outlines)

        assert self._substring_in_output('1 xpassed', result.outlines)
        assert self._substring_in_output('XPASS test_report_on_with_reruns.py::test_xpass', result.outlines)

        assert self._substring_in_output('1 xfailed', result.outlines)
        assert self._substring_in_output('XFAIL test_report_on_with_reruns.py::test_xfail', result.outlines)

        assert self._substring_in_output('1 rerun', result.outlines)
        assert self._substring_in_output('RERUN test_report_on_with_reruns.py::test_flaky_test', result.outlines)

    def test_report_on_without_reruns(self, testdir):
        test_file = self.variety_of_tests(testdir)

        result = testdir.runpytest('-r fsxX')

        assert self._substring_in_output('.FxXF', result.outlines)

        assert self._substring_in_output(' 1 passed', result.outlines)

        assert self._substring_in_output('2 failed', result.outlines)
        assert self._substring_in_output('FAIL test_report_on_without_reruns.py::test_fake_fail', result.outlines)
        assert self._substring_in_output('FAIL test_report_on_without_reruns.py::test_flaky_test', result.outlines)

        assert self._substring_in_output('1 xpassed', result.outlines)
        assert self._substring_in_output('XPASS test_report_on_without_reruns.py::test_xpass', result.outlines)

        assert self._substring_in_output('1 xfailed', result.outlines)
        assert self._substring_in_output('XFAIL test_report_on_without_reruns.py::test_xfail', result.outlines)

        assert not self._substring_in_output('RERUN test_report_on_without_reruns.py::test_flaky_test', result.errlines)
        assert not self._substring_in_output('1 rerun', result.outlines)

    def test_verbose_statuses_with_reruns(self, testdir):
        test_file = self.variety_of_tests(testdir)

        result = testdir.runpytest('--reruns=2', '--verbose')

        assert self._substring_in_output(' 1 passed', result.outlines)
        assert self._substring_in_output('test_verbose_statuses_with_reruns.py:3: test_fake_pass PASSED', result.outlines)

        assert self._substring_in_output('1 failed', result.outlines)
        assert self._substring_in_output('test_verbose_statuses_with_reruns.py:7: test_fake_fail FAILED', result.outlines)

        assert self._substring_in_output('1 xpassed', result.outlines)
        assert self._substring_in_output('test_verbose_statuses_with_reruns.py:16: test_xpass XPASS', result.outlines)

        assert self._substring_in_output('1 xfailed', result.outlines)
        assert self._substring_in_output('test_verbose_statuses_with_reruns.py:11: test_xfail xfail', result.outlines)

        assert self._substring_in_output('1 rerun', result.outlines)
        assert self._substring_in_output('test_verbose_statuses_with_reruns.py:21: test_flaky_test RERUN', result.outlines)

    def test_report_off_with_reruns_with_xdist(self, testdir):
        '''This test is identical to test_report_off_with_reruns except it
        also uses xdist's -n flag.
        '''
        # precondition: xdist installed
        self._pytest_xdist_installed(testdir)

        test_file = self.variety_of_tests(testdir)

        result = testdir.runpytest('--reruns=2', '-n 1')

        assert self._substring_in_output('.FxXR', result.outlines)

        assert self._substring_in_output('1 passed', result.outlines)

        assert self._substring_in_output('1 failed', result.outlines)
        assert not self._substring_in_output('FAIL test_report_off_with_reruns_with_xdist.py::test_fake_fail', result.outlines)

        assert self._substring_in_output('1 xpassed', result.outlines)
        assert not self._substring_in_output('XPASS test_report_off_with_reruns_with_xdist.py::test_xpass', result.outlines)

        assert self._substring_in_output('1 xfailed', result.outlines)
        assert not self._substring_in_output('XFAIL test_report_off_with_reruns_with_xdist.py::test_xfail', result.outlines)

        assert not self._substring_in_output('RERUN test_report_off_with_reruns_with_xdist.py::test_flaky_test', result.outlines)
        assert self._substring_in_output('1 rerun', result.outlines)

    def test_report_on_with_reruns_with_xdist(self, testdir):
        '''This test is identical to test_report_on_with_reruns except it
        also uses xdist's -n flag.
        '''
        # precondition: xdist installed
        self._pytest_xdist_installed(testdir)

        test_file = self.variety_of_tests(testdir)

        result = testdir.runpytest('--reruns=2', '-r fsxXR', '-n 1')

        assert self._substring_in_output('.FxXR', result.outlines)

        assert self._substring_in_output(' 1 passed', result.outlines)

        assert self._substring_in_output('1 failed', result.outlines)
        assert self._substring_in_output('FAIL test_report_on_with_reruns_with_xdist.py::test_fake_fail', result.outlines)

        assert self._substring_in_output('1 xpassed', result.outlines)
        assert self._substring_in_output('XPASS test_report_on_with_reruns_with_xdist.py::test_xpass', result.outlines)

        assert self._substring_in_output('1 xfailed', result.outlines)
        assert self._substring_in_output('XFAIL test_report_on_with_reruns_with_xdist.py::test_xfail', result.outlines)

        assert self._substring_in_output('1 rerun', result.outlines)
        assert self._substring_in_output('RERUN test_report_on_with_reruns_with_xdist.py::test_flaky_test', result.outlines)


    def _pytest_xdist_installed(self, testdir):
        try:
            result = testdir.runpytest('--version')
            result.stderr.fnmatch_lines(['*pytest-xdist*'])
        except Exception:
            import pytest
            pytest.skip("this test requires pytest-xdist")

    def _substring_in_output(self, substring, output_lines):
        print '-' * 30
        found = False
        for line in output_lines:
            if substring in line:
                print "'%s' matched: %s" % (substring, line)
                found = True
        if not found:
            print "'%s' not found in:\n\t%s" % (substring, "\n\t".join(output_lines))
        return found


if __name__ == '__main__':
    pytest.cmdline.main(args=[os.path.abspath(__file__)])

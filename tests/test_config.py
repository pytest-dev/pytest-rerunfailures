import py, pytest


class TestConfig(object):

    passing_test = """
            import pytest
            @pytest.mark.nondestructive
            def test_fake_pass():
                assert True
        """
 
    @pytest.mark.xfail(reason="don't know where to put check so that it is testable. manually, the test passes.")
    def test_reruns_incompatible_with_pdb(self, testdir):
        file_test = testdir.makepyfile(self.passing_test)
        reprec = testdir.inline_run('--reruns=3',
                                    '--pdb',
                                    file_test)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'ERROR: --reruns incompatible with --pdb'


    def test_reruns_incompatible_with_looponfail(self, testdir):
        pytest.skip("-xdist highjacks process before my plugin can test command line options")
        file_test = testdir.makepyfile(self.passing_test)
        reprec = testdir.inline_run('--reruns=3',
                                    '--looponfail',
                                    file_test)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'ERROR: --reruns incompatible with --looponfail'

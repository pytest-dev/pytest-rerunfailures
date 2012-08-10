import py, pytest

from tests.base import BaseTest

class TestConfig(BaseTest):

    pytest_plugins = 'pytester'

    def test_reruns_incompatible_with_pdb(self, tmpdir):
        file_test = tmpdir.makepyfile("""
            import pytest
            @pytest.mark.nondestructive
            def test_selenium(mozwebqa):
            assert True
        """)
        reprec = tmpdir.inline_run('--reruns=3',
                                    '--pdb',
                                    file_test)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'UsageError: --reruns incompatible with --pdb'


    def test_reruns_incompatible_with_looponfail(self, tmpdir):
        file_test = tmpdir.makepyfile("""
            import pytest
            @pytest.mark.nondestructive
            def test_selenium(mozwebqa):
            assert True
        """)
        reprec = tmpdir.inline_run('--reruns=3',
                                    '--pdb',
                                    file_test)
        passed, skipped, failed = reprec.listoutcomes()
        assert len(failed) == 1
        out = failed[0].longrepr.reprcrash.message
        assert out == 'UsageError: --reruns incompatible with --looponfail'

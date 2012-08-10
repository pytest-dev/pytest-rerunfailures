import py, pytest


class TestFlakeyTeardown(object):

    # @pytest.mark.xfail(reason="may fail if --rerun is less than 3")
    def test_flakey_teardown(self):
        pass
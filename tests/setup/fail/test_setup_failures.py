import py, pytest


class TestSetupFailure(object):

    @pytest.mark.xfail(reason="intended to fail")
    def test_setup_failure(self):
        pass
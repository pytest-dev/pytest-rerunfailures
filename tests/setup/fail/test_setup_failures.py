import py, pytest

from tests.base import BaseTest


class TestSetupFailure(BaseTest):

    @pytest.mark.xfail(reason="intended to fail")
    def test_setup_failure(self):
        pass
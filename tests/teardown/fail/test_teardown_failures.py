import py, pytest

from tests.base import BaseTest

class TestTeardownFailure(BaseTest):

    # @pytest.mark.xfail(reason="intended to fail")
    def test_teardown_failure(self):
        pass
import py, pytest

from tests.base import BaseTest

class TestFlakeyTeardown(BaseTest):

    @pytest.mark.destructive
    def test_flakey_teardown(self):
        pass
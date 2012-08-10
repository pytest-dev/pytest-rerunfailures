import py, pytest
import time

from base import BaseTest

class TestMethodStates(BaseTest):

    def test_method_passes(self):
        pass

    @pytest.mark.xfail(reason="intended to fail")
    def test_method_fails(self):
        self.failing_method()

    # @pytest.mark.xfail(reason="may fail if --rerun is less than 3")
    def test_method_flakey(self):
        self.pass_the_third_time('test_method_flakey')
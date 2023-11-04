from unittest import TestCase

from utils import loghelper
from utils.perf_timer import timer

logger = loghelper.get_logger(__name__)


class Test(TestCase):

    def test_execute(self):
        @timer(logger=logger, action='Func')
        def func(name: str):
            print(f"Hello, {name}.")

        func("world")

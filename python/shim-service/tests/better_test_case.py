from typing import Type, Callable, Any
from unittest import TestCase


class BetterTestCase(TestCase):
    def __init__(self, method_name: str = None) -> None:
        super(BetterTestCase, self).__init__(method_name)

    def assertException(self,
                        expected_exception_type: Type[Exception],
                        caller: Callable,
                        handler: Callable[[Exception], None] = None):
        try:
            caller()
        except Exception as ex:
            if isinstance(ex, expected_exception_type):
                if handler is not None:
                    handler(ex)
                    return
        self.fail(f"Expected a {expected_exception_type} to be raised.")

    def assertEqual(self, expected: Any, actual: Any, msg: Any = ...) -> None:
        super(BetterTestCase, self).assertEqual(expected, actual, msg)

    def assertSetsEqual(self, expected: set, actual: set):
        if expected is None and actual is None:
            return
        if expected is None:
            self.assertIsNone(actual)
        else:
            self.assertIsNotNone(actual)
        diff = actual.symmetric_difference(expected)
        if len(diff) != 0:
            self.fail(f"Sets to not match. Expected: {expected}, got: {actual}.")

    def assertThrows(self, expected_exception_type: Type[Exception],
                     caller: Callable,
                     partial_message: str = None) -> Exception:
        failure_message = None
        try:
            caller()
            failure_message = f"Expected a {expected_exception_type} to be raised."
        except Exception as ex:
            if isinstance(ex, expected_exception_type):
                if partial_message is not None:
                    message = f"{ex}"
                    if partial_message not in message:
                        failure_message = f"Expected exception message to contain '{partial_message}' but was '{message}'"
                if failure_message is None:
                    return ex
        self.fail(failure_message)

    def newAssertIsNotNone(self, obj: Any, msg=None) -> Any:
        super(BetterTestCase, self).assertIsNotNone(obj, msg)
        return obj

    def assertEmpty(self, thing: Any):
        if len(thing) != 0:
            self.fail(f"Expected {thing} to be empty.")

    def assertNotEmpty(self, thing: Any):
        if len(thing) == 0:
            self.fail("Expected value to not be empty.")

    def assertHasLength(self, expected_length: int, thing: Any):
        if thing is None:
            self.assertIsNotNone(thing)
        actual_len = len(thing)
        if actual_len != expected_length:
            self.fail(f"Expected length of {expected_length}, but was {actual_len}.")

    def assertSame(self, expected: Any, actual: Any):
        if id(expected) != id(actual):
            self.fail(f"Expected {expected} to be the same as {actual}.")

    def assertAttributeEquals(self, expected: Any, obj: Any, attribute_name: str):
        actual = getattr(obj, attribute_name)
        if actual != expected:
            self.fail(f"attribute {attribute_name} value of {actual} != {expected}")

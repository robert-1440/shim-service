import os.path
import sys
import unittest
from copy import copy
from functools import cmp_to_key
from typing import List, Iterable, Any, Callable, Optional, Tuple
from unittest import TestCase, TestSuite

from coverage import Coverage

coverage = False


def get_class_name(obj: Any) -> str:
    if obj is None:
        return "NoneType"
    return obj.__class__.__name__


def get_test_case(suite: TestSuite) -> Optional[TestCase]:
    tests = getattr(suite, '_tests')
    if len(tests) == 0:
        return None
    for t in tests:
        if isinstance(t, TestCase):
            return t
        c = get_test_case(t)
        if c is not None:
            return c

    return None


def get_level(suite: TestSuite):
    tc = get_test_case(suite)
    if tc is not None:
        name = get_class_name(tc)
        if name.endswith("IT"):
            return 1
    return 0


def split_tests(suite: TestSuite) -> Tuple[TestSuite]:
    standard_tests = []
    it_tests = []
    tests = getattr(suite, '_tests')
    for t in tests:
        level = get_level(t)
        if level == 0:
            standard_tests.append(t)
        else:
            it_tests.append(t)
    results = []
    left = suite
    if len(standard_tests) > 0:
        setattr(left, '_tests', standard_tests)
        results.append(left)
    if len(it_tests) > 0:
        right = copy(suite)
        setattr(right, '_tests', it_tests)
        results.append(right)
    return tuple(results)


def sort_test(collection: Iterable[Any], comparator: Callable[[Any, Any], int]) -> List[Any]:
    """
    Convenience function that will sort the given collection using the given comparator.

    :param collection: the collection to sort.
    :param comparator:  the comparator to use.
    :return: the sorted list.
    """
    return sorted(collection, key=cmp_to_key(comparator))


if __name__ == "__main__":
    our_file = __file__
    parent = os.path.split(our_file)[0]
    top_level = os.path.split(parent)[0]
    src = os.path.join(top_level, 'src')
    sys.path.insert(0, src)


    def compare_test_case(a: TestSuite, b: TestSuite):
        return get_level(a) - get_level(b)


    def add_env_var(string: str):
        if len(string) > 2:
            index = string.find("=")
            if index > 0:
                name = string[0:index:]
                value = string[index + 1::]
                os.environ[name] = value
                return

        print(f"Unrecognized command line argument: {string}", file=sys.stderr)
        exit(2)


    def check_command_line():
        size = len(sys.argv)
        if size > 1:
            for i in range(1, size):
                v = sys.argv[i]
                if v == "--cov":
                    global coverage
                    coverage = True
                else:
                    add_env_var(v)


    check_command_line()

    if coverage:
        os.environ['COVERAGE_RCFILE'] = os.path.join(parent, ".coveragerc")
        cov = Coverage()
        cov.start()
    else:
        cov = None

    loader = unittest.TestLoader()
    suite = loader.discover(parent)
    runner = unittest.runner.TextTestRunner(descriptions=True, verbosity=2)
    split = split_tests(suite)
    for tests in split:
        result = runner.run(tests)
        if len(result.errors) > 0 or len(result.failures) > 0:
            exit(3)

    if cov is not None:
        cov.stop()
        cov.report(omit="*test*", show_missing=True, skip_empty=True, file=sys.stdout)

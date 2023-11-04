import abc
from typing import Dict, Any, Iterable, List

from botomocks.exceptions import AwsResourceNotFoundResponseException, AwsInvalidRequestResponseException, \
    AwsInvalidParameterResponseException, AwsConflictResponseException


def raise_not_found(operation_name: str, message: str):
    raise AwsResourceNotFoundResponseException(operation_name, message)


def raise_invalid_request(operation_name: str, message: str):
    raise AwsInvalidRequestResponseException(operation_name, message)

def raise_invalid_parameter(operation_name: str, message: str):
    raise AwsInvalidParameterResponseException(operation_name, message)


def raise_conflict_exception(operation_name: str, message: str):
    raise AwsConflictResponseException(operation_name, message)

class KeyId:
    def __init__(self, *args):
        if len(args) == 1 and type(args) == tuple:
            self.__objects = args[0]
        else:
            objects = []
            for arg in args:
                objects.append(arg)
            self.__objects = tuple(objects)
        hashed = 0
        for obj in self.__objects:
            hashed += hash(obj)
        self.__hash_value = hashed

    def __getitem__(self, item):
        return self.__objects[item]

    def __hash__(self):
        return self.__hash_value

    def __eq__(self, other):
        return isinstance(other, KeyId) and self.__objects == other.__objects

class MockPageIterator:
    def __init__(self, results: Dict[str, Any]):
        self.results = results

    def __iter__(self):
        return iter([self.results])


class MockPaginator:
    def __init__(self, result_key: str,
                 results: Iterable[Any] = None):
        self.result_key = result_key
        self.results = {result_key: []}
        self.args_passed = None
        if results is not None:
            for r in results:
                self.add_result(r)

    def add_result(self, obj: Any):
        if not isinstance(obj, dict):
            if hasattr(obj, "to_json"):
                obj = obj.to_json()
            else:
                obj = obj.__dict__
        for v in self.results.values():
            v.append(obj)
            break

    def paginate(self, **kwargs):
        self.args_passed = kwargs
        return MockPageIterator(self.results)


class BaseMockClient(metaclass=abc.ABCMeta):

    def __init__(self):
        self.paginators: Dict[str, List[MockPaginator]] = {}

    def get_paginator(self, operation_name: str):
        p = self.create_paginator(operation_name)
        self.paginators.setdefault(operation_name, []).append(p)
        return p

    @abc.abstractmethod
    def create_paginator(self, operation_name: str):
        raise NotImplementedError()


def assert_empty(props: Dict[str, Any]):
    if len(props) != 0:
        raise AssertionError(f"Unrecognized properties: {','.join(props.keys())}")

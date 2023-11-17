import abc
from collections import namedtuple
from enum import Enum
from typing import Dict, Type, Any, Tuple, Optional, Callable, Union, List

from aws.dynamodb import DynamoDbRow
from utils import collection_utils
from utils.collection_utils import EMPTY_TUPLE

InjectedAttribute = Tuple[str, str]
AttributeType = Union[Type, Tuple[Type, int]]
InjectedAttributeValue = namedtuple("InjectedAttributeValue", "name value")

DEFAULT_DELIMITER = '\t'

def _find_attribute(obj: Any, name: str) -> Optional[Any]:
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _get_attribute(self, name) -> Any:
    try:
        return getattr(self, name)
    except Exception:
        raise AttributeError(f"{name} attribute is required.")


class _ArgsHolder:
    def __init__(self, value: Tuple):
        self.value = value


class _Formatter(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def format(self, value: Any) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def extract(self, value: str) -> Any:
        return value


class _StringFormatter(_Formatter):

    def __init__(self, size: Optional[int] = None):
        assert size is None or size > 0
        self.size: Optional[int] = size

    def format(self, value: str) -> str:
        if self.size is not None:
            return value.ljust(self.size, '~')
        return value

    def extract(self, value: str) -> Any:
        if self.size is not None:
            index = value.find('~')
            if index > -1:
                value = value[0:index:]
        return value

    @staticmethod
    def build(size: Optional[int]):
        if size is None:
            return _DEFAULT_STRING_FORMATTER
        return _StringFormatter(size)


class _IntFormatter(_Formatter):

    def __init__(self, size: Optional[int] = None):
        assert size is None or size > 0
        self.size: Optional[int] = size

    def format(self, value: int) -> str:
        output = str(value)
        if self.size is not None:
            return output.rjust(self.size, '0')
        return output

    def extract(self, value: str) -> int:
        return int(value)

    @staticmethod
    def build(size: Optional[int]):
        if size is None:
            return _DEFAULT_INT_FORMATTER
        return _IntFormatter(size)


_DEFAULT_STRING_FORMATTER = _StringFormatter()
_DEFAULT_INT_FORMATTER = _IntFormatter()

_FORMATTER_BUILDERS: Dict[Type, Callable[[Optional[int]], _Formatter]] = {
    str: _StringFormatter.build,
    int: _IntFormatter.build
}


class CompositeKeyPart:
    def __init__(self,
                 attribute_name: str,
                 attribute_type: AttributeType):
        self.attribute_name = attribute_name
        if type(attribute_type) is tuple:
            size = attribute_type[1]
            attribute_type = attribute_type[0]
        else:
            self.attribute_type = attribute_type
            size = None

        b = _FORMATTER_BUILDERS.get(attribute_type)
        if b is None:
            raise ValueError(f"Unsupported type: {attribute_type}")
        self.formatter = b(size)

    def build(self, value: Any) -> str:
        return self.formatter.format(value)

    def extract(self, value: str) -> Any:
        return self.formatter.extract(value)


def _transform_dict(source: Dict[str, Any], transformer: Callable[[str, Any], Any]) -> Dict[str, Any]:
    new_dict = {}
    for key, value in source.items():
        new_dict[key] = transformer(key, value)
    return new_dict


class CompositeKey:
    def __init__(self,
                 attribute_name: str,
                 attributes_and_types: Dict[str, Union[Type, Tuple[Type, int]]],
                 delimiter=DEFAULT_DELIMITER):
        self.attribute_name = attribute_name
        self.parts: Dict[str, CompositeKeyPart] = _transform_dict(attributes_and_types, CompositeKeyPart)
        self.original_parts = self.parts
        self.delimiter = delimiter
        self.injected: Optional[InjectedAttributeValue] = None

    def inject_attribute(self, attribute_name: str, attribute_value: Any):
        """
        Here we update the composite key with the given attribute as the first part. The main use case is
        to inject a "record type" for hash keys, so that subclasses do not have to include it when constructing
        the key parts.

        :param attribute_name: attribute name to inject.
        :param attribute_value: attribute type
        :return: the new composite key
        """
        new_parts = {attribute_name: CompositeKeyPart(attribute_name, type(attribute_value))}
        new_parts.update(self.parts)
        self.parts = new_parts
        self.injected = InjectedAttributeValue(attribute_name, attribute_value)

    def build_key(self, item: Dict[str, Any], target_dict: Optional[Dict[str, Any]], remove: bool = False) -> str:
        """
        Populates the given target dictionary with the key values, and optionally removes them from the item.

        :param item: the row
        :param target_dict: the optional target dictionary to populate.
        :param remove: True to remove the attributes from the item.
        :return the key as a string.
        """
        values: List[str] = []

        if self.injected is not None:
            values.append(self.injected.value)

        if remove:
            for attribute_name, part in self.original_parts.items():
                values.append(part.build(item.pop(attribute_name)))
        else:
            for attribute_name, part in self.original_parts.items():
                values.append(part.build(item[attribute_name]))

        key_string = self.delimiter.join(values)
        if target_dict is not None:
            target_dict[self.attribute_name] = key_string
        return key_string

    def prep_for_serialization(self, item: DynamoDbRow):
        """
        Prepares the item for storage by removing the component attributes and adding the key.

        :param item: the item.
        """
        self.build_key(item, item, remove=True)

    def build_key_from_args(self, args_holder: _ArgsHolder, target_dict: Dict[str, Any]):
        """
        Constructs a key from the given arguments.

        :param args_holder: the arguments holder.
        :param target_dict: the target dictionary to populate.
        :return: the key
        """

        args = args_holder.value
        it = iter(args)
        index = 0
        for attribute_name, part in self.original_parts.items():
            index += 1
            target_dict[attribute_name] = part.build(next(it))

        args_holder.value = args[index::]

    def prep_for_deserialization(self, item: Dict[str, Any]):
        """
        Reconstructs an item from the values in the key.

        :param item: the item.
        """
        key = item.pop(self.attribute_name)
        values = key.split(self.delimiter)
        it = iter(values)

        # Skip the injected attribute?
        if self.injected is not None:
            next(it)
        for attribute, part in self.original_parts.items():
            v: str = next(it)
            item[attribute] = part.extract(v)


class Key:
    def __init__(self, attribute_name: Optional[str] = None, key: Optional[CompositeKey] = None):
        self.attribute_name = attribute_name if key is None else key.attribute_name
        assert type(self.attribute_name) is str
        self.composite_key = key

    def populate_key(self, item: Dict[str, Any], target_dict: Dict[str, Any], remove: bool,
                     pre_serialized: bool = False):
        if not pre_serialized and self.composite_key is not None:
            self.composite_key.build_key(item, target_dict, remove)
            return
        target_dict[self.attribute_name] = item[self.attribute_name]

    def populate_key_from_args(self, args_holder: _ArgsHolder, target_dict: Dict[str, Any]):
        args = args_holder.value
        if self.composite_key is not None:
            self.composite_key.build_key_from_args(args_holder, target_dict)
        else:
            target_dict[self.attribute_name] = args[0]
            args_holder.value = args[1::] if len(args) > 1 else EMPTY_TUPLE

    def prep_for_serialization(self, item: DynamoDbRow):
        if self.composite_key is not None:
            self.composite_key.prep_for_serialization(item)

    def prep_for_deserialization(self, item: DynamoDbRow):
        if self.composite_key is not None:
            self.composite_key.prep_for_deserialization(item)


class _KeyType(Enum):
    HASH = "hash"
    RANGE = "range"


def _extract_key(key_type: _KeyType, obj: Any) -> Optional[Key]:
    """
    Here we determine whether the object has an attribute name for the key, or a composite.
    :param key_type: the key type
    :param obj: the object with the attributes to check.
    :return:
    """
    attribute = f"__{key_type.value}_key__"
    k = _find_attribute(obj, attribute)
    if k is None:
        if key_type == _KeyType.HASH:
            raise AssertionError(f"{obj}: attribute '{attribute}' is required.")
        return None
    key_attribute = f"__{key_type.value}_key_attributes__"
    ka: Optional[Dict[str, Any]] = _find_attribute(obj, key_attribute)
    if ka is not None:
        kc = CompositeKey(k, ka)
        if key_type == _KeyType.HASH:
            inject_attribute: InjectedAttribute = _find_attribute(obj, "__inject_hash_attribute__")
            if inject_attribute is not None:
                kc.inject_attribute(inject_attribute[0], _get_attribute(obj, inject_attribute[1]))
        return Key(key=kc)
    return Key(attribute_name=k)


class CompoundKey:
    def __init__(self, hash_key: Key, range_key: Optional[Key] = None):
        self.keys: Tuple[Key, ...] = collection_utils.to_non_none_tuple(hash_key, range_key)
        self.key_attributes = list(map(lambda k: k.attribute_name, self.keys))

    def key_count(self) -> int:
        return len(self.keys)

    def build_key_as_dict(self, item: Dict[str, Any], pre_serialized: bool = False) -> Dict[str, Any]:
        """
        Build the primary key (hash + range) as a dictionary, from the given item.

        :param item: the row
        :return: the dictionary
        """

        target_dict = {}
        for key in self.keys:
            key.populate_key(item, target_dict, False, pre_serialized=pre_serialized)

        return target_dict

    def build_hash_key_from_args(self, *args) -> Tuple[str, Any]:
        """
        Use this to get the hash key attribute and value.

        :param args: the args.
        :return: the hash key and value
        """
        holder = _ArgsHolder(args)
        result_key = {}
        key = self.keys[0]
        key.populate_key_from_args(holder, result_key)
        key.prep_for_serialization(result_key)
        return key.attribute_name, result_key[key.attribute_name]

    def build_range_key_from_args(self, *args) -> Tuple[str, Any]:
        """
        Use this to get the range key attribute and value.

        :param args: the args.
        :return: the hash key and value
        """
        holder = _ArgsHolder(args)
        result_key = {}
        key = self.keys[1]
        key.populate_key_from_args(holder, result_key)
        key.prep_for_serialization(result_key)
        for key, value in result_key.items():
            return key, value
        return key.attribute_name, result_key[key.attribute_name]

    def build_key_from_args(self, *args) -> Tuple[Dict[str, Any], Tuple]:
        holder = _ArgsHolder(args)
        result_key = {}
        for key in self.keys:
            key.populate_key_from_args(holder, result_key)
        self.prep_for_serialization(result_key)
        return result_key, holder.value

    def prep_for_serialization(self, item: DynamoDbRow):
        for key in self.keys:
            key.prep_for_serialization(item)

    def prep_for_deserialization(self, item: DynamoDbRow):
        for key in self.keys:
            key.prep_for_deserialization(item)


def create_primary_key(obj: Any) -> CompoundKey:
    hash_key = _extract_key(_KeyType.HASH, obj)
    range_key = _extract_key(_KeyType.RANGE, obj)
    return CompoundKey(hash_key, range_key)

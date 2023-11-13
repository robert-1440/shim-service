import abc
import random
from copy import deepcopy
from threading import RLock
from typing import List, Optional, Any, Dict, Tuple, Iterable, Callable

from aws.dynamodb import DynamoDbValidationException, DynamoDbRow, DynamoDbItem, convert_value, \
    ResourceNotFoundException
from botomocks import AwsResourceNotFoundResponseException, assert_empty, AwsInvalidRequestResponseException, \
    raise_invalid_parameter, AwsInvalidParameterResponseException
from botomocks.ddb_reserved import RESERVED_WORDS
from botomocks.exceptions import ConditionalCheckFailedException, AwsExceptionResponseException, \
    AwsTransactionCanceledException
from support.collection_stuff import binary_search
from support.thread_utils import synchronized
from utils.dict_utils import get_or_create, set_if_not_none


class KeyPart:
    def __init__(self, attribute_name: str, attribute_type: str):
        self.attribute_name = attribute_name
        self.attribute_type = attribute_type

    @classmethod
    def from_dict(cls, v: Dict[str, Any]):
        for key, value in v.items():
            return KeyPart(key, value)


def _to_sort_value(value: Any):
    vt = type(value)
    if vt is str:
        return value
    if vt is int:
        v = str(value)
        return v.rjust(20, '0')
    return str(value)


def _to_compare_value(value: Dict[str, Any]):
    if type(value) is not dict:
        raise AttributeError(f"{type(value)} is not supported.")
    return convert_value(value)


class KeyDefinition:
    def __init__(self, parts: List[KeyPart]):
        self.parts = parts

    def build_key(self, row: Dict[str, Dict[str, Any]]):
        key = ""
        for part in self.parts:
            v = row[part.attribute_name]
            if len(key) > 0:
                key += "^"
            key += str(_to_sort_value(_get_attribute_value_for_key(v)))
        return key

    @classmethod
    def from_dict(cls, v: Optional[Dict[str, Any]]):
        if v is None:
            return None
        return KeyDefinition([KeyPart.from_dict(v)])


class AttributeValue:
    def __init__(self, attribute_type: str, attribute_value: Any):
        self.attribute_type = attribute_type
        self.attribute_value = attribute_value

    def to_dict(self):
        return {self.attribute_type: self.attribute_value}


def _get_attribute_value_for_key(value: Dict[str, Any]):
    keys = list(value.keys())
    if len(keys) > 1:
        raise ValueError("Too many keys")
    type_name = keys[0]
    value = value[type_name]
    if type_name == 'N':
        return int(value)
    return value


class Table:
    def __init__(self, name: str,
                 hash_key: KeyDefinition,
                 range_key: Optional[KeyDefinition]):
        self.hash_key = hash_key
        self.range_key = range_key
        self.name = name
        self.rows: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def build_key(self, row: Dict[str, Dict[str, Any]]):
        key = self.hash_key.build_key(row)
        if self.range_key is not None:
            key += f'\t{self.range_key.build_key(row)}'

        return key

    def find_by_example(self, row: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Dict[str, Any]]]:
        key = self.build_key(row)
        return self.rows.get(key)

    def add(self, row: Dict[str, Dict[str, Any]], replace: bool = True) -> Optional[dict]:
        key = self.build_key(row)
        if not replace:
            if key in self.rows:
                raise ConditionalCheckFailedException("PutItem")
        current = self.rows.get(key)
        self.rows[key] = row
        return current

    def get(self, key: Dict[str, Dict[str, Any]]):
        our_key = self.build_key(key)
        v = self.rows.get(our_key)
        return v

    def remove(self, key: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        our_key = self.build_key(key)
        return self.rows.pop(our_key, None)

    def query(self, partition_key: Dict[str, Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        our_key = self.hash_key.build_key(partition_key) + '\t'
        matches = list(map(lambda kr: kr[1], filter(lambda kr: kr[0].startswith(our_key), self.rows.items())))
        if self.range_key is not None:
            matches.sort(key=lambda row: self.range_key.build_key(row))
        return matches


class Condition(metaclass=abc.ABCMeta):
    name: str
    bind_name: str

    def check(self, record: Dict[str, Any], attributes: Dict[str, Any]) -> bool:
        if hasattr(self, 'bind_name'):
            value = attributes[self.bind_name]
        else:
            value = None
        return self.check_value(value, self.get_record_value(record, attributes))

    def get_record_value(self, record: DynamoDbItem, attributes: Dict[str, Any]):
        name = self.name
        if name.startswith("#"):
            name = attributes[name]
        return record.get(name)

    @abc.abstractmethod
    def check_value(self, expected: Any, actual: Any):
        raise NotImplementedError()


class EqualCondition(Condition):
    def __init__(self, name: str, bind_name: str):
        self.name = name
        self.bind_name = bind_name

    def check_value(self, expected: Any, actual: Any):
        return expected == actual


class GreaterCondition(Condition):
    def __init__(self, name: str, bind_name: str):
        self.name = name
        self.bind_name = bind_name

    def check_value(self, expected: Any, actual: Any):
        return _to_compare_value(actual) > _to_compare_value(expected)


class LessThanOrEqualCondition(Condition):
    def __init__(self, name: str, bind_name: str):
        self.name = name
        self.bind_name = bind_name

    def check_value(self, expected: Any, actual: Any):
        return _to_compare_value(actual) <= _to_compare_value(expected)


class AttributeExistsCondition(Condition):
    def __init__(self, name: str):
        self.name = name

    def check_value(self, expected: Any, actual: Any):
        return actual is not None


class AttributeDoesNotExistCondition(Condition):
    def __init__(self, name: str):
        self.name = name

    def check_value(self, expected: Any, actual: Any):
        return actual is None


class Conditions:
    def __init__(self, conditions: List[Condition]):
        self.conditions = conditions

    def validate(self, operation: str, record: dict, attributes: dict, fail: bool = True) -> bool:
        for c in self.conditions:
            if not c.check(record, attributes):
                if fail:
                    raise ConditionalCheckFailedException(operation)
                return False
        return True

    def filter_list(self, row_list: List[dict], attributes: dict) -> List[Any]:
        return list(filter(lambda row: self.validate("", row, attributes, fail=False), row_list))


def _parse_conditions(expr: Optional[str]) -> Optional[Conditions]:
    if expr is None:
        return None
    values = expr.split(" AND ")
    condition_list = []
    for v in values:
        parsed = _parse_condition_expression(v)
        if parsed.right is not None:
            if parsed.operation == '=':
                condition_list.append(EqualCondition(parsed.left, parsed.right))
            elif parsed.operation == ">":
                condition_list.append(GreaterCondition(parsed.left, parsed.right))
            elif parsed.operation == "<=":
                condition_list.append(LessThanOrEqualCondition(parsed.left, parsed.right))
            else:
                raise NotImplementedError(f"{parsed.operation} not supported.")
        elif parsed.operation == "attribute_exists":
            condition_list.append(AttributeExistsCondition(parsed.left))
        elif parsed.operation == "attribute_not_exists":
            condition_list.append(AttributeDoesNotExistCondition(parsed.left))
        else:
            raise NotImplementedError(f"Can't parsed {expr}")
    assert len(condition_list) > 0
    return Conditions(condition_list)


def _extract_assignment(expr: str, attributes: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    kv_pair = expr.split(" = ")
    prop_name = kv_pair[0].strip()
    bind_name = kv_pair[1].strip()
    return prop_name, attributes[bind_name]


def _collect_updates(expr: str, attributes: Dict[str, Dict[str, Any]]):
    if not expr.startswith("SET "):
        raise NotImplementedError(f"Unsupported expression: {expr}")
    values = expr[3::].split(",")
    record = {}
    for v in values:
        kv_pair = v.split(" = ")
        prop_name = kv_pair[0].strip()
        check_keyword(prop_name)
        bind_name = kv_pair[1].strip()
        record[prop_name] = attributes[bind_name]
    return record


def check_keyword(attribute: str):
    if attribute.lower() in RESERVED_WORDS:
        raise DynamoDbValidationException(
            f'Invalid expression: Attribute name is a reserved keyword; reserved keyword: {attribute}')


class ParsedExpression:
    def __init__(self, action: str, attribute: str):
        check_keyword(attribute)
        self.action = action
        self.attribute = attribute


def _parse_expression(expr: str) -> ParsedExpression:
    index = expr.index('(')
    if index > 0:
        end_index = expr.index(')', index + 1)
        if end_index > 0:
            action = expr[0:index:]
            attribute = expr[index + 1:end_index:]
            return ParsedExpression(action, attribute)
    raise AssertionError(f"Cannot parse expression {expr}")


class ParsedConditionExpression:
    def __init__(self, left: str, operation: str, right: Optional[str]):
        check_keyword(left)
        self.left = left
        self.operation = operation
        self.right = right


def _parse_condition_expression(expr: str) -> ParsedConditionExpression:
    values = expr.split(' ')
    if len(values) == 3:
        return ParsedConditionExpression(values[0].strip(), values[1].strip(), values[2].strip())
    elif len(values) == 1:
        v = values[0]
        index = v.find('(')
        if index > 0:
            end_index = v.find(')')
            if end_index > 0:
                operation = v[0:index:]
                attribute = v[index + 1:end_index:]
                return ParsedConditionExpression(attribute, operation, None)
    raise AssertionError(f"Can't parse '{expr}'")


class MockDynamoDbClient:
    def __init__(self):
        self.tables: Dict[str, Table] = {}
        self.update_count = 0
        self.mutex = RLock()
        self.__update_callback: Optional[Callable] = None
        self.__delete_callback: Optional[Callable] = None
        self.__get_callback: Optional[Callable] = None
        self.__put_callback: Optional[Callable] = None

    def set_get_callback(self, callback: Optional[Callable]):
        self.__get_callback = callback

    def set_put_callback(self, callback: Optional[Callable]):
        self.__put_callback = callback

    def set_update_callback(self, callback: Optional[Callable]):
        self.__update_callback = callback

    def set_delete_callback(self, callback: Optional[Callable]):
        self.__delete_callback = callback

    def add_manual_table(self, name: str, hash_key: KeyDefinition, range_key: Optional[KeyDefinition] = None):
        t = Table(name, hash_key, range_key)
        self.tables[name] = t

    def add_manual_table_v2(self, name: str, hash_key: dict, range_key: Optional[dict] = None):
        t = Table(name, KeyDefinition.from_dict(hash_key), KeyDefinition.from_dict(range_key))
        self.tables[name] = t

    def __get_table(self, name: str) -> Table:
        t = self.tables.get(name)
        if t is None:
            raise AwsResourceNotFoundResponseException("GetItem", "Requested resource not found")
        return t

    @synchronized
    def put_item(self, **kwargs):
        kwargs = dict(kwargs)
        table_name = kwargs.pop('TableName')
        item = kwargs.pop('Item')
        expr = kwargs.pop('ConditionExpression', None)
        kwargs.pop('ReturnConsumedCapacity', None)
        kwargs.pop('ReturnItemCollectionMetrics', None)
        return_values = kwargs.pop("ReturnValues", None)
        if return_values is not None and return_values not in ('NONE', 'ALL_OLD'):
            raise AwsInvalidParameterResponseException("PutItem", f"Invalid ReturnValues: {return_values}")
        assert_empty(kwargs)
        replace = expr is None
        if self.__put_callback is not None:
            c = self.__put_callback
            self.__put_callback = None
            if c():
                self.__put_callback = c
        old_values = self.__get_table(table_name).add(item, replace)
        if return_values == 'ALL_OLD' and old_values is not None:
            return {'Attributes': old_values}
        return {}

    @synchronized
    def update_item(self, **kwargs):
        self.update_count += 1
        kwargs = dict(kwargs)
        table_name = kwargs.pop("TableName")
        key = kwargs.pop("Key")
        expr = kwargs.pop("UpdateExpression")
        condition_expr = kwargs.pop("ConditionExpression", None)
        expr_attributes = kwargs.pop("ExpressionAttributeValues", None)
        kwargs.pop('ReturnConsumedCapacity', None)
        kwargs.pop('ReturnItemCollectionMetrics', None)

        assert_empty(kwargs)
        updates = _collect_updates(expr, expr_attributes)
        t = self.__get_table(table_name)

        if self.__update_callback:
            c = self.__update_callback
            self.__update_callback = None
            c()
        current = t.find_by_example(key)
        new_record = False
        if current is None:
            current = {}
            new_record = True

        if condition_expr is not None:
            conditions = _parse_conditions(condition_expr)
            conditions.validate("UpdateItem", current, expr_attributes)
        current.update(updates)
        if new_record:
            current.update(key)
            t.add(current)

        return {}

    @synchronized
    def delete_item(self, **kwargs):
        kwargs = dict(kwargs)
        table_name = kwargs.pop('TableName')
        key = kwargs.pop('Key')
        rv = kwargs.pop('ReturnValues', None)
        condition_expr = kwargs.pop('ConditionExpression', None)
        expr_attributes = kwargs.pop("ExpressionAttributeValues", None)
        if len(kwargs) != 0:
            raise AssertionError(f"Unrecognized properties: {','.join(kwargs.keys())}")

        if self.__delete_callback is not None:
            dc = self.__delete_callback
            self.__delete_callback = None
            dc()

        t = self.__get_table(table_name)
        if condition_expr is not None:
            current = t.get(key)
            if current is None:
                raise ConditionalCheckFailedException("DeleteItem")

            conditions = _parse_conditions(condition_expr)
            conditions.validate("DeleteItem", current, expr_attributes)

        v = t.remove(key)
        record = {}

        if v is not None and rv == 'ALL_OLD':
            record['Attributes'] = v
        return record

    @synchronized
    def get_item(self, **kwargs):
        kwargs = dict(kwargs)
        table_name = kwargs.pop('TableName')
        key = kwargs.pop('Key')
        kwargs.pop("ConsistentRead", None)
        attributes = kwargs.pop("ProjectionExpression", None)

        if len(kwargs) != 0:
            raise AssertionError(f"Unrecognized properties: {','.join(kwargs.keys())}")

        if self.__get_callback is not None:
            c = self.__get_callback
            self.__get_callback = None
            c()

        v = self.__get_table(table_name).get(key)
        if v is None:
            return {}
        if attributes is not None and len(attributes) > 0:
            result_item = dict(key)
            for key in attributes.split(','):
                key = key.strip()
                result_item[key] = v[key]
            v = result_item
        return {"Item": deepcopy(v)}

    @synchronized
    def batch_write_item(self, **kwargs):
        items: Dict[str, List[Dict[str, Any]]] = kwargs.pop('RequestItems')
        if len(items) > 25:
            raise AssertionError("too many items")
        assert_empty(kwargs)
        unprocessed = []
        for table_name, requests in items.items():
            for request in requests:
                for action, item_request in request.items():
                    if len(item_request) != 1:
                        raise AssertionError(f"Too many entries in {item_request}")
                    if action == 'PutRequest':
                        item = item_request['Item']
                        self.put_item(TableName=table_name, Item=item)
                    elif action == 'DeleteRequest':
                        key = item_request['Key']
                        self.delete_item(TableName=table_name, Key=key)
                    else:
                        raise AwsInvalidParameterResponseException("BatchWriteItems", f"Invalid action: {action}")

        return {'UnprocessedItems': unprocessed}

    @synchronized
    def batch_get_item(self, **kwargs):
        kwargs = dict(kwargs)
        items: Dict[str, Dict[str, Any]] = kwargs.pop('RequestItems')
        if len(items) > 100:
            raise AssertionError("too many items")
        assert_empty(kwargs)
        unprocessed = {}
        results: Dict[str, List[DynamoDbItem]] = {}
        for table_name, request in items.items():
            params = {
                'TableName': table_name,
                'ConsistentRead': request.get('ConsistentRead', False)
            }
            set_if_not_none(params, 'ProjectionExpression', request.get('ProjectionExpression'))

            for key in request['Keys']:
                params['Key'] = key
                try:
                    result = self.get_item(**params)
                    item = result.get("Item")
                    if item is not None:
                        result_list = get_or_create(results, table_name, list)
                        result_list.append(item)
                except ResourceNotFoundException:
                    pass

        # Shuffle them to simulate parallel processing
        for table_name, result_list in results.items():
            if len(result_list) > 1:
                random.shuffle(result_list)
        return {
            'Responses': results,
            'UnprocessedKeys': unprocessed
        }

    @synchronized
    def transact_write_items(self, **kwargs):
        items: List[Dict[str, Any]] = kwargs.pop('TransactItems')
        if len(items) == 0:
            return None
        if len(items) > 100:
            raise AssertionError("too many items")
        assert_empty(kwargs)
        save_tables = deepcopy(self.tables)
        ok = False
        try:
            cancel_reasons = []
            error_count = 0
            for item in items:
                keys = item.keys()
                if len(keys) != 1:
                    raise_invalid_parameter("TransactWriteItems", f"Too many values in {item}")
                action = next(iter(keys))
                content = next(iter(item.values()))
                if error_count < 1:
                    try:
                        if action == 'Put':
                            self.put_item(**content)
                        elif action == 'Delete':
                            self.delete_item(**content)
                        elif action == 'Update':
                            self.update_item(**content)
                        else:
                            raise_invalid_parameter("TransactWriteItems", f"Unsupported action {action} "
                                                                          f"in {item}")
                    except AwsInvalidRequestResponseException as ex:
                        raise ex
                    except AwsExceptionResponseException as ex:
                        cancel_reasons.append({'Code': f"{ex.response['Error']['Code']}",
                                               'Message': {ex.response['Error']['Message']}})
                        error_count += 1
                        continue
                cancel_reasons.append({'Code': 'None'})
            if error_count > 0:
                raise AwsTransactionCanceledException(cancel_reasons)
            ok = True
        finally:
            if not ok:
                self.tables = save_tables

    @synchronized
    def scan(self, **kwargs):
        table_name = kwargs.pop('TableName')
        select = kwargs.pop('Select')
        assert select == "ALL_ATTRIBUTES"
        t = self.__get_table(table_name)
        cloned = list(map(lambda row: row.copy(), t.rows.values()))
        return {
            'Items': cloned
        }

    @synchronized
    def query(self, **kwargs):
        kwargs = kwargs.copy()
        table_name = kwargs.pop('TableName')
        select = kwargs.pop('Select')
        assert select == "ALL_ATTRIBUTES"

        key_condition_exp = kwargs.pop('KeyConditionExpression')
        exp_attributes: Dict[str, Any] = kwargs.pop('ExpressionAttributeValues').copy()
        limit: Optional[int] = kwargs.pop("Limit", None)
        exclusive_start_key: str = kwargs.pop("ExclusiveStartKey", None)
        consistent_read = kwargs.pop('ConsistentRead', None)
        if consistent_read is not None:
            assert type(consistent_read) is bool

        filter_expression = kwargs.pop('FilterExpression', None)
        expr_attribute_names: Dict[str, str] = kwargs.pop('ExpressionAttributeNames', None)

        assert_empty(kwargs)

        conditions = _parse_conditions(key_condition_exp)
        hk_condition = conditions.conditions.pop(0)

        partition_key = {hk_condition.name: exp_attributes.get(hk_condition.bind_name)}

        filter_conditions = _parse_conditions(filter_expression)

        t = self.__get_table(table_name)

        record = {}

        results: List[DynamoDbItem] = list(map(lambda row: row.copy(), t.query(partition_key)))
        if exclusive_start_key is not None and len(results) > 0:
            def compare_entry(key: str, row: DynamoDbRow):
                row_key = t.build_key(row)
                if key == row_key:
                    return 0
                if key < row_key:
                    return -1
                return 1

            end_index = binary_search(results, exclusive_start_key, compare_entry)
            if end_index < 0:
                raise AssertionError(f"Could not find last exclusive start key: {exclusive_start_key}")
            results = results[end_index::]

        if len(conditions.conditions) > 0:
            results = list(
                filter(lambda row: conditions.validate("", row, exp_attributes, fail=False), results))

        if limit is not None and len(results) > limit:
            next_one = results[limit]
            results = results[0:limit:]
            record['LastEvaluatedKey'] = t.build_key(next_one)

        if filter_conditions is not None:
            if expr_attribute_names is not None:
                exp_attributes.update(expr_attribute_names)
            results = filter_conditions.filter_list(results, exp_attributes)

        cloned = list(map(lambda row: row.copy(), results))
        record['Items'] = cloned
        return record

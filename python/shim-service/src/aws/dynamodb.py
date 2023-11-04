import abc
import json
import threading
import time
from collections import namedtuple
from io import StringIO
from typing import Any, Callable, Tuple, Union, Optional, List, Mapping, Dict, Collection, Iterable

from aws import is_not_found_exception, is_exception
from utils import date_utils, exception_utils, object_utils
from utils.dict_utils import get_or_create

DynamoDbRow = Dict[str, Any]
DynamoDbItem = Dict[str, Dict[str, Any]]

RangeKeyQuerySpecifier = namedtuple("RangeKeyQuerySpecifier", "attribute value operation")


class FilterOperation:
    def __init__(self, name: str, value: Any, operation: str):
        self.name = name
        self.value = value
        self.operation = operation


def eq_filter(name: str, value: Any) -> FilterOperation:
    return FilterOperation(name, value, '=')


def le_filter(name: str, value: Any) -> FilterOperation:
    return FilterOperation(name, value, '<=')


def not_exists_filter(name: str) -> FilterOperation:
    return FilterOperation(name, None, "!exists")


def _build_filter_expression(filters: Union[FilterOperation, Collection[FilterOperation]],
                             expr_attributes: DynamoDbItem,
                             expr_attribute_names: Dict[str, str]):
    io = StringIO()
    counter = 1
    if not isinstance(filters, Collection):
        filters = [filters]

    for fo in filters:
        if io.tell() > 0:
            io.write(" AND ")
        if fo.operation == '!exists':
            io.write(f"attribute_not_exists({fo.name})")
        else:
            key = f":f{counter}"
            att_name_key = f"#e{counter}"
            io.write(f"{att_name_key} {fo.operation} {key}")
            expr_attributes[key] = _to_attribute_value_dict(fo.value)
            expr_attribute_names[att_name_key] = fo.name
            counter += 1

    return io.getvalue()


class PrimaryKeyViolationException(Exception):
    def __init__(self):
        super(PrimaryKeyViolationException, self).__init__("Primary key violation")


class PreconditionFailedException(Exception):
    def __init__(self):
        super(PreconditionFailedException, self).__init__("Precondition Failed")


class ResourceNotFoundException(Exception):
    def __init__(self):
        super(ResourceNotFoundException, self).__init__("Resource not found")


class ClientError(Exception):
    def __init__(self, ex: Any):
        super(ClientError, self).__init__(exception_utils.get_exception_message(ex))
        self.error_code = ex.response['Error']['Code']


class ThrottlingException(Exception):
    def __init__(self, ex: Any):
        super(Exception, self).__init__(exception_utils.get_exception_message(ex))


class DynamoDbValidationException(Exception):
    def __init__(self, message: str):
        super(DynamoDbValidationException, self).__init__(message)


class CancelReason:
    def __init__(self, node: dict):
        self.code = node['Code']
        if self.code == 'None':
            self.code = None
        self.message = node.get('Message')

    def __str__(self):
        result = ""
        if self.code is not None:
            result = f"Code={self.code}"
        if self.message is not None:
            if len(result) > 0:
                result += ' '
            result += f"Message={self.message}"
        return result

    def __repr__(self):
        return self.__str__()


class TransactionCancelledException(Exception):
    def __init__(self, nodes: List[Dict[str, Any]]):
        super(TransactionCancelledException, self).__init__("TransactionCancelled")
        self.reasons = list(map(CancelReason, nodes))


def convert_value(value: dict):
    keys = list(value.keys())
    if len(keys) > 1:
        raise ValueError("Too many keys")
    att_type = keys[0]
    att_value = value[keys[0]]

    if att_type == "S" or att_type == "BOOL" or att_type == "B":
        return att_value
    if att_type == "N":
        if "." in att_value:
            return float(att_value)
        return int(att_value)
    if att_type == "M":
        return build_map(att_value)
    if att_type == "L":
        values = []
        for x in att_value:
            values.append(convert_value(x))
        return values
    if att_type == "NULL":
        return None
    raise ValueError(f"Don't know how to handle {att_type}")


def build_map(entry: dict) -> dict:
    new_record = {}
    for key, value in entry.items():
        new_record[key] = convert_value(value)
    return new_record


def _from_ddb_item(item: DynamoDbItem) -> DynamoDbRow:
    return build_map(item)


def _to_attribute_value_map(entry: DynamoDbRow) -> DynamoDbItem:
    new_record = {}
    for key, value in entry.items():
        at, av = _to_attribute_value(value)
        new_record[key] = {at: av}
    return new_record


def _to_attribute_value(value: Any):
    if value is None:
        return "NULL", True
    t = type(value)
    if t is int or t is float:
        attribute_type = "N"
        attribute_value = str(value)
    elif t is str:
        attribute_type = "S"
        attribute_value = value
    elif t is bool:
        attribute_type = "BOOL"
        attribute_value = value
    elif t is list:
        attribute_type = "L"
        arr = []
        for x in value:
            t, v = _to_attribute_value(x)
            arr.append({t: v})
        attribute_value = arr
    elif t is dict:
        attribute_type = "M"
        attribute_value = _to_attribute_value_map(value)
    elif t is bytes:
        attribute_type = "B"
        attribute_value = value
    else:
        raise Exception(f"Don't know how to handle {t}")
    return attribute_type, attribute_value


def _to_attribute_value_dict(value: Any):
    name, value = _to_attribute_value(value)
    return {name: value}


def _to_ddb_item(entry: DynamoDbRow) -> DynamoDbItem:
    return _to_attribute_value_map(entry)


def _handle_client_error(ex):
    code = ex.response['Error']['Code']
    if code == "ValidationException":
        raise DynamoDbValidationException(exception_utils.get_exception_message(ex))
    if code == "ThrottlingException":
        raise ThrottlingException(ex)
    raise ClientError(ex)


def _handle_exception(ex: Any):
    if is_not_found_exception(ex):
        raise ResourceNotFoundException()

    if is_exception(ex, 400, "TransactionCanceledException"):
        raise TransactionCancelledException(ex.response['CancellationReasons'])

    type_string = str(type(ex))
    if "ConditionalCheckFailedException" in type_string:
        raise PreconditionFailedException()

    if type_string.find("ResourceNotFoundException") > -1:
        raise ResourceNotFoundException()

    if type_string.find("ClientError") > -1:
        _handle_client_error(ex)

    print(f"!!! Don't know how to handle {type_string}: {json.dumps(ex.__dict__, indent=True)}")
    raise ex


def _process_condition(condition: Union[dict, Tuple[str, dict]], params: dict):
    if type(condition) is tuple:
        bind_vars = _to_ddb_item(condition[1])
        statement = condition[0]
    else:
        counter = 1
        expr = ""
        bind_vars = {}
        for key, value in _to_ddb_item(condition).items():
            if counter > 1:
                expr += " AND "
            bind_name = f":c{counter}"
            expr += f"{key} = {bind_name}"
            bind_vars[bind_name] = value
            counter += 1
        statement = expr

    params['ConditionExpression'] = statement
    params['ExpressionAttributeValues'] = bind_vars


def _merge_key_condition(keys: Iterable[str], params: dict):
    statement = params.pop('ConditionExpression', "")

    for key in keys:
        if len(statement) > 0:
            statement += " AND "
        statement += f"attribute_exists({key})"
    params['ConditionExpression'] = statement


def _merge_key_attributes(keys: Dict[str, Any], params: dict):
    statement = params.pop('ConditionExpression', "")
    bind_vars = params.get('ExpressionAttributeValues', {})

    for key, value in keys.items():
        if len(statement) > 0:
            statement += " AND "
        bind_name = f":k{len(bind_vars)}"
        bind_vars[bind_name] = value
        statement += f"{key} = {bind_name}"
    params['ConditionExpression'] = statement
    params['ExpressionAttributeValues'] = bind_vars


def _merge_attributes(params: dict, attributes: dict):
    existing = params.get('ExpressionAttributeValues')
    if existing is None:
        existing = {}
        params['ExpressionAttributeValues'] = existing
    for key, value in attributes.items():
        existing[key] = value


class DynamoResponse:
    def __init__(self, start_time: int, response: Mapping, throttle_count: int):
        self.start_time = start_time
        self.elapsed_time = date_utils.get_system_time_in_millis() - start_time
        self.throttle_count = throttle_count
        if response is not None:
            cc = response.get('ConsumedCapacity')
            self.capacity_units = cc.get('CapacityUnits') if cc is not None else None
            self.retry_attempts = response.get('RetryAttempts', 0)
        else:
            self.capacity_units = self.retry_attempts = 0


class TransactionRequest(metaclass=abc.ABCMeta):
    table_name: str
    virtual_table_name: Optional[str]

    def __init__(self):
        self.cancel_reason: Optional[CancelReason] = None

    @abc.abstractmethod
    def to_ddb_request(self) -> Dict[str, Any]:
        raise NotImplementedError()

    def describe(self, ) -> str:
        class_name = object_utils.get_class_name(self)
        table_name = self.virtual_table_name if self.virtual_table_name is not None else self.table_name
        message = f"{class_name}({table_name})"
        if self.cancel_reason is not None:
            message += f" - {self.cancel_reason}"
        return message


class BatchCapableRequest(metaclass=abc.ABCMeta):
    table_name: str

    @abc.abstractmethod
    def to_ddb_batch_request(self) -> Dict[str, Any]:
        raise NotImplementedError()


class GetItemRequest:
    def __init__(self,
                 table_name: str,
                 keys: Dict[str, Any],
                 consistent: bool = False,
                 attributes_to_get: List[str] = None):
        self.table_name = table_name
        self.keys = keys
        self.consistent = consistent
        self.ddb_keys = _to_ddb_item(keys)
        if attributes_to_get is not None and len(attributes_to_get) == 0:
            attributes_to_get = None
        self.attributes_to_get = attributes_to_get


class PutItemRequest(TransactionRequest, BatchCapableRequest):
    def __init__(self,
                 table_name: str,
                 item: Dict[str, Any],
                 key_attributes: Optional[List[str]] = None,
                 condition: Union[dict, Tuple[str, dict]] = None,
                 virtual_table_name: str = None
                 ):
        super(PutItemRequest, self).__init__()
        self.table_name = table_name
        self.item = item
        self.key_attributes = key_attributes
        self.condition = condition
        self.virtual_table_name = virtual_table_name

    def to_ddb_request(self) -> Dict[str, Any]:
        ddb_item = _to_ddb_item(self.item)
        params = {
            "TableName": self.table_name,
            "Item": ddb_item
        }
        if self.key_attributes is not None and len(self.key_attributes) > 0:
            assert self.condition is None
            expr = ""
            for att in self.key_attributes:
                if len(expr) > 0:
                    expr += " AND "
                expr += f"attribute_not_exists({att})"
            params['ConditionExpression'] = expr

        if self.condition is not None:
            _process_condition(self.condition, params)

        return {'Put': params}

    def to_ddb_batch_request(self) -> Dict[str, Any]:
        # Cannot specify a condition on batch write so fail here
        assert self.condition is None
        item = _to_ddb_item(self.item)
        return {'PutRequest': {'Item': item}}


class UpdateItemRequest(TransactionRequest):
    def __init__(self,
                 table_name: str,
                 keys: dict,
                 item: Dict[str, Any],
                 condition: Union[dict, Tuple[str, dict]] = None,
                 must_exist: bool = True,
                 virtual_table_name: str = None
                 ):
        super(UpdateItemRequest, self).__init__()
        self.virtual_table_name = virtual_table_name
        self.must_exist = must_exist
        self.table_name = table_name
        self.item = item
        self.keys = keys
        self.condition = condition

    def to_ddb_request(self) -> Dict[str, Any]:
        ddb_item = _to_ddb_item(self.item)
        ddb_key = _to_ddb_item(self.keys)
        update_expression = None
        expression_values = {}
        counter = 1
        for key, value in ddb_item.items():
            if key in self.keys:
                continue
            if update_expression is None:
                update_expression = "SET "
            else:
                update_expression += ", "
            bind_name = f":v{counter}"
            counter += 1
            update_expression += f"{key} = {bind_name}"
            expression_values[bind_name] = value

        params = {
            "TableName": self.table_name,
            "Key": ddb_key,
            "UpdateExpression": update_expression
        }
        if self.condition is not None:
            _process_condition(self.condition, params)

        if self.must_exist:
            _merge_key_attributes(ddb_key, params)

        _merge_attributes(params, expression_values)

        return {'Update': params}


class DeleteItemRequest(TransactionRequest, BatchCapableRequest):
    def __init__(self,
                 table_name: str,
                 keys: dict,
                 condition: Union[dict, Tuple[str, dict]] = None,
                 must_exist: bool = True,
                 virtual_table_name: str = None
                 ):
        super(DeleteItemRequest, self).__init__()
        self.virtual_table_name = virtual_table_name
        self.table_name = table_name
        self.keys = keys
        self.condition = condition
        self.must_exist = must_exist

    def to_ddb_request(self) -> Dict[str, Any]:
        ddb_key = _to_ddb_item(self.keys)
        params = {
            "TableName": self.table_name,
            "Key": ddb_key
        }

        if self.condition is not None:
            _process_condition(self.condition, params)

        if self.must_exist:
            _merge_key_condition(self.keys.keys(), params)

        return {'Delete': params}

    def to_ddb_batch_request(self) -> Dict[str, Any]:
        ddb_key = _to_ddb_item(self.keys)
        return {'DeleteRequest': {'Key': ddb_key}}


class DynamoDb:
    def __init__(self, client):
        self.__client = client
        self.__thread_local = threading.local()

    def get_last_response(self) -> Union[DynamoResponse, None]:
        if hasattr(self.__thread_local, 'last_response'):
            return self.__thread_local.last_response
        return None

    def _handle_throttling(self, function_to_call) -> Any:
        self.__thread_local.throttle_count = 0
        while True:
            try:
                try:
                    return function_to_call()
                except Exception as ex:
                    _handle_exception(ex)
                    return None
            except ThrottlingException:
                self.__thread_local.throttle_count += 1
                time.sleep(1)

    def _execute_and_wrap(self, function_to_call: Callable):
        start = date_utils.get_system_time_in_millis()
        resp = self._handle_throttling(function_to_call)
        if resp is not None:
            self.__thread_local.last_response = DynamoResponse(start, resp, self.__thread_local.throttle_count)
        return resp

    def find_item(self, table_name: str,
                  keys: dict,
                  consistent: bool = False,
                  attributes_to_get=None) -> Optional[DynamoDbRow]:
        try:
            return self.get_item(table_name, keys, consistent, attributes_to_get)
        except ResourceNotFoundException:
            return None

    def get_item(self, table_name: str, keys: dict, consistent: bool = False, attributes_to_get=None) -> DynamoDbRow:
        ddb_keys = _to_ddb_item(keys)
        params = {"TableName": table_name,
                  "Key": ddb_keys}
        if attributes_to_get is not None and len(attributes_to_get) > 0:
            if type(attributes_to_get) is tuple:
                attributes_to_get = list(attributes_to_get)
            params['AttributesToGet'] = attributes_to_get

        if consistent:
            params['ConsistentRead'] = True

        record = self._execute_and_wrap(lambda: self.__client.get_item(**params))
        item = record.get('Item')
        if item is None:
            raise ResourceNotFoundException()
        return _from_ddb_item(item)

    def put_item(self, table_name: str,
                 item: DynamoDbRow,
                 key_attributes: Optional[Collection[str]] = None,
                 condition: Union[dict, Tuple[str, dict]] = None,
                 return_old: bool = False):
        ddb_item = _to_ddb_item(item)
        params = {"TableName": table_name,
                  "Item": ddb_item,
                  "ReturnConsumedCapacity": "TOTAL",
                  "ReturnItemCollectionMetrics": "SIZE"}
        if return_old:
            params['ReturnValues'] = "ALL_OLD"
        if key_attributes is not None and len(key_attributes) > 0:
            assert condition is None
            expr = ""
            for att in key_attributes:
                if len(expr) > 0:
                    expr += " AND "
                expr += f"attribute_not_exists({att})"
            params['ConditionExpression'] = expr

        if condition is not None:
            _process_condition(condition, params)

        try:
            return self._execute_and_wrap(lambda: self.__client.put_item(**params))
        except PreconditionFailedException as ex:
            if condition is None:
                raise PrimaryKeyViolationException()
            raise ex
        except ResourceNotFoundException as ex:
            raise ex

    def delete_item(self, table_name: str,
                    keys: dict,
                    condition: Union[dict, Tuple[str, dict]] = None) -> bool:
        params = {"TableName": table_name,
                  "Key": _to_ddb_item(keys),
                  "ReturnValues": "ALL_OLD"}
        if condition is not None:
            _process_condition(condition, params)
        resp = self._execute_and_wrap(lambda: self.__client.delete_item(**params))
        return resp.get('Attributes') is not None

    def delete_items(self, table_name: str,
                     keys: List[Dict[str, Any]]):
        items = []
        req = {table_name: items}
        for key in keys:
            item = {
                'DeleteRequest': {
                    'Key': _to_ddb_item(key)
                }
            }
            items.append(item)
        self._execute_and_wrap(lambda: self.__client.batch_write_item(RequestItems=req))

    def update_item(self, table_name: str,
                    keys: dict,
                    item: DynamoDbRow,
                    condition: Union[dict, Tuple[str, dict]] = None):
        ddb_item = _to_ddb_item(item)
        update_expression = None
        expression_values = {}
        counter = 1
        for key, value in ddb_item.items():
            if key in keys:
                continue
            if update_expression is None:
                update_expression = "SET "
            else:
                update_expression += ", "
            bind_name = f":v{counter}"
            counter += 1
            update_expression += f"{key} = {bind_name}"
            expression_values[bind_name] = value

        params = {"TableName": table_name,
                  "ReturnConsumedCapacity": "TOTAL",
                  "ReturnItemCollectionMetrics": "SIZE",
                  "Key": _to_ddb_item(keys),
                  "UpdateExpression": update_expression}

        if condition is not None:
            _process_condition(condition, params)

        _merge_key_condition(keys.keys(), params)

        _merge_attributes(params, expression_values)

        resp = self._execute_and_wrap(lambda: self.__client.update_item(**params))
        return resp

    @staticmethod
    def has_attributes(resp: Dict[str, Any]) -> bool:
        return 'Attributes' in resp

    def transact_write(self, items: List[TransactionRequest]):
        item_list = list(map(lambda item: item.to_ddb_request(), items))
        return self._execute_and_wrap(lambda: self.__client.transact_write_items(TransactItems=item_list))

    def batch_write(self, items: List[BatchCapableRequest]):
        """
        Performs a batch write.

        :param items: the list of BatchCapableRequest items to write.
        :return: the number of iterations required to perform the batch write
        (due to 'unprocessed items' being returned)
        """
        table_requests: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            requests: List[Dict[str, Any]] = get_or_create(table_requests, item.table_name, list)
            requests.append(item.to_ddb_batch_request())

        count = 0
        while len(table_requests) > 0:
            resp = self._execute_and_wrap(lambda: self.__client.batch_write_item(RequestItems=table_requests))
            table_requests = resp['UnprocessedItems']
            count += 1
        return count

    def batch_get(self, requests: List[GetItemRequest]) -> Dict[str, List[DynamoDbRow]]:
        table_requests: Dict[str, Dict[str, Any]] = {}
        for request in requests:
            table_request: Dict[str, Any] = get_or_create(table_requests, request.table_name, dict)
            keys: List[Dict[str, Any]] = get_or_create(table_request, 'Keys', list)
            keys.append(request.ddb_keys)
            if request.consistent:
                table_request['ConsistentRead'] = True
            if request.attributes_to_get is not None:
                table_request['ProjectionExpression'] = ",".join(request.attributes_to_get)

        results = {}
        while len(table_requests) > 0:
            resp = self._execute_and_wrap(lambda: self.__client.batch_get_item(RequestItems=table_requests))
            responses: Dict[str, List[DynamoDbItem]] = resp['Responses']
            for table_name, row_items in responses.items():
                rows: List[DynamoDbRow] = get_or_create(results, table_name, list)
                rows.extend(map(lambda m: _from_ddb_item(m), row_items))
            table_requests = resp['UnprocessedKeys']

        return results

    def scan(self, table_name: str, select_attributes: str = None):

        props = {'TableName': table_name}
        if select_attributes is None:
            props['Select'] = "ALL_ATTRIBUTES"
        else:
            props["ProjectionExpression"] = select_attributes

        def query_function(next_key: dict):
            if next_key is None:
                response = self.__client.scan(**props)
            else:
                response = self.__client.scan(ExclusiveStartKey=next_key, **props)
            items = response["Items"]
            return items, response.get("LastEvaluatedKey")

        return ResultSet(query_function)

    def query(self, table_name: str,
              partition_key_attribute: str,
              partition_key_value: Any,
              select_attributes: str = None,
              range_key_qualifier: Optional[RangeKeyQuerySpecifier] = None,
              limit: int = None,
              last_evaluated_key: Any = None,
              consistent: bool = False,
              filter_operations: Union[FilterOperation, Collection[FilterOperation]] = None):
        props = {'TableName': table_name}
        if select_attributes is None:
            props['Select'] = "ALL_ATTRIBUTES"
        else:
            props["ProjectionExpression"] = select_attributes

        if consistent:
            props['ConsistentRead'] = True

        att_name, att_value = _to_attribute_value(partition_key_value)
        stmt = f"{partition_key_attribute} = :keyval"
        expression_atts = {':keyval': {att_name: att_value}}
        if range_key_qualifier is not None:
            stmt += f" AND {range_key_qualifier.attribute} {range_key_qualifier.operation} :rangeval"
            expression_atts[':rangeval'] = _to_attribute_value(range_key_qualifier.value)

        props['KeyConditionExpression'] = stmt

        expression_attribute_names = {}
        if filter_operations is not None:
            props['FilterExpression'] = _build_filter_expression(filter_operations, expression_atts,
                                                                 expression_attribute_names)

        props['ExpressionAttributeValues'] = expression_atts

        if len(expression_attribute_names) > 0:
            props['ExpressionAttributeNames'] = expression_attribute_names

        if last_evaluated_key is not None:
            props['ExclusiveStartKey'] = last_evaluated_key

        def query_function(next_key: dict):
            nonlocal limit

            if limit is not None:
                if limit < 1:
                    raise StopIteration()
                props['Limit'] = limit

            if next_key is None:
                response = self.__client.query(**props)
            else:
                response = self.__client.query(ExclusiveStartKey=next_key, **props)
            items = response["Items"]
            if limit is not None:
                limit -= len(items)

            return items, response.get("LastEvaluatedKey")

        return ResultSet(query_function)


class ResultSet:
    def __init__(self, query_function):
        self.__query_function = query_function
        self.__next_key = None
        self.__items = None
        self.__counter = 0
        self.__done = False

    def __iter__(self):
        return self

    def __next__(self):
        if not self.has_next():
            raise StopIteration()
        return self.next()

    @property
    def next_key(self) -> Optional[Any]:
        return self.__next_key

    def has_next(self):
        if self.__done:
            return False
        if self.__items is None or self.__counter == len(self.__items):
            if self.__items is None or self.__next_key is not None:
                try:
                    self.__items, self.__next_key = self.__query_function(self.__next_key)
                except StopIteration:
                    self.__done = True
                    return False
                if len(self.__items) > 0:
                    self.__counter = 0
                    return True
            self.__done = True
            return False
        return True

    def next(self) -> Dict[str, Any]:
        if not self.has_next():
            raise Exception("No more")
        item = _from_ddb_item(self.__items[self.__counter])
        self.__counter += 1
        return item

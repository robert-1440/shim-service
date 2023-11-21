import abc
from typing import Dict, Any, Optional, Tuple, Callable, List, Union, Collection

from aws.dynamodb import DynamoDb, PrimaryKeyViolationException, PutItemRequest, TransactionCancelledException, \
    DynamoDbRow, PreconditionFailedException, DeleteItemRequest, TransactionRequest, UpdateItemRequest, \
    RangeKeyQuerySpecifier, GetItemRequest, DynamoDbItem, FilterOperation, BatchCapableRequest
from aws.dynamodb_keys import create_primary_key, _find_attribute, CompoundKey
from repos import OptimisticLockException, Record, QueryResult, QueryResultSet
from repos.aws import VirtualTable
from utils import loghelper
from utils.date_utils import get_system_time_in_millis

INITIALIZER_ATTRIBUTE = '__initializer__'

UPDATE_TIME_ATTRIBUTE = '__update_time__'

STATE_COUNTER_ATTRIBUTE = '__state_counter__'

TABLE_NAME_ATTRIBUTE = "__table_name__"

BatchGetResultItem = Optional[Union[Record, DynamoDbRow]]

logger = loghelper.get_logger(__name__)


class BatchGetResult:
    def __init__(self, entries: List[BatchGetResultItem], row_count: int):
        self.entries = entries
        self.row_count = row_count
        self.index = 0

    def get_entry_at(self, index: int) -> Optional[BatchGetResultItem]:
        return self.entries[index]

    def get_next_entry(self) -> Optional[BatchGetResultItem]:
        if self.index == self.row_count:
            raise IndexError()
        v = self.entries[self.index]
        self.index += 1
        return v

    def has_entry(self, index: int):
        return self.entries[index] is not None


class AbstractAwsRepo(metaclass=abc.ABCMeta):
    primary_key: CompoundKey

    def __init__(self, ddb: DynamoDb, virtual_table: Optional[VirtualTable] = None):
        if virtual_table is not None:
            self.__inject_hash_attribute__ = ('tableType', '__table_type__')
            self.__table_type__ = virtual_table.table_type
        self.virtual_table = virtual_table
        self.ddb = ddb
        self.table_name = self.get_attribute(TABLE_NAME_ATTRIBUTE)
        self.initializer: Callable[[DynamoDbRow], Any] = self.get_attribute(INITIALIZER_ATTRIBUTE)
        self.primary_key = create_primary_key(self)
        self.state_counter_attribute = self.find_attribute(STATE_COUNTER_ATTRIBUTE, "stateCounter")
        self.update_time_attribute = self.find_attribute(UPDATE_TIME_ATTRIBUTE, "updateTime")

    def find_attribute(self, name: str, default_value_if_true: Any = None):
        v = _find_attribute(self, name)
        if v is not None:
            if type(v) == bool and v and default_value_if_true is not None:
                return default_value_if_true

        return v

    def __get_virtual_table_name(self):
        return self.virtual_table.name if self.virtual_table else None

    def get_attribute(self, name: str) -> Any:
        try:
            return getattr(self, name)
        except:
            raise AttributeError(f"{name} attribute is required.")

    def create(self, entry: Record):
        item = self.prepare_item(entry)
        try:
            self.ddb.put_item(self.table_name, item, key_attributes=self.primary_key.key_attributes)
            return True
        except PrimaryKeyViolationException:
            return False

    def update_with_state_check(self, entry: Record):
        self.__update_with_state_check(entry, None)

    def create_update_with_state_check_request(self, entry: Record) -> UpdateItemRequest:
        return self.__update_with_state_check(entry, None, False)

    def patch_with_state_check(self, entry: Record, patches: Dict[str, Any]):
        self.__update_with_state_check(entry, patches)

    def create_patch_with_state_check_request(self, entry: Record, patches: Dict[str, Any]) -> UpdateItemRequest:
        return self.__update_with_state_check(entry, patches, apply_now=False)

    def __update_with_state_check(self, entry: Record, patches: Optional[Dict[str, Any]],
                                  apply_now: bool = True) -> Optional[UpdateItemRequest]:
        assert self.state_counter_attribute is not None, "No __state_counter__ was specified."
        item = self.prepare_item(entry)
        if patches is None:
            patches = item

        current_state_counter = item[self.state_counter_attribute]
        patches[self.state_counter_attribute] = current_state_counter + 1
        if self.update_time_attribute is not None:
            patches[self.update_time_attribute] = get_system_time_in_millis()
        keys = self.primary_key.build_key_as_dict(item)
        condition = {self.state_counter_attribute: current_state_counter}
        if not apply_now:
            return UpdateItemRequest(
                self.table_name,
                keys=keys,
                item=patches,
                condition=condition,
                must_exist=True,
                virtual_table_name=self.__get_virtual_table_name()
            )
        try:
            self.ddb.update_item(
                table_name=self.table_name,
                keys=keys,
                item=patches,
                condition=condition
            )
        except PreconditionFailedException:
            raise OptimisticLockException()
        return None

    def patch(self, entry: Record, patches: Dict[str, Any]) -> bool:
        item = self.prepare_item(entry)
        try:
            self.ddb.update_item(
                table_name=self.table_name,
                keys=self.primary_key.build_key_as_dict(item, pre_serialized=True),
                item=patches
            )
            return True
        except PreconditionFailedException:
            return False

    def patch_from_args(self, *args, patches: Dict[str, Any]) -> bool:
        key, _ = self.primary_key.build_key_from_args(*args)
        try:
            self.ddb.update_item(
                table_name=self.table_name,
                keys=key,
                item=patches
            )
            return True
        except PreconditionFailedException:
            return False

    def create_patch_from_args_request(self, *args, patches: Dict[str, Any], must_exist: bool = False):
        key, _ = self.primary_key.build_key_from_args(*args)
        return UpdateItemRequest(
            self.table_name,
            keys=key,
            item=patches,
            must_exist=must_exist,
            virtual_table_name=self.__get_virtual_table_name()
        )

    def patch_with_condition(self, entry: Record,
                             condition_property: str,
                             new_value: Any,
                             patches: Dict[str, Any] = None):
        item = self.prepare_item(entry)
        current_value = item[condition_property]
        if patches is None:
            patches = {}
        patches[condition_property] = new_value
        try:
            self.ddb.update_item(
                table_name=self.table_name,
                keys=self.primary_key.build_key_as_dict(item, pre_serialized=True),
                item=patches,
                condition={condition_property: current_value}
            )
        except PreconditionFailedException:
            raise OptimisticLockException()

    def replace(self, entry: Record):
        """
        Used to replace an item.

        :param entry: the entry.
        :return: True if the item was created, False if it was updated.
        """
        item = self.prepare_item(entry)
        return 'Attributes' not in self.ddb.put_item(self.table_name, item, return_old=True)

    def find(self, *args, **kwargs) -> Optional[Any]:
        consistent = kwargs.pop('consistent', False)
        key, _ = self.primary_key.build_key_from_args(*args)
        item = self.ddb.find_item(self.table_name, key, consistent=consistent)
        if item is None:
            return item
        return self.deserialize_record(item)

    def create_get_item_request_from_args(self, *args,
                                          consistent: bool = False,
                                          attributes_to_get: List[str] = None) -> GetItemRequest:

        key, _ = self.primary_key.build_key_from_args(*args)
        if self.virtual_table is not None and (attributes_to_get is not None and len(attributes_to_get) > 0):
            raise NotImplementedError("Projecting attributes is not supported with virtual tables")
        if attributes_to_get is not None:
            # We need to ensure that the primary key attributes are included so that we can match them up later
            att_set = set(attributes_to_get)
            att_set.update(key.keys())
            attributes_to_get = list(att_set)

        req = GetItemRequest(
            self.table_name,
            key,
            consistent=consistent,
            attributes_to_get=attributes_to_get
        )
        setattr(req, 'repo', self)
        return req

    def batch_write(self, requests: List[BatchCapableRequest]):
        self.ddb.batch_write(requests)

    def batch_get(self, requests: List[GetItemRequest]) -> BatchGetResult:

        # Collect the requests such that we can reconcile them after. This is because DynamoDB will return them
        # in a random order due to parallel processing.
        counter = 0
        requests_to_match = []
        for req in requests:
            requests_to_match.append((req, counter))
            counter += 1

        def key_matches(row_key: DynamoDbRow, tracker_key: DynamoDbRow):
            for key, value in tracker_key.items():
                if row_key.get(key) != value:
                    return False
            return True

        def find_match(table_name: str, row_key: DynamoDbItem) -> Optional[Tuple[GetItemRequest, int, AbstractAwsRepo]]:
            counter = 0
            for req, index in requests_to_match:
                if req.table_name == table_name and key_matches(row_key, req.keys):
                    del requests_to_match[counter]
                    return req, index, getattr(req, 'repo')
                counter += 1

            return None

        results = self.ddb.batch_get(requests)
        result_list = [None] * len(requests)
        match_count = 0
        for table_name, rows in results.items():
            if len(rows) < 1:
                continue
            for row in rows:
                match = find_match(table_name, row)
                if match is None:
                    continue
                match_count += 1
                request = match[0]
                repo = match[2]
                result_list[match[1]] = repo.deserialize_record(row) if request.attributes_to_get is None else row

        return BatchGetResult(result_list, match_count)

    def delete_entry(self, entry: Record) -> bool:
        item = self.prepare_item(entry)
        key = self.primary_key.build_key_as_dict(item, pre_serialized=True)
        return self.ddb.delete_item(self.table_name, key)

    def delete(self, *args) -> bool:
        key, _ = self.primary_key.build_key_from_args(*args)
        return self.ddb.delete_item(self.table_name, key)

    def delete_with_condition(self, entry: Record,
                              condition_property: str,
                              condition_value: Any):
        item = self.prepare_item(entry)
        try:
            self.ddb.delete_item(
                table_name=self.table_name,
                keys=self.primary_key.build_key_as_dict(item, pre_serialized=True),
                condition={condition_property: condition_value}
            )
        except PreconditionFailedException:
            raise OptimisticLockException()

    def query_set(self,
                  *args,
                  consistent: bool = False,
                  start_after=None,
                  limit: int = None,
                  last_evaluated_key=None,
                  range_filter: Optional[FilterOperation] = None,
                  filters: Union[FilterOperation, Collection[FilterOperation]] = None,
                  select_attributes: List[str] = None
                  ) -> QueryResultSet:
        att, value = self.primary_key.build_hash_key_from_args(*args)
        if start_after is not None:
            range_att, range_value = self.primary_key.build_range_key_from_args(start_after)
            rq = RangeKeyQuerySpecifier(range_att, range_value, ">")
        elif range_filter is not None:
            v = range_filter.value
            if type(v) is tuple:
                range_att, range_value = self.primary_key.build_range_key_from_args(*v)
            else:
                range_att, range_value = self.primary_key.build_range_key_from_args(v)
            rq = RangeKeyQuerySpecifier(range_att, range_value, range_filter.operation)
        else:
            rq = None

        rset = self.ddb.query(
            self.table_name,
            att,
            value,
            consistent=consistent,
            select_attributes=select_attributes,
            range_key_qualifier=rq,
            limit=limit,
            last_evaluated_key=last_evaluated_key,
            filter_operations=filters
        )
        if select_attributes is None:
            rset = map(self.deserialize_record, rset)
        return QueryResultSet(rset, lambda: rset.next_key)

    def query(self,
              *args,
              consistent: bool = False,
              start_after=None,
              limit: int = None,
              last_evaluated_key=None,
              range_filter: Optional[FilterOperation] = None,
              filters: Union[FilterOperation, Collection[FilterOperation]] = None
              ) -> QueryResult:
        rset = self.query_set(
            *args,
            consistent=consistent,
            start_after=start_after,
            limit=limit,
            last_evaluated_key=last_evaluated_key,
            range_filter=range_filter,
            filters=filters
        )
        return QueryResult(list(rset), rset.next_token)

    def prepare_item(self, entry: Record) -> Dict[str, Any]:
        item = entry.to_record()
        self.primary_key.prep_for_serialization(item)
        return item

    def deserialize_record(self, item: DynamoDbRow):
        self.primary_key.prep_for_deserialization(item)
        return self.initializer(item)

    def prepare_put(self, item: DynamoDbRow):
        pass

    def create_put_item_request(self, entry: Record, **kwargs):
        item = self.prepare_item(entry)
        if len(kwargs) > 0:
            item.update(kwargs)
        self.prepare_put(item)
        return PutItemRequest(
            self.table_name,
            item,
            key_attributes=self.primary_key.key_attributes,
            virtual_table_name=self.__get_virtual_table_name()
        )

    def create_update_item_request_from_args(self, patch: Dict[str, Any], *args,
                                             must_exist: bool = True) -> UpdateItemRequest:
        key, _ = self.primary_key.build_key_from_args(*args)
        return UpdateItemRequest(
            self.table_name,
            key,
            patch,
            must_exist=must_exist,
            virtual_table_name=self.__get_virtual_table_name()
        )

    def create_update_item_request(self, entry: Record, patches: Dict[str, Any], must_exist: bool = True):
        item = self.prepare_item(entry)
        key = self.primary_key.build_key_as_dict(item, pre_serialized=True)
        return UpdateItemRequest(
            self.table_name,
            key,
            item=patches,
            must_exist=must_exist,
            virtual_table_name=self.__get_virtual_table_name()
        )

    def create_delete_item_request_from_args(self, *args, must_exist: bool = False) -> DeleteItemRequest:
        key, _ = self.primary_key.build_key_from_args(*args)
        return DeleteItemRequest(
            self.table_name,
            key,
            must_exist=must_exist,
            virtual_table_name=self.__get_virtual_table_name()
        )

    def create_delete_item_request(self, entry: Record, must_exist: bool = False) -> DeleteItemRequest:
        item = self.prepare_item(entry)
        key = self.primary_key.build_key_as_dict(item, pre_serialized=True)
        return DeleteItemRequest(
            self.table_name,
            key,
            must_exist=must_exist,
            virtual_table_name=self.__get_virtual_table_name()
        )

    def transact_write(self, requests: Union[List[TransactionRequest], Tuple]) -> Optional[TransactionRequest]:
        try:
            self.ddb.transact_write(requests)
            return None
        except TransactionCancelledException as ex:
            index = 0
            for r in ex.reasons:
                if r.code is not None:
                    req = requests[index]
                    req.cancel_reason = r
                    return req
                index += 1
            raise ex

from collections.abc import Callable
from typing import Optional, Dict, Any

from retry import retry

from aws.dynamodb import DynamoDb
from repos import OptimisticLockException
from repos.aws import RESOURCE_LOCK_TABLE
from repos.aws.abstract_table_repo import AwsVirtualTableRepo
from repos.resource_lock import ResourceLockRepo, ResourceLock
from utils import date_utils
from utils.date_utils import EpochSeconds

EXPIRE_AT = "expireAt"


class LocalDto:
    def __init__(self,
                 resource_name: str,
                 timeout_at: Optional[int]):
        self.resource_name = resource_name
        self.timeout_at = timeout_at

    def to_record(self) -> Dict[str, Any]:
        return {
            'resourceName': self.resource_name,
            'expireAt': self.timeout_at
        }

    @classmethod
    def from_record(cls, record: Dict[str, Any]):
        return cls(
            record['resourceName'],
            record.get('expireAt')
        )


class _LockImpl(ResourceLock):

    def __init__(self, name: str,
                 timeout_at: EpochSeconds,
                 refresh_seconds: int,
                 releaser: Callable[['_LockImpl'], bool],
                 refresher: Callable[['_LockImpl'], bool]):
        self.name = name
        self.timeout_at = timeout_at
        self.refresh_seconds = refresh_seconds
        self.refresher = refresher
        self.releaser = releaser
        self.__release_result: Optional[bool] = None

    def refresh(self) -> bool:
        assert self.__release_result is None, "Already released"
        return self.refresher(self)

    def release(self) -> bool:
        if self.__release_result is None:
            self.__release_result = self.releaser(self)
        return self.__release_result


class AwsResourceLockRepo(AwsVirtualTableRepo, ResourceLockRepo):
    __hash_key_attributes__ = {
        'resourceName': str,
    }

    __initializer__ = LocalDto.from_record
    __virtual_table__ = RESOURCE_LOCK_TABLE

    def __init__(self, ddb: DynamoDb):
        super(AwsResourceLockRepo, self).__init__(ddb)

    def __releaser(self, lock: _LockImpl) -> bool:
        dto = LocalDto(lock.name, lock.timeout_at)
        try:
            self.delete_with_condition(dto, EXPIRE_AT, dto.timeout_at)
            return True
        except OptimisticLockException:
            return False

    def __refresher(self, lock: _LockImpl) -> bool:
        target_time = date_utils.get_epoch_seconds_in_future(lock.refresh_seconds)
        dto = LocalDto(lock.name, lock.timeout_at)
        try:
            self.patch_with_condition(dto, EXPIRE_AT, target_time)
            lock.timeout_at = target_time
            return True
        except OptimisticLockException:
            pass
        # See if we can create it again (perhaps it just expired)
        if self.create(dto):
            lock.timeout_at = target_time
            return True

        return False

    @retry(exceptions=OptimisticLockException, tries=10, delay=.01, max_delay=10, backoff=.05, jitter=(.01, .5))
    def try_acquire(self, name: str, expire_seconds: int) -> Optional[ResourceLock]:
        # 880 - we should never expect to keep something locked for longer than a lambda session
        assert 0 < expire_seconds < 880
        now = date_utils.get_system_time_in_seconds()
        target_time = date_utils.get_epoch_seconds_in_future(expire_seconds)
        dto = LocalDto(name, target_time)
        # Attempt to create it
        if not self.create(dto):
            # It exists, so grab the current expiration time
            current: LocalDto = self.find(name, consistent=True)
            if current is None:
                # Try the create again
                if not self.create(dto):
                    # Looks like we are competing
                    return None
            else:
                # >= - for grace period of 1 second
                if current.timeout_at >= now:
                    return None
                # Try to grab it. Note that it throws OptimisticLockException if it is updated before we can do it.
                # We should retry in that case (due to the retry decorator)
                self.patch_with_condition(current, EXPIRE_AT, dto.timeout_at)
        return _LockImpl(
            name,
            target_time,
            expire_seconds,
            self.__releaser,
            self.__refresher
        )

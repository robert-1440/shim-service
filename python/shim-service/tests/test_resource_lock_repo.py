from typing import Optional

from base_test import BaseTest
from bean import beans, BeanName
from repos.aws.aws_resource_lock import AwsResourceLockRepo, LocalDto
from repos.resource_lock import ResourceLock
from utils import date_utils

_RESOURCE_NAME = "tenants/1/sessions/1"


class ResourceLockTests(BaseTest):
    repo: AwsResourceLockRepo

    def test_basic(self):
        lock = self.acquire()
        self.assertIsNotNone(lock)
        self.assertTrue(lock.refresh())
        self.assertTrue(lock.release())

    def test_auto(self):
        repo = self.repo

        hits = 0

        def update_hit():
            nonlocal hits
            hits += 1

        self.ddb_mock.set_update_callback(update_hit)

        lock = repo.try_acquire_auto_refresh_lock(_RESOURCE_NAME, 30)
        self.assertIsNotNone(lock)
        self.assertTrue(lock.release())

        # We're making sure the refresh was never called
        self.assertEqual(0, hits)

        self.assertTrue(lock.release())

    def test_more_contention(self):
        #
        # Attempt to acquire a lock that exists, but is removed before being able to get the record
        #
        repo = self.repo

        # Get the lock
        lock = self.acquire()

        # Set it up so that we release the lock as we try to find it
        self.ddb_mock.set_get_callback(lambda: lock.release())

        new_lock = repo.try_acquire(_RESOURCE_NAME, 30)
        self.assertIsNotNone(new_lock)

        # Same as before, but, simulate another process locking it after the find
        self.ddb_mock.set_get_callback(lambda: new_lock.release())

        put_count = 0

        # We need to take action only after the second put attempt
        def putter():
            nonlocal put_count
            put_count += 1
            if put_count == 2:
                self.acquire()
                return False
            return True

        self.ddb_mock.set_put_callback(putter)

        new_lock = self.acquire()
        self.assertIsNone(new_lock)

        repo.delete(_RESOURCE_NAME)
        new_lock = self.acquire()

        # Now simulate the case where
        # 1. We go to lock an expired lock
        # 2. We attempt to patch the lock
        # 3. The process with the lock refreshes before the patch
        #
        # We are ensuring that a retry is done in this case
        #
        self._expire_lock(new_lock)

        # Set up the refresh as we go to patch
        self.ddb_mock.set_update_callback(lambda: new_lock.refresh())

        self.assertIsNone(self.acquire())

    def test_refresh_after_expiration(self):
        #
        # Test the case where we have a lock, but are unable to refresh before it expires.
        # No other process has the lock, so we should be able to lock it.
        #
        repo = self.repo
        lock = repo.try_acquire(_RESOURCE_NAME, 30)
        self.assertIsNotNone(lock)

        # Delete it (simulates expiration)
        self.assertTrue(repo.delete(_RESOURCE_NAME))
        # Double check
        self.assertIsNone(repo.find(_RESOURCE_NAME))

        self.assertTrue(lock.refresh())

        # Double check
        self.assertIsNotNone(repo.find(_RESOURCE_NAME))

    def test_again(self):
        repo = self.repo
        name = _RESOURCE_NAME

        lock = repo.try_acquire(name, 30)
        self.assertIsNotNone(lock)

        new_lock = repo.try_acquire(name, 30)
        self.assertIsNone(new_lock)

        dto = LocalDto(name, 0)
        # Move it back
        stamp = date_utils.get_epoch_seconds_in_future(-15)
        repo.patch(dto, {'expireAt': stamp})

        # Make sure
        dto = repo.find(name)
        self.assertEqual(stamp, dto.timeout_at)

        # Hack so we can refresh
        lock.timeout_at = stamp

        # Refresh
        self.assertTrue(lock.refresh())
        dto = repo.find(name)
        self.assertGreater(dto.timeout_at, stamp)

        self._expire_lock(lock)

        # Now we should be able to obtain the lock
        new_lock = repo.try_acquire(name, 30)
        self.assertIsNotNone(new_lock)

        # The refresh of the first one should fail
        self.assertFalse(lock.refresh())

        # Release too
        self.assertFalse(lock.release())

        self.assertTrue(new_lock.refresh())
        self.assertTrue(new_lock.release())

    def setUp(self) -> None:
        super().setUp()
        self.repo = beans.get_bean_instance(BeanName.RESOURCE_LOCK_REPO)

    def tearDown(self) -> None:
        beans.reset()

    def _expire_lock(self, lock: ResourceLock):
        stamp = date_utils.get_epoch_seconds_in_future(-31)
        dto = LocalDto(lock.name, stamp)
        self.repo.patch(dto, {'expireAt': stamp})
        lock.timeout_at = stamp

    def acquire(self, must_succeed: bool = False) -> Optional[ResourceLock]:
        lock = self.repo.try_acquire(_RESOURCE_NAME, 30)
        if must_succeed:
            self.assertTrue(lock, "Expected lock to succeed.")
        return lock

import abc
from typing import Any, Dict

from lambda_web_framework import InvocableBeanRequestHandler
from poll.polling_group import AbstractProcessorGroup
from repos.resource_lock import ResourceLockRepo
from utils import loghelper
from utils.date_utils import get_system_time_in_millis, format_elapsed_time_seconds

logger = loghelper.get_logger(__name__)


class BasePollingProcessor(InvocableBeanRequestHandler, metaclass=abc.ABCMeta):

    def __init__(self,
                 resource_lock_repo: ResourceLockRepo,
                 max_collect_seconds: int
                 ):
        self.resource_lock_repo = resource_lock_repo
        self.max_collect_seconds = max_collect_seconds

    @classmethod
    @abc.abstractmethod
    def lock_name(cls) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def create_group(self) -> AbstractProcessorGroup:
        raise NotImplementedError()

    def invoke(self, parameters: Dict[str, Any]):

        # We want to lock during collection to avoid as many collisions on individual events found as possible
        lock = self.resource_lock_repo.try_acquire(self.lock_name(), self.max_collect_seconds + 2)
        if lock is None:
            logger.info("Another poller is collecting sessions.")
            return

        with lock:
            group = self.create_group()
            group.collect()

        if group.is_empty():
            logger.info("No sessions to poll.")
            return

        start_time = get_system_time_in_millis()
        try:
            logger.info(f"Starting poll for {group.thread_count()} session(s) ...")

            with group:
                while not group.join(30):
                    elapsed = format_elapsed_time_seconds(start_time)
                    logger.info(f"Number of threads still running: {group.thread_count()}, up time={elapsed} seconds.")
        finally:
            logger.info(f"Stopping, elapsed time = {format_elapsed_time_seconds(start_time)}.")

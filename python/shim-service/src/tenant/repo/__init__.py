import abc
from copy import copy
from typing import Any, Optional

from bean import inject, BeanName
from repos import QueryResult
from tenant import PendingTenantEvent, PendingTenantEventType, TenantContextType, TenantContext


class PendingTenantEventRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def update_or_create(self, event: PendingTenantEvent):
        raise NotImplementedError()

    @abc.abstractmethod
    def update_action_time(self, event: PendingTenantEvent, seconds_in_future: int) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_event(self, event: PendingTenantEvent) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def query_events(self, event_type: PendingTenantEventType, limit: int, next_token: Any) -> QueryResult:
        raise NotImplementedError()


class TenantContextRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def find_context(self, context_type: TenantContextType, tenant_id: int) -> Optional[TenantContext]:
        raise NotImplementedError()

    @abc.abstractmethod
    def update_or_create_context(self, context: TenantContext):
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_context(self, context: TenantContext) -> bool:
        raise NotImplementedError()


@inject(bean_instances=BeanName.TENANT_CONTEXT_REPO)
def set_context_data(context: TenantContext, data: bytes, repo: TenantContextRepo):
    new_context = copy(context)
    new_context.data = data
    repo.update_or_create_context(new_context)

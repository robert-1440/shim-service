import abc

from repos import QueryResult


class EventsRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def query_events(self, tenant_id: int,
                     limit: int = 100,
                     last_seq_no: int = None) -> QueryResult:
        raise NotImplementedError()

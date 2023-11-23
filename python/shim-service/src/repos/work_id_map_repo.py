import abc
from typing import Optional, Any, Dict

from lambda_web_framework.web_exceptions import InvalidParameterException, NotFoundException


class WorkIdMap:
    def __init__(self, tenant_id: int, user_id: str, work_id: str, work_target_id: str, session_id: str):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.work_id = work_id
        self.work_target_id = work_target_id
        self.session_id = session_id

    def to_record(self) -> Dict[str, Any]:
        return {
            'tenantId': self.tenant_id,
            'userId': self.user_id,
            'workId': self.work_id,
            'workTargetId': self.work_target_id,
            'sessionId': self.session_id
        }

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> 'WorkIdMap':
        return cls(
            record['tenantId'],
            record['userId'],
            record['workId'],
            record['workTargetId'],
            record['sessionId']
        )


class WorkIdMapRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def find_work(self, tenant_id: int, work_target_id: str) -> Optional[WorkIdMap]:
        raise NotImplementedError()

    def get_work_id(self, tenant_id: int, user_id: str, work_target_id: str, in_path: bool = False) -> str:
        w = self.find_work(tenant_id, work_target_id)
        if w is None:
            if in_path:
                raise NotFoundException("Unable to find specified workTargetId.")
            else:
                raise InvalidParameterException("workTargetId", "Unable to find workId for given workTargetId")
        elif w.user_id != user_id:
            raise InvalidParameterException("workTargetId", "workTargetId is not owned by the given user.")
        return w.work_id

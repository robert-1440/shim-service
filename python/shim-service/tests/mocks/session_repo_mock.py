from typing import List, Callable, Any

from aws.dynamodb import DynamoDb
from repos.aws.aws_events import AwsEventsRepo
from repos.aws.aws_sequence import AwsSequenceRepo
from repos.aws.aws_sessions import AwsSessionsRepo
from repos.aws.aws_sfdc_sessions_repo import AwsSfdcSessionsRepo
from repos.aws.aws_user_sessions import AwsUserSessionsRepo
from session import Session

Hook = Callable[[Session], Any]


class MockAwsSessionsRepo(AwsSessionsRepo):

    def __init__(self,
                 dynamodb: DynamoDb,
                 user_sessions_repo: AwsUserSessionsRepo,
                 events_repo: AwsEventsRepo,
                 sequence_repo: AwsSequenceRepo,
                 sfdc_sessions_repo: AwsSfdcSessionsRepo):
        super(MockAwsSessionsRepo, self).__init__(
            dynamodb,
            user_sessions_repo,
            events_repo,
            sequence_repo,
            sfdc_sessions_repo
        )
        self.update_hooks: List[Hook] = []
        self.touch_hooks: List[Hook] = []
        self.delete_hooks: List[Hook] = []
        self.hooks_disabled = False

    def update_session(self, session: Session) -> bool:
        self.__check_hooks(self.update_hooks, session)
        return super().update_session(session)

    def add_update_hook(self, hook: Hook):
        self.update_hooks.append(hook)

    def add_delete_hook(self, hook: Hook):
        self.delete_hooks.append(hook)

    def add_touch_hook(self, hook: Hook):
        self.touch_hooks.append(hook)

    def assert_no_update_hooks(self):
        assert len(self.update_hooks) == 0, "Expected no update hooks."

    def assert_no_delete_hooks(self):
        assert len(self.delete_hooks) == 0, "Expected no delete hooks."

    def touch(self, session: Session):
        self.__check_hooks(self.touch_hooks, session)
        return super().touch(session)

    def delete_session(self, session: Session) -> bool:
        self.__check_hooks(self.delete_hooks, session)
        return super().delete_session(session)

    def __check_hooks(self, hook_list: List[Hook], session: Session):
        if not self.hooks_disabled and len(hook_list) > 0:
            hook = hook_list.pop(0)
            with self:
                hook(session)

    def __enter__(self):
        self.hooks_disabled = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.hooks_disabled = False

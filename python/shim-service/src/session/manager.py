from copy import copy
from typing import List, Optional

from retry import retry

from auth import Credentials
from bean import BeanName
from bean.beans import inject
from instance import Instance
from lambda_pkg import LambdaInvoker
from lambda_web_framework.web_exceptions import NotAuthorizedException, GoneException, BadRequestException, \
    LambdaHttpException
from lambda_web_framework.web_router import LambdaHttpRequest
from poll import PollingPlatform
from push_notification import PushNotificationContextSettings
from repos import OptimisticLockException
from repos.session_contexts import SessionContextsRepo
from repos.sessions_repo import SessionsRepo, UserSessionExistsException, CreateSessionRequest
from repos.user_sessions import UserSessionsRepo
from services.sfdc.live_agent import LiveAgentWebSettings, PresenceStatus
from services.sfdc.sfdc_session import create_sfdc_session_from_session, SfdcSession, load_with_context
from session import Session, SessionStatus, verify_session_status, ContextType, SessionContext
from session.token import SessionToken
from utils import loghelper, exception_utils

logger = loghelper.get_logger(__name__)


class CreateResult:
    def __init__(self, session: Session, created: bool, presence_statuses: Optional[List[PresenceStatus]]):
        self.session = session
        self.created = created
        self.presence_statuses = presence_statuses


class RetryCounter:
    def __init__(self, max_retries: int):
        self.max_retries = max_retries
        self.count = 0
        self.created = False
        self.no_change = False

    def inc(self):
        if self.count < self.max_retries:
            self.count += 1
            return True
        return False


def __check_replace_session(sessions_repo: SessionsRepo,
                            session_request: CreateSessionRequest,
                            existing_session_id: str,
                            retry_counter: RetryCounter) -> Session:
    session = session_request.session
    current = sessions_repo.find_session(session.key_of(session.tenant_id, existing_session_id))
    if current is not None and current.status != SessionStatus.FAILED:
        # Can the session be replaced?
        if not current.can_replace_session(session):
            raise UserSessionExistsException(existing_session_id)

        # Is there any need to replace the session?
        if not current.should_replace_session(session):
            # If the update time is old enough, go ahead and touch it
            if session.update_time - current.update_time < 60 or sessions_repo.touch(current):
                return current
        else:
            # Try to update the session
            session_copy = copy(session)
            session_copy.state_counter = current.state_counter
            session_copy.session_id = current.session_id
            if sessions_repo.update_session(session_copy):
                return session_copy
    else:
        # This means the user session is an orphan (most likely, the session expired), or the session failed.
        # Let's delete it and try again
        sessions_repo.fix_orphaned_session(session, existing_session_id)

    return __create_session(sessions_repo, session_request, retry_counter)


def __create_session(sessions_repo: SessionsRepo,
                     session_request: CreateSessionRequest,
                     retry_counter: RetryCounter):
    try:
        sessions_repo.create_session(session_request)
        retry_counter.created = True
        return session_request.session
    except UserSessionExistsException as ex:
        if not retry_counter.inc():
            raise ex
        session_id = ex.session_id

    return __check_replace_session(sessions_repo, session_request, session_id, retry_counter)


def __build_request(instance: Instance, session: Session) -> CreateSessionRequest:
    return CreateSessionRequest(session, instance.config.worker_timeout_seconds)


@inject(bean_instances=BeanName.USER_SESSIONS_REPO)
def __check_fcm_token(instance: Instance,
                      session: Session,
                      user_sessions_repo: UserSessionsRepo):
    current_session = user_sessions_repo.find_user_session(session)

    # We'll assume we don't have to check the token if we've already done so
    if current_session is not None and current_session.fcm_device_token == session.fcm_device_token:
        return
    message = instance.verify_fcm_device_token(session.fcm_device_token)
    if message is not None:
        raise BadRequestException(f"FCM device token validation failed: {message}",
                                  error_code="InvalidFcmDeviceToken")


def __construct_web_context(session: Session):
    return SessionContext(
        tenant_id=session.tenant_id,
        session_id=session.session_id,
        user_id=session.user_id,
        context_type=ContextType.WEB,
        session_data=LiveAgentWebSettings().serialize()
    )


def __construct_push_notification_context(session: Session):
    return SessionContext(
        tenant_id=session.tenant_id,
        session_id=session.session_id,
        user_id=session.user_id,
        context_type=ContextType.PUSH_NOTIFIER,
        session_data=PushNotificationContextSettings().serialize()
    )


@inject(bean_instances=(BeanName.LIVE_AGENT_POLLER_PLATFORM, BeanName.SESSION_CONTEXTS_REPO, BeanName.LAMBDA_INVOKER))
def __connect_to_sfdc(session: Session, live_agent_platform: PollingPlatform,
                      contexts_repo: SessionContextsRepo,
                      lambda_invoker: LambdaInvoker) -> SfdcSession:
    sfdc_sess = create_sfdc_session_from_session(session)
    # Create the required session contexts
    contexts = [__construct_web_context(session), __construct_push_notification_context(session)]
    if session.has_live_agent_polling():
        contexts.append(live_agent_platform.create_session_context(session))
    if not contexts_repo.create_session_contexts(session, sfdc_sess, contexts):
        raise OptimisticLockException()
    if session.has_live_agent_polling():
        lambda_invoker.invoke_live_agent_poller()
    return sfdc_sess


@inject(bean_instances=BeanName.SESSIONS_REPO)
@retry(
    exceptions=OptimisticLockException,
    tries=10,
    delay=.1,
    max_delay=5,
    backoff=.1
)
def finish_connection(tenant_id: int, session_id: str, repo: SessionsRepo):
    session = repo.get_session(Session.key_of(tenant_id, session_id), allow_pending=True, allow_failure=False)
    # Already active, should be fine
    if session.status == SessionStatus.ACTIVE:
        return
    __connect_to_sfdc(session)


@inject(bean_instances=BeanName.LAMBDA_INVOKER)
def __connect_session_async(session: Session,
                            sessions_repo: SessionsRepo,
                            invoker: LambdaInvoker):
    try:
        invoker.invoke_connect_session(session)
    except Exception as ex:
        message = exception_utils.get_exception_message(ex)
        logger.error(exception_utils.dump_ex(ex))
        session = sessions_repo.find_session(session)
        if session is not None:
            session.set_failed(message)
            sessions_repo.update_session(session)
        raise LambdaHttpException(502, message)


@inject(bean_instances=(BeanName.INSTANCE, BeanName.SESSIONS_REPO))
def create_session(session: Session,
                   async_connect: bool,
                   instance: Instance,
                   sessions_repo: SessionsRepo) -> CreateResult:
    __check_fcm_token(instance, session)

    counter = RetryCounter(instance.config.max_create_session_retries)
    session_request = __build_request(instance, session)
    result_session = __create_session(sessions_repo, session_request, counter)
    presence_statuses: Optional[List[PresenceStatus]] = None
    if counter.created:
        if async_connect:
            __connect_session_async(result_session, sessions_repo)
        else:
            sfdc_sess: SfdcSession = __connect_to_sfdc(session)
            presence_statuses = sfdc_sess.get_presence_statuses()
    elif result_session.status == SessionStatus.ACTIVE:
        sac = load_with_context(result_session, ContextType.WEB)
        if sac is not None:
            presence_statuses = sac.session.get_presence_statuses()

    return CreateResult(result_session, counter.created, presence_statuses)


@inject(bean_instances=BeanName.SESSIONS_REPO)
def verify_session(request: LambdaHttpRequest, creds: Credentials, sessions_repo: SessionsRepo):
    request.set_session(__load_session(sessions_repo, request, creds=creds))


@inject(bean_instances=BeanName.SESSIONS_REPO)
def keepalive(token_string: str,
              request: LambdaHttpRequest,
              sessions_repo: SessionsRepo) -> int:
    session = __load_session(sessions_repo, request, token_string=token_string)
    result = sessions_repo.touch(session)
    if result is None:
        raise GoneException("Session no longer exists.")
    return result


@inject(bean_instances=BeanName.SESSIONS_REPO)
def delete_session_by_token(token_string: str,
                            request: LambdaHttpRequest,
                            sessions_repo: SessionsRepo) -> bool:
    session = __load_session(sessions_repo, request, token_string=token_string,
                             allow_pending=True,
                             allow_failure=True)
    return sessions_repo.delete_session(session)


def __load_session(sessions_repo: SessionsRepo,
                   request: LambdaHttpRequest,
                   creds: Credentials = None,
                   token_string: str = None,
                   allow_pending: bool = False,
                   allow_failure: bool = False) -> Session:
    if token_string is None:
        in_path = False
        token_string = request.get_header('x-1440-session-token')
        if token_string is None:
            raise NotAuthorizedException('Missing X-1440-Session-Token header')
    else:
        in_path = True
    creds: Credentials = request.get_credentials() if creds is None else creds
    token = SessionToken.deserialize(creds, token_string)
    creds.assert_tenant_access(token.tenant_id)
    session = sessions_repo.get_session(
        token,
        in_path=in_path,
        allow_pending=True,
        allow_failure=allow_failure
    )
    if session.user_id != token.user_id:
        raise NotAuthorizedException("User id mismatch in token.")
    if not allow_pending or not allow_failure:
        verify_session_status(session, pending_ok=allow_pending)
    return session

from grpc import ChannelCredentials

from bean import beans, BeanName
from poll.platform_event import EMPTY_CONTEXT
from poll.platform_event.pubsub_service import PubSubService
from support import salesforce_auth
from tenant import TenantContext, TenantContextType, PendingTenantEvent, PendingTenantEventType

service: PubSubService = beans.get_bean_instance(BeanName.PUBSUB_SERVICE)
auth_info = salesforce_auth.get_auth_info()

credentials: ChannelCredentials = beans.get_bean_instance(BeanName.SECURE_CHANNEL_CREDENTIALS)
context = TenantContext(TenantContextType.X1440, 1000, 0, EMPTY_CONTEXT)
event = PendingTenantEvent(
    PendingTenantEventType.X1440_POLL,
    auth_info.org_id,
    1000,
    auth_info.session_id,
    auth_info.origin
)
stream = service.create_stream(credentials, context, event, "test", 10)
for event in stream:
    print("Huh?")

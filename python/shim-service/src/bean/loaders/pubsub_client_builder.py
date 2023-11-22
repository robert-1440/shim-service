from grpc.beta.implementations import ChannelCredentials

from bean import inject, BeanName
from poll.platform_event.grpc_pubsub_client import GrpcPubSubClientBuilder
from poll.platform_event.schema_cache import SchemaCache


@inject(bean_instances=(BeanName.SECURE_CHANNEL_CREDENTIALS, BeanName.SCHEMA_CACHE))
def init(credentials: ChannelCredentials, schema_cache: SchemaCache):
    return GrpcPubSubClientBuilder(credentials, schema_cache)

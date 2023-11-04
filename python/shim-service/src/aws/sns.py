from typing import Any, Dict, List

from aws import paginate_all


class Subscription:
    def __init__(self, node: Dict[str, Any]):
        self.arn = node['SubscriptionArn']
        self.owner = node.get('Owner')
        self.protocol = node.get('Protocol')
        self.endpoint = node.get('Endpoint')
        self.topic_arn = node.get("TopicArn")


class Sns:
    def __init__(self, client: Any):
        self.__client = client

    def list_subscriptions(self, topic_arn: str) -> List[Subscription]:
        return paginate_all(self.__client, "list_subscriptions_by_topic", "Subscriptions",
                            lambda n: Subscription(n), TopicArn=topic_arn)

    def subscribe(self, topic_arn: str,
                  protocol: str,
                  endpoint: str,
                  attributes: Dict[str, Any] = None):
        params = {"TopicArn": topic_arn,
                  "Protocol": protocol,
                  "Endpoint": endpoint}
        if attributes is not None and len(attributes) > 0:
            params['Attributes'] = attributes
        self.__client.subscribe(**params)

    def unsubscribe(self, subscription_arn: str):
        self.__client.unsubscribe(SubscriptionArn=subscription_arn)

    def get_subscription_attributes(self, subscription: Subscription) -> Dict[str, Any]:
        if subscription.arn == 'PendingConfirmation':
            return {'PendingConfirmation': "true"}
        return self.__client.get_subscription_attributes(SubscriptionArn=subscription.arn)['Attributes']

    def publish(self, topic_arn: str, subject: str, message: str):
        self.__client.publish(TopicArn=topic_arn,
                              Subject=subject,
                              Message=message)

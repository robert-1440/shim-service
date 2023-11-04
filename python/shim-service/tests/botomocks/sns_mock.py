import json
from typing import List, Optional, Any, Dict

from botomocks import assert_empty, raise_not_found, BaseMockClient, MockPaginator, raise_invalid_parameter


class Notification:
    def __init__(self, topic_arn: str, subject: str, message: str):
        self.topic_arn = topic_arn
        self.subject = subject
        self.message = message

    def __str__(self):
        return json.dumps(self.__dict__, indent=True)

    def __repr__(self):
        return self.__str__()


class MockSubscription:
    def __init__(self, topic_arn: str, protocol: str, endpoint: str, attributes: Optional[dict]):
        self.topic_arn = topic_arn
        self.protocol = protocol
        self.endpoint = endpoint
        self.attributes: Optional[Dict[str, str]] = attributes
        self.sub_attributes = {'PendingConfirmation': 'true'}
        self.arn = 'PendingConfirmation'

    def confirmed(self):
        self.arn = f'sns:{self.topic_arn}:{self.protocol}:{self.endpoint}'
        self.sub_attributes.pop('PendingConfirmation')


class MockSnsClient(BaseMockClient):
    def __init__(self):
        super(MockSnsClient, self).__init__()
        self.notifications: List[Notification] = []
        self.subscriptions: List[MockSubscription] = []

    def pop_notification(self, topic_arn: str = None) -> Notification:
        if topic_arn is None:
            return self.notifications.pop(0)
        for n in filter(lambda nf: nf.topic_arn == topic_arn, self.notifications):
            self.notifications.remove(n)
            return n
        raise AssertionError(f"No notification found for topic {topic_arn}.")

    def set_confirmed(self, topic_arn: str, email_address: str):
        for sub in filter(lambda s: s.topic_arn == topic_arn and s.endpoint == email_address, self.subscriptions):
            sub.confirmed()
            return
        raise AssertionError(f"Can't find {email_address} for topic {topic_arn}")

    def assert_no_notifications(self):
        assert len(self.notifications) == 0, f"Was not expecting notifications. Got: {self.notifications}"

    def subscribe(self, **kwargs):
        topic_arn = kwargs.pop('TopicArn')
        protocol = kwargs.pop('Protocol')
        endpoint: str = kwargs.pop('Endpoint')
        attributes = kwargs.pop('Attributes', None)
        assert_empty(kwargs)

        assert protocol == 'email'
        lwr = endpoint.lower()

        # This is just for our sanity, make sure we don't allow duplicates
        for _ in filter(lambda sub: sub.endpoint.lower() == lwr, self.subscriptions):
            raise AssertionError("Subscription already exists.")

        self.subscriptions.append(MockSubscription(topic_arn, protocol, endpoint, attributes))

    def unsubscribe(self, **kwargs):
        sub_arn = kwargs.pop('SubscriptionArn')
        assert_empty(kwargs)

        if ":" not in sub_arn:
            raise_invalid_parameter("GetSubscriptionAttributes", "ARN is invalid")

        for sub in filter(lambda sub: sub.arn == sub_arn, self.subscriptions):
            self.subscriptions.remove(sub)
            return
        raise raise_not_found('Unsubscribe', 'Unable to find subscription')

    def publish(self, **kwargs):
        topic_arn = kwargs.pop("TopicArn")
        subject = kwargs.pop("Subject")
        message = kwargs.pop("Message")
        assert_empty(kwargs)
        self.notifications.append(Notification(topic_arn, subject, message))

    def list_subscriptions_by_topic(self, **kwargs):
        topic_arn = kwargs.pop("TopicArn")
        assert_empty(kwargs)
        subs = []
        results = {'Subscriptions': subs}
        for sub in filter(lambda s: s.topic_arn == topic_arn, self.subscriptions):
            entry = {
                'SubscriptionArn': sub.arn,
                'Owner': 'somebody',
                'Protocol': sub.protocol,
                'Endpoint': sub.endpoint,
                'TopicArn': sub.topic_arn
            }
            subs.append(entry)
        return results

    def get_subscription_attributes(self, **kwargs):
        arn = kwargs.pop("SubscriptionArn")
        assert_empty(kwargs)

        if ":" not in arn:
            raise_invalid_parameter("GetSubscriptionAttributes", "ARN is invalid")

        for sub in filter(lambda s: s.arn == arn, self.subscriptions):
            sub: MockSubscription
            atts = {} if sub.attributes is None else dict(sub.attributes)
            atts.update(sub.sub_attributes)
            return {'Attributes': atts}
        raise_not_found("GetSubscriptionAttributes", "Unable to find subscription")

    def create_paginator(self, name: str):
        if name != "list_subscriptions_by_topic":
            raise NotImplementedError(f"{name} not supported.")

        def inner(params: Dict[str, Any]):
            return self.list_subscriptions_by_topic(**params)

        return MockPaginator("Subscriptions", result_loader=inner)

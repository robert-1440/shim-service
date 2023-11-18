from typing import Any


class Sns:
    def __init__(self, client: Any):
        self.__client = client

    def publish(self, topic_arn: str, subject: str, message: str):
        self.__client.publish(TopicArn=topic_arn,
                              Subject=subject,
                              Message=message)

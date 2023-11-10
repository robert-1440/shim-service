from typing import Dict

from botomocks import BaseMockClient, assert_empty, raise_not_found
from utils import dict_utils


class Queue:
    def __init__(self, url: str):
        self.url = url
        self.groups = {}

    def send_message(self, group_id: str, message: str):
        group_list = dict_utils.get_or_create(self.groups, group_id, list)
        group_list.append(message)

    def pop_message(self, group_id: str) -> str:
        group_list = self.groups[group_id]
        return group_list.pop(0)


class MockSqsClient(BaseMockClient):

    def __init__(self):
        super(MockSqsClient, self).__init__()
        self.queues: Dict[str, Queue] = {}

    def get_queue(self, url: str) -> Queue:
        return self.queues[url]

    def send_message(self, **kwargs):
        queue_url = kwargs.pop('QueueUrl')
        message_body = kwargs.pop('MessageBody')
        message_group = kwargs.pop('MessageGroupId')

        assert_empty(kwargs)
        queue = dict_utils.get_or_create(self.queues, queue_url, lambda: Queue(queue_url))
        if queue is None:
            raise_not_found("SendMessage", "Queue does not exist")
        queue.send_message(message_group, message_body)
        return {}

    def create_paginator(self, operation_name: str):
        pass

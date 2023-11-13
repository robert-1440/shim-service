import json
from threading import RLock
from typing import Dict

import app
from bean import BeanName
from botomocks import BaseMockClient, assert_empty, raise_not_found
from support.thread_utils import synchronized
from utils import dict_utils


class Queue:
    def __init__(self, url: str):
        self.url = url
        self.groups = {}

    def send_message(self, group_id: str, message: str):
        group_list = dict_utils.get_or_create(self.groups, group_id, list)
        group_list.append(message)

    def pop_message(self, group_id: str = "") -> str:
        group_list = self.groups[group_id]
        return group_list.pop(0)


class MockSqsClient(BaseMockClient):

    def __init__(self):
        super(MockSqsClient, self).__init__()
        self.mutex = RLock()
        self.queues: Dict[str, Queue] = {}

    def get_queue(self, url: str) -> Queue:
        return self.queues[url]

    @synchronized
    def send_message(self, **kwargs):
        queue_url = kwargs.pop('QueueUrl')
        message_body = kwargs.pop('MessageBody')
        message_group = kwargs.pop('MessageGroupId', "")
        kwargs.pop('DelaySeconds', None)

        assert_empty(kwargs)
        queue: Queue = dict_utils.get_or_create(self.queues, queue_url, lambda: Queue(queue_url))
        if queue is None:
            raise_not_found("SendMessage", "Queue does not exist")
        queue.send_message(message_group, message_body)
        return {}

    @synchronized
    def invoke_schedules(self, bean_name: BeanName):
        for q in self.queues.values():
            g = q.groups.get("")
            if g is not None:
                for message in list(g):
                    record = json.loads(message)
                    if bean_name is not None:
                        if record['bean'] != bean_name.name:
                            continue
                    app.handler(record, None)
                    g.remove(message)

        pass

    def create_paginator(self, operation_name: str):
        pass

    @synchronized
    def clear_schedules(self, url: str):
        q = self.queues.get(url)
        if q is not None:
            q.groups.clear()

    @synchronized
    def pop_schedule(self, url: str) -> dict:
        q = self.queues.get(url)
        if q is None:
            raise AssertionError(f"Unable to find queue url in {self.queues.keys()}")
        g = q.groups.get("")
        if g is not None:
            for message in g:
                record = json.loads(message)
                g.remove(message)
                return record

        raise AssertionError("No messages found for {url}")

    def assert_no_schedules(self, url: str):
        q = self.queues.get(url)
        if q is not None:
            g = q.groups.get("")
            if g is not None:
                if len(g) > 0:
                    raise AssertionError(f"Expected no schedules for {url} but found {g}")

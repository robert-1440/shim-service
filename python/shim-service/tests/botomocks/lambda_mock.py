import json
from threading import Thread
from traceback import print_exc
from typing import Callable, Dict, Any, List, Optional

import app
from bean import beans, InvocableBean
from botomocks import assert_empty, AwsInvalidParameterResponseException
from lambda_pkg import LambdaFunction
from support import thread_utils

LambdaFunctionHandler = Callable[[Dict[str, Any], Any], None]


class Invocation:
    def __init__(self,
                 function_name: str,
                 invocation_type: str,
                 payload: bytes):
        self.function_name = function_name
        self.invocation_type = invocation_type
        self.payload = payload


LambdaCallback = Callable[[Invocation], None]


class _LambdaFunction:
    def __init__(self, name: str, handler: LambdaFunctionHandler):
        self.name = name
        self.handler = handler
        self.invocations: List[Dict[str, Any]] = []
        self.delayed_events: List[Dict[str, Any]] = []
        self.delayed = False

    def invoke(self, event: Dict[str, Any], exception_list: List[Any], context: Any = None):
        try:
            self.handler(event, context)
        except BaseException as ex:
            print_exc()
            exception_list.append(ex)

    def create_threads_for_delayed(self, exception_list: List[Any], context: Any = None) -> List[Thread]:
        if len(self.delayed_events) == 0:
            return []

        def start_thread(event: dict):
            return thread_utils.start_thread(lambda: self.invoke(event, exception_list, context))

        return list(map(start_thread, self.delayed_events))


class MockLambdaClient:
    def __init__(self, allow_all: bool):
        self.functions: Dict[str, _LambdaFunction] = {}
        self.threads: List[Thread] = []
        self.lambda_exceptions = []
        self.allow_all = allow_all
        self.invoke_callback: Optional[LambdaCallback] = None
        self.invocations: List[Invocation] = []

    def set_invoke_callback(self, callback: Optional[LambdaCallback]):
        self.invoke_callback = callback

    def add_function(self, name: str, handler: LambdaFunctionHandler):
        self.functions[name] = _LambdaFunction(name, handler)

    def pop_invocation(self, name: str = None) -> Invocation:
        if name is None:
            return self.invocations.pop(0)
        for invocation in filter(lambda i: i.function_name == name, self.invocations):
            self.invocations.remove(invocation)
            return invocation
        raise ValueError(f"No invocation found for function {name}")

    def clear_invocations(self):
        self.invocations.clear()

    def enable_function(self, name: str, delayed: bool = False):
        lf = LambdaFunction.value_of(name)
        params = lf.value
        invoker = beans.get_invocable_bean(params.default_bean_name)
        assert isinstance(invoker, InvocableBean)
        f = self.functions.get(name)
        if f is None:
            f = self.functions[name] = _LambdaFunction(name, app.handler)
        else:
            f.handler = app.handler
        f.delayed = delayed

    def assert_no_invocations(self, name: str = None):
        if len(self.invocations) == 0:
            return
        if name is None:
            raise AssertionError("Expected no invocations")
        for _ in filter(lambda i: i.function_name == name, self.invocations):
            raise AssertionError(f"Expected no invocations for function {name}")

    def invoke(self, **kwargs):
        params = dict(kwargs)
        function_name = params.pop('FunctionName')
        invocation_type = params.pop('InvocationType')
        payload: bytes = params.pop('Payload')
        assert_empty(params)

        invocation = Invocation(function_name, invocation_type, payload)
        self.invocations.append(invocation)
        if invocation_type != 'Event':
            raise AwsInvalidParameterResponseException("InvokeFunction",
                                                       f"InvocationType {invocation_type} not supported.")

        if self.invoke_callback is not None:
            c = self.invoke_callback
            self.invoke_callback = None
            c(invocation)

        handler = self.functions.get(function_name)
        if handler is not None:
            event = json.loads(payload.decode('utf-8'))
            if handler.delayed:
                handler.delayed_events.append(event)
            else:
                self.threads.append(thread_utils.start_thread(lambda: handler.invoke(event, self.lambda_exceptions)))
        elif not self.allow_all:
            raise AwsInvalidParameterResponseException("InvokeFunction",
                                                       f"Function {function_name} does not exist.")
        return {'StatusCode': 200}

    def get_function(self, **kwargs):
        params = dict(kwargs)
        name = params.pop("FunctionName")
        assert_empty(params)

        arn = f"lambda:arn:{name}"
        return {
            'Configuration':
                {
                    "FunctionName": name,
                    "FunctionArn": arn
                }
        }

    def wait_for_completion(self, name: str = None) -> int:
        if name is not None:
            f = self.functions[name]
            lambda_exceptions = []
            threads = f.create_threads_for_delayed(lambda_exceptions)
        else:
            threads = self.threads
            lambda_exceptions = self.lambda_exceptions

        count = 0
        for t in threads:
            t.join(1000)
            assert not t.is_alive()
            count += 1
        threads.clear()
        if len(lambda_exceptions) > 0:
            ex_list = list(lambda_exceptions)
            lambda_exceptions.clear()
            raise ex_list[0]
        return count


def invoke_by_arn(arn: str, input_string: str):
    values = arn.split(":")
    if len(values) == 3 and values[0] == 'lambda' and values[1] == "arn":
        event = json.loads(input_string)
        app.handler(event, None)
        return
    raise AssertionError(f"Unrecognized arn: {arn}")
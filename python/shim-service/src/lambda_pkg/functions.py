import abc
from typing import Any, Dict

from bean import BeanName
from lambda_pkg.params import LambdaFunctionParameters
from session import SessionKey
from utils.enum_utils import ReverseLookupEnum


class LambdaFunction(ReverseLookupEnum):
    Web = LambdaFunctionParameters("ShimServiceWeb", "SHIM_SERVICE_WEB",
                                   BeanName.SESSION_CONNECTOR)
    LiveAgentPoller = LambdaFunctionParameters(
        "ShimServiceLiveAgentPoller",
        "SHIM_SERVICE_LIVE_AGENT_POLLER",
        BeanName.LIVE_AGENT_PROCESSOR)

    SfdcPubSubPoller = LambdaFunctionParameters(
        "ShimSfdcPubSubPoller",
        "SHIM_SERVICE_SFDC_PUBSUB",
        BeanName.SFDC_PUBSUB_POLLER)

    PushNotifier = LambdaFunctionParameters(
        "ShimServiceNotificationPublisher",
        "SHIM_SERVICE_PUSH_NOTIFIER",
        BeanName.PUSH_NOTIFIER_PROCESSOR
    )

    @classmethod
    def value_of(cls, function_name: str) -> 'LambdaFunction':
        return cls._value_of(function_name, "lambda function")

    @classmethod
    def value_for_enum(cls, v: 'LambdaFunctionParameters') -> Any:
        return v.name


class LambdaInvoker(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def invoke_function(self,
                        function: LambdaFunction,
                        parameters: Dict[str, Any],
                        bean_name: BeanName = None):
        raise NotImplementedError()

    def invoke_connect_session(self, session_key: SessionKey):
        self.invoke_function(LambdaFunction.Web, parameters=session_key.to_key_dict())

    def invoke_live_agent_poller(self):
        self.invoke_function(
            LambdaFunction.LiveAgentPoller,
            parameters={}
        )

    def invoke_notification_poller(self, session_key: SessionKey):
        return self.invoke_function(
            LambdaFunction.PushNotifier,
            parameters=session_key.to_key_dict()
        )

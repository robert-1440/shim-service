import abc
import os
from typing import Dict, Any

from bean import BeanName
from session import SessionKey
from utils.enum_utils import ReverseLookupEnum


class LambdaFunctionParameters:
    def __init__(self, name: str,
                 role_env_name: str,
                 default_bean_name: BeanName,
                 scheduler_group: str):
        self.__name = name
        self.__role_env_name = role_env_name + "_ROLE_ARN"
        self.__default_bean_name = default_bean_name
        self.__scheduler_group = scheduler_group

    @property
    def scheduler_group_name(self) -> str:
        return self.__scheduler_group

    @property
    def default_bean_name(self) -> BeanName:
        return self.__default_bean_name

    @property
    def name(self) -> str:
        return self.__name

    @property
    def scheduler_role_arn(self) -> str:
        return os.environ[self.__role_env_name]


class LambdaFunction(ReverseLookupEnum):
    Web = LambdaFunctionParameters("ShimServiceWeb", "SHIM_SERVICE_WEB",
                                   BeanName.SESSION_CONNECTOR,
                                   "ShimWeb")
    LiveAgentPoller = LambdaFunctionParameters(
        "ShimServiceLiveAgentPoller",
        "SHIM_SERVICE_LIVE_AGENT_POLLER",
        BeanName.LIVE_AGENT_PROCESSOR,
        "ShimLiveAgent"
    )
    SfdcPubSubPoller = LambdaFunctionParameters(
        "ShimSfdcPubSubPoller",
        "SHIM_SERVICE_SFDC_PUBSUB",
        BeanName.SFDC_PUBSUB_POLLER,
        "ShimSfdcPubSub"
    )

    PushNotifier = LambdaFunctionParameters(
        "ShimPushNotifier",
        "SHIM_SERVICE_PUSH_NOTIFIER",
        BeanName.PUSH_NOTIFIER_PROCESSOR,
        "ShimPushNotifier"
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

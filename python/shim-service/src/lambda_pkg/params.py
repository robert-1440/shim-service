import os

from bean import BeanName


class LambdaFunctionParameters:
    def __init__(self, name: str,
                 role_env_name: str,
                 default_bean_name: BeanName):
        self.__name = name
        self.__role_env_name = role_env_name + "_ROLE_ARN"
        self.__default_bean_name = default_bean_name
        self.__queue_url = os.environ.get(f"SQS_{self.__name.upper()}_QUEUE_URL", "")

    @property
    def queue_url(self) -> str:
        if self.__queue_url is None:
            raise AssertionError("No queue url for " + self.__name)
        return self.__queue_url

    @property
    def default_bean_name(self) -> BeanName:
        return self.__default_bean_name

    @property
    def name(self) -> str:
        return self.__name

    @property
    def scheduler_role_arn(self) -> str:
        return os.environ[self.__role_env_name]

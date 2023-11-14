import os

from bean import BeanName


class LambdaFunctionParameters:
    def __init__(self, name: str,
                 default_bean_name: BeanName,
                 scheduler_group_env_name: str = None):
        self.__name = name
        self.__default_bean_name = default_bean_name
        self.__queue_url = os.environ.get(f"SQS_{self.__name.upper()}_QUEUE_URL", "")
        self.__scheduler_group_env_name = scheduler_group_env_name

    @property
    def effective_name(self) -> str:
        """
        This is the name that should be used for the lambda function for the purpose of invoking or scheduling it.
        It checks to see if the current function name is this one, and if so returns the name of the mirror function,
        to avoid the recursive invocation problem where AWS disables it.
        :return: the effective function name.
        """
        name = self.name
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') == name:
            name = os.environ.get('MIRROR_FUNCTION_NAME', name)
        return name

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
        assert self.__scheduler_group_env_name is not None
        return os.environ[f"{self.__scheduler_group_env_name}_ROLE_ARN"]

    @property
    def scheduler_group(self) -> str:
        assert self.__scheduler_group_env_name is not None
        return os.environ.get(self.__scheduler_group_env_name)

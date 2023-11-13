import abc
from typing import Dict, Any


class WebRequestProcessor(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def process(self, event: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()

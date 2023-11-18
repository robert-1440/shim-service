import abc


class Notifier(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def notify(self, subject: str, message: str):
        raise NotImplementedError()

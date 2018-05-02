from abc import ABC, abstractmethod


class CommandOutput(ABC):  # pylint: disable=too-few-public-methods
    @abstractmethod
    def get_default_view(self) -> str:
        raise NotImplementedError()

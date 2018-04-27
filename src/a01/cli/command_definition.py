import inspect
import argparse
import asyncio
from typing import Callable

from . import ArgumentDefinition


class CommandDefinition(object):
    def __init__(self, name: str, func: Callable, desc: str = None):
        self.name = name
        self.func = func
        self.description = desc

        self.argument_definitions = {}
        self._signature = None

    def add_argument(self, definition: ArgumentDefinition) -> None:
        if definition.dest not in self.signature.parameters:
            raise ValueError(f'@arg {definition.dest} is not an argument of {self.func}')
        if definition.dest in self.argument_definitions:
            raise ValueError(f'@arg: repeated definition of {definition.dest} on {self.func}')
        self.argument_definitions[definition.dest] = definition

    def get_argument(self, dest: str) -> ArgumentDefinition:
        return self.argument_definitions.get(dest, ArgumentDefinition(dest))

    @property
    def signature(self) -> inspect.Signature:
        if not self._signature:
            self._signature = inspect.signature(self.func)
        return self._signature

    def execute(self, args: argparse.Namespace):
        kwargs = {parameter: getattr(args, parameter) for parameter in self.signature.parameters}

        if inspect.iscoroutinefunction(self.func):
            return asyncio.get_event_loop().run_until_complete(self.func(**kwargs))

        return self.func(**kwargs)

    def setup(self, parser: argparse.ArgumentParser) -> None:
        parser.description = self.description

        for name, parameter in self.signature.parameters.items():
            argument_definition = self.argument_definitions.get(name, None)
            argument_definition.setup(parser, parameter)

        parser.set_defaults(func=self.execute)

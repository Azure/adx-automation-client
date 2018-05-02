import sys
import inspect
import argparse
import asyncio
from typing import Callable

from a01.output import CommandOutput
from .argument_definition import ArgumentDefinition


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

    def output(self, arg: argparse.Namespace):
        result = self.execute(arg)
        if isinstance(result, CommandOutput):
            sys.stdout.write(result.get_default_view())

    def setup(self, parser: argparse.ArgumentParser) -> None:
        parser.description = self.description

        for name, parameter in self.signature.parameters.items():
            argument_definition = self.argument_definitions.get(name, None)
            argument_definition.setup(parser, parameter)

        parser.set_defaults(func=self.output)


class CommandNode(object):
    def __init__(self, parent: 'CommandNode' = None, name: str = None, parser: argparse.ArgumentParser = None) -> None:
        self.name = name
        self.children = dict()
        self.parer = parser
        self.parent = parent
        self._definition = None

    @property
    def definition(self) -> CommandDefinition:
        return self._definition

    @definition.setter
    def definition(self, value: CommandDefinition) -> None:
        self._definition = value

    def get_child(self, name) -> 'CommandNode':
        if name not in self.children:
            child = CommandNode(self, name)
            self.children[name] = child

        return self.children[name]

    def setup(self, parser: argparse.ArgumentParser) -> None:
        if self.children:
            # this is not a command but a command group
            parser.set_defaults(func=lambda _: parser.print_help())
            subparsers = parser.add_subparsers(title='Commands')
            for name, node in self.children.items():
                node.setup(subparsers.add_parser(name))
            return

        if not self.definition:
            return

        self.definition.setup(parser)

    def __repr__(self) -> str:
        if self.parent:
            return f'{self.parent.__repr__()} -> {self.name}'
        return 'root'

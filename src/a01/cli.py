import argparse
import inspect
from typing import Callable, Collection

from a01.common import get_logger

logger = get_logger(__name__)  # pylint: disable=invalid-name

COMMAND_TABLE = dict()


def cmd(name: str, desc: str = None):
    logger.info(f'register command [{name}]')

    def _decorator(func):
        if hasattr(func, '__command_definition'):
            raise SyntaxError(f'Duplicate @cmd decorator on {func}')

        command_definition = CommandDefinition(name, func, desc)
        COMMAND_TABLE[name] = command_definition

        argument_definitions = getattr(func, '__argument_definitions', None)
        if argument_definitions:
            for each in argument_definitions:
                command_definition.add_argument(each)
            delattr(func, '__argument_definitions')

        setattr(func, '__command_definition', COMMAND_TABLE[name])

        return func

    return _decorator


def arg(dest: str, positional: bool = False, option: Collection[str] = None, **kwargs):
    logger.info(f'register argument [{dest}]')

    def _decorator(func):
        argument_definition = ArgumentDefinition(dest=dest, positional=positional, option=option or (), **kwargs)

        command_definition = getattr(func, '__command_definition', None)
        if command_definition:
            command_definition.add_argument(argument_definition)
        else:
            argument_definitions = getattr(func, '__argument_definitions', [])
            argument_definitions.append(argument_definition)
            setattr(func, '__argument_definitions', argument_definitions)
        return func

    return _decorator


def setup_commands() -> argparse.ArgumentParser:
    logger.info('setting up commands')

    parser = argparse.ArgumentParser(prog='a01')
    parser.set_defaults(func=lambda _: parser.print_help())
    root = CommandNode(parser=parser)

    for name, definition in COMMAND_TABLE.items():
        logger.info(f'add [{name}] to command tree')
        node = root
        for part in name.split(' '):
            node = node.get_child(part)

        node.definition = definition

    root.setup(parser)

    return parser


class ArgumentDefinition(object):  # pylint: disable=too-few-public-methods
    def __init__(self, dest: str, positional: bool = False, option: Collection[str] = None, **kwargs) -> None:
        self.dest = dest
        self.positional = positional
        self.option = option
        self.kwargs = kwargs

    def setup(self, parser: argparse.ArgumentParser, parameter_def: inspect.Parameter) -> None:
        if self.positional and self.option:
            raise ValueError(f'@arg: {self.dest} parameter cannot be both positional and optional.')

        args = []
        kwargs = {}
        if self.positional:
            args.append(self.dest)
        elif not self.option:
            args.append(f'--{self.dest}')
        else:
            args.extend(self.option)
            kwargs['dest'] = self.dest

        if parameter_def.annotation:
            annotation = parameter_def.annotation
            if annotation is bool:
                if parameter_def.default == parameter_def.empty:
                    kwargs['type'] = bool
                else:
                    kwargs['action'] = 'store_false' if parameter_def.default else 'store_true'
            elif type(annotation) == list:  # pylint: disable=unidiomatic-typecheck
                kwargs['nargs'] = '+' if self.positional else '*'
            elif annotation is int:
                kwargs['type'] = int
            else:
                logger.warning(f'@arg: Unknown annotation type {annotation} on {self.dest}')

        if parameter_def.default:
            kwargs['default'] = parameter_def.default

        for key, value in self.kwargs.items():
            kwargs[key] = value

        parser.add_argument(*args, **kwargs)


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
        logger.info(f'execute [{self.name}] -> {self.func}')

        kwargs = {parameter: getattr(args, parameter) for parameter in self.signature.parameters}
        return self.func(**kwargs)

    def setup(self, parser: argparse.ArgumentParser) -> None:
        parser.description = self.description

        for name, parameter in self.signature.parameters.items():
            argument_definition = self.argument_definitions.get(name, None)
            argument_definition.setup(parser, parameter)

        parser.set_defaults(func=self.execute)


class CommandNode(object):
    def __init__(self, parent: 'CommandNode' = None, name: str = None, parser: argparse.ArgumentParser = None) -> None:
        self.name = name
        self.children = dict()
        self.parer = parser
        self.parent = parent
        self._definition = None

        logger.debug(f'init: {self.__repr__()}')

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
        logger.info(f'setup [{self.__repr__()}]')

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

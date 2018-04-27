import argparse
from typing import Collection

from a01.common import get_logger

from a01.cli.argument_definition import ArgumentDefinition
from a01.cli.command_node import CommandNode
from a01.cli.command_definition import CommandDefinition

logger = get_logger(__name__)  # pylint: disable=invalid-name

COMMAND_TABLE = dict()


def cmd(name: str, desc: str = None):
    logger.info(f'register command [{name}]')

    def _decorator(func):
        if hasattr(func, '__command_definition'):
            raise SyntaxError(f'Duplicate @cmd decorator on {func}')

        cmddef = CommandDefinition(name, func, desc)
        COMMAND_TABLE[name] = cmddef

        argument_definitions = getattr(func, '__argument_definitions', None)
        if argument_definitions:
            for each in argument_definitions:
                cmddef.add_argument(each)
            delattr(func, '__argument_definitions')

        setattr(func, '__command_definition', COMMAND_TABLE[name])

        return func

    return _decorator


def arg(dest: str, positional: bool = False, option: Collection[str] = None, **kwargs):
    logger.info(f'register argument [{dest}]')

    def _decorator(func):
        argdef = ArgumentDefinition(dest=dest, positional=positional, option=option or (), **kwargs)

        cmddef = getattr(func, '__command_definition', None)
        if cmddef:
            cmddef.add_argument(argdef)
        else:
            argument_definitions = getattr(func, '__argument_definitions', [])
            argument_definitions.append(argdef)
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

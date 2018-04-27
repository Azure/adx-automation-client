import argparse

from a01.cli.command_definition import CommandDefinition


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

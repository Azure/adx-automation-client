import argparse
import inspect
import logging
from typing import Collection


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
            elif annotation is str:
                kwargs['type'] = str
            else:
                logger = logging.getLogger(__name__)
                logger.warning(f'@arg: Unknown annotation type {annotation} on {self.dest}')

        if parameter_def.default:
            kwargs['default'] = parameter_def.default

        for key, value in self.kwargs.items():
            kwargs[key] = value

        parser.add_argument(*args, **kwargs)

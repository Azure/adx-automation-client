import sys

import colorama
import colorama.ansi
from tabulate import tabulate


def output_in_table(data, headers=(), tablefmt: str = None,
                    background_color: colorama.ansi.AnsiBack = None,
                    foreground_color: colorama.ansi.AnsiFore = None) -> None:
    output = tabulate(data, headers=headers, tablefmt=tablefmt or 'simple')
    if background_color:
        output = f'{background_color}{output}{colorama.Back.RESET}'
    if foreground_color:
        output = f'{foreground_color}{output}{colorama.Fore.RESET}'

    sys.stdout.write(f'\n{output}\n')

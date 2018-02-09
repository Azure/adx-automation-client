import sys

from tabulate import tabulate


def output_in_table(data, headers=(), tablefmt=None):
    table = tabulate(data, headers=headers, tablefmt=tablefmt or 'simple')
    sys.stdout.write(f'\n{table}\n')

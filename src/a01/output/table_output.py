import colorama
import tabulate

from a01.output.command_output import CommandOutput


class TableOutput(CommandOutput):
    def __init__(self, data, headers=None, fmt='Simple'):
        self._data = data
        self._headers = headers or ()
        self._fmt = fmt
        self._background_color = None
        self._foreground_color = None

    @property
    def background_color(self):
        return self._background_color

    @background_color.setter
    def background_color(self, value):
        self._background_color = value

    @property
    def foreground_color(self):
        return self._foreground_color

    @foreground_color.setter
    def foreground_color(self, value):
        self._foreground_color = value

    def get_default_view(self) -> str:

        output = tabulate.tabulate(self._data, headers=self._headers, tablefmt=self._fmt)
        if self.background_color:
            output = f'{self.background_color}{output}{colorama.Back.RESET}'
        if self.foreground_color:
            output = f'{self.foreground_color}{output}{colorama.Fore.RESET}'

        return f'\n{output}\n'

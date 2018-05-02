import json

from a01.output.command_output import CommandOutput


class JsonOutput(CommandOutput):  # pylint: disable=too-few-public-methods
    def __init__(self, data, indent=2):
        self._data = data
        self._indent = indent

    def get_default_view(self):
        return json.dumps(self._data, indent=self._indent) + '\n'

from a01.output.command_output import CommandOutput


class SequentialOutput(CommandOutput):
    def __init__(self, *args):
        """Accept a collection of CommandOutput and concatenate them in sequence."""
        self._outputs = [output for output in args if isinstance(output, CommandOutput)]

    def append(self, output: CommandOutput) -> None:
        if output:
            self._outputs.append(output)

    def get_default_view(self) -> str:
        return '\n'.join([output.get_default_view() for output in self._outputs])

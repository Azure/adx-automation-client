from itertools import zip_longest
from typing import List, Tuple, Generator
from collections import defaultdict

import colorama

from a01.output.table_output import TableOutput
from a01.models import Task


class TaskBriefOutput(TableOutput):
    def __init__(self, task: Task):
        data = zip_longest(
            ('Id', 'Name', 'Status', 'Result', 'Agent', 'Duration(ms)'),
            (task.id, task.name, task.status, task.result, task.result_details.get('agent', None), task.duration))

        super(TaskBriefOutput, self).__init__(data, None, 'plain')


class TaskLogOutput(TableOutput):
    def __init__(self, log_content: List[Tuple[str, str]]):
        super(TaskLogOutput, self).__init__(log_content, None, 'plain')
        self.foreground_color = colorama.Fore.CYAN


class TasksSummary(TableOutput):
    def __init__(self, tasks: List[Task]):
        statuses = defaultdict(lambda: 0)
        results = defaultdict(lambda: 0)
        for task in tasks:
            statuses[task.status] = statuses[task.status] + 1
            results[task.result] = results[task.result] + 1

        status_summary = ' | '.join([f'{status_name}: {count}' for status_name, count in statuses.items()])
        result_summary = f'{colorama.Fore.GREEN}Pass: {results["Passed"]}{colorama.Fore.RESET} | ' \
                         f'{colorama.Fore.RED}Fail: {results["Failed"]}{colorama.Fore.RESET} | ' \
                         f'Error: {results["Error"]}'
        super(TasksSummary, self).__init__(data=[('Task', status_summary), ('Result', result_summary)],
                                           headers=None,
                                           fmt='plain')


class TasksOutput(TableOutput):
    def __init__(self, tasks: List[Task], show_all: bool = False):
        self.tasks = tasks
        super(TasksOutput, self).__init__(self.get_table_view(failed=not show_all), self.get_table_header())

    def get_table_view(self, failed: bool = True) -> Generator[Tuple[str, ...], None, None]:
        for task in self.get_failed_tasks() if failed else self.tasks:
            yield task.get_table_view()

    @staticmethod
    def get_table_header() -> Tuple[str, ...]:
        return Task.get_table_header()

    def get_failed_tasks(self) -> Generator[Task, None, None]:
        for task in self.tasks:
            if task.result == 'Passed' or task.status == 'initialized':
                continue
            yield task

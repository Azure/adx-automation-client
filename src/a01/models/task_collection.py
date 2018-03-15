import json
from collections import defaultdict
from typing import List, Tuple, Generator

import colorama
from requests import HTTPError

from a01.common import get_logger, A01Config
from a01.communication import session
from a01.models import Task


class TaskCollection(object):
    logger = get_logger('TaskCollection')

    def __init__(self, tasks: List[Task], run_id: str) -> None:
        self.tasks = sorted(tasks, key=lambda t: t.identifier)
        self.run_name = run_id

    def get_failed_tasks(self) -> Generator[Task, None, None]:
        for task in self.tasks:
            if task.result == 'Passed' or task.status == 'initialized':
                continue
            yield task

    def post(self) -> None:
        try:
            payload = [t.to_dict() for t in self.tasks]
            session.post(f'{self.endpoint_uri()}/run/{self.run_name}/tasks', json=payload).raise_for_status()
        except HTTPError:
            self.logger.debug('HttpError', exc_info=True)
            raise ValueError('Failed to create tasks in the task store.')

    @classmethod
    def get(cls, run_id: str) -> 'TaskCollection':
        try:
            resp = session.get(f'{cls.endpoint_uri()}/run/{run_id}/tasks')
            resp.raise_for_status()

            tasks = [Task.from_dict(each) for each in resp.json()]
            return TaskCollection(tasks=tasks, run_id=run_id)
        except HTTPError as error:
            cls.logger.debug('HttpError', exc_info=True)
            if error.response.status_code == 404:
                raise ValueError(f'Run {run_id} is not found.')
            raise ValueError('Fail to get runs.')
        except (KeyError, json.JSONDecodeError, TypeError):
            cls.logger.debug('JsonError', exc_info=True)
            raise ValueError('Fail to parse the runs data.')

    @staticmethod
    def endpoint_uri():
        config = A01Config()
        config.ensure_config()
        return config.endpoint_uri

    def get_summary(self) -> Tuple[Tuple[str, str], Tuple[str, str]]:
        statuses = defaultdict(lambda: 0)
        results = defaultdict(lambda: 0)
        for task in self.tasks:
            statuses[task.status] = statuses[task.status] + 1
            results[task.result] = results[task.result] + 1

        status_summary = ' | '.join([f'{status_name}: {count}' for status_name, count in statuses.items()])
        result_summary = f'{colorama.Fore.GREEN}Pass: {results["Passed"]}{colorama.Fore.RESET} | ' \
                         f'{colorama.Fore.RED}Fail: {results["Failed"]}{colorama.Fore.RESET} | ' \
                         f'Error: {results["Error"]}'

        return ('Task', status_summary), ('Result', result_summary)

    def get_table_view(self, failed: bool = True) -> Generator[Tuple[str, ...], None, None]:
        for task in self.get_failed_tasks() if failed else self.tasks:
            yield task.get_table_view()

    @staticmethod
    def get_table_header() -> Tuple[str, ...]:
        return Task.get_table_header()

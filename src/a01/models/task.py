import os.path
import json
from typing import Tuple, Generator

import requests

from a01.common import get_logger, A01Config, LOG_FILE
from a01.communication import session


class Task(object):  # pylint: disable=too-many-instance-attributes
    logger = get_logger('Task')

    def __init__(self, name: str, annotation: str, settings: dict) -> None:
        self.name = name
        self.annotation = annotation
        self.settings = settings

        self.id = None  # pylint: disable=invalid-name
        self.status = None
        self.result_details = {}  # dict
        self.result = None
        self.duration = None  # int
        self.run_id = None

    @classmethod
    def get(cls, task_id: str) -> 'Task':
        try:
            resp = session.get(f'{cls.endpoint_uri()}/task/{task_id}')
            resp.raise_for_status()
            return Task.from_dict(resp.json())
        except requests.HTTPError as error:
            cls.logger.debug('HttpError', exc_info=True)
            if error.response.status_code == 404:
                raise ValueError(f'Task {task_id} is not found.')
            raise ValueError('Fail to get runs.')
        except (KeyError, json.JSONDecodeError, TypeError):
            cls.logger.debug('JsonError', exc_info=True)
            raise ValueError('Fail to parse the runs data.')

    @property
    def log_path(self) -> str:
        return LOG_FILE.format(f'{self.run_id}/task_{self.id}.log')

    def to_dict(self) -> dict:
        result = {
            'name': self.name,
            'annotation': self.annotation,
            'settings': self.settings
        }

        return result

    @staticmethod
    def from_dict(data: dict) -> 'Task':
        result = Task(name=data['name'], annotation=data['annotation'], settings=data['settings'])
        result.id = str(data['id'])
        result.status = data['status']
        result.result_details = data['result_details'] or {}
        result.result = data['result']
        result.duration = data['duration']
        result.run_id = str(data['run_id'])

        return result

    def get_log_content(self) -> Generator[str, None, None]:
        for index, line in enumerate(requests.get(self.log_path).content.decode('utf-7').split('\n')):
            yield '>', f' {index}\t{line}'

    def get_table_view(self) -> Tuple[str, ...]:
        return self.id, self.name, self.status, self.result, self.result_details.get('agent', None), \
               self.result_details.get('duration', None)

    @staticmethod
    def get_table_header() -> Tuple[str, ...]:
        return 'Id', 'Name', 'Status', 'Result', 'Agent', 'Duration(ms)'

    def download_recording(self, az_mode: bool) -> None:
        recording_path = LOG_FILE.format(f'{self.run_id}/recording_{self.id}.yaml')
        resp = requests.get(recording_path)
        if resp.status_code != 200:
            return

        path_paths = self.settings['classifier']['identifier'].split('.')
        if az_mode:
            module_name = path_paths[3]
            method_name = path_paths[-1]
            profile_name = path_paths[-4]
            recording_path = os.path.join('recording', f'azure-cli-{module_name}', 'azure', 'cli', 'command_module',
                                          module_name, 'tests', profile_name, 'recordings', f'{method_name}.yaml')
        else:
            path_paths[-1] = path_paths[-1] + '.yaml'
            path_paths.insert(0, 'recording')
            recording_path = os.path.join(*path_paths)

        os.makedirs(os.path.dirname(recording_path), exist_ok=True)
        with open(recording_path, 'wb') as recording_file:
            recording_file.write(resp.content)

    @staticmethod
    def endpoint_uri():
        config = A01Config()
        config.ensure_config()
        return config.endpoint_uri

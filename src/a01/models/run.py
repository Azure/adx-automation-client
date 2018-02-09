import json
import datetime
from typing import List, Tuple, Generator

import colorama
from requests import HTTPError

from a01.communication import session
from a01.common import get_logger, A01Config


class Run(object):
    logger = get_logger('Run')

    def __init__(self, name: str, settings: dict, details: dict):
        self.name = name
        self.settings = settings
        self.details = details

        self.id = None  # pylint: disable=invalid-name
        self.creation = None

    def to_dict(self) -> dict:
        result = {
            'name': self.name,
            'settings': self.settings,
            'details': self.details
        }

        return result

    def post(self) -> str:
        try:
            resp = session.post(f'{self.endpoint_uri()}/run', json=self.to_dict())
            return resp.json()['id']
        except HTTPError:
            self.logger.debug('HttpError', exc_info=True)
            raise ValueError('Failed to create run in the task store.')
        except (json.JSONDecodeError, TypeError):
            self.logger.debug('JsonError', exc_info=True)
            raise ValueError('Failed to deserialize the response content.')

    @staticmethod
    def from_dict(data: dict) -> 'Run':
        result = Run(name=data['name'], settings=data['settings'], details=data['details'])
        result.id = data['id']
        result.creation = datetime.datetime.strptime(data['creation'], '%Y-%m-%dT%H:%M:%SZ')

        return result

    @staticmethod
    def endpoint_uri():
        config = A01Config()
        config.ensure_config()
        return config.endpoint_uri


class RunCollection(object):
    logger = get_logger('RunCollection')

    def __init__(self, runs: List[Run]) -> None:
        self.runs = runs

    def get_table_view(self) -> Generator[List, None, None]:
        for run in self.runs:
            time = (run.creation - datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M PST')
            remark = run.details.get('remark', '')

            row = [run.id, run.name, time, remark]
            if remark and remark.lower() == 'official':
                for i, column in enumerate(row):
                    row[i] = colorama.Style.BRIGHT + str(column) + colorama.Style.RESET_ALL

            yield row

    @staticmethod
    def get_table_header() -> Tuple:
        return 'Id', 'Name', 'Creation', 'Remark'

    @classmethod
    def get(cls) -> 'RunCollection':
        try:
            resp = session.get(f'{cls.endpoint_uri()}/runs')
            resp.raise_for_status()

            runs = [Run.from_dict(each) for each in resp.json()]
            return RunCollection(runs)
        except HTTPError:
            cls.logger.debug('HttpError', exc_info=True)
            raise ValueError('Fail to get runs.')
        except (KeyError, json.JSONDecodeError, TypeError):
            cls.logger.debug('JsonError', exc_info=True)
            raise ValueError('Fail to parse the runs data.')

    @staticmethod
    def endpoint_uri():
        config = A01Config()
        config.ensure_config()
        return config.endpoint_uri

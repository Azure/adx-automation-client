import json
import datetime
import urllib
from typing import List, Tuple, Generator

import colorama
from requests import HTTPError

from a01.communication import session
from a01.common import get_logger, A01Config


class Run(object):
    logger = get_logger('Run')

    def __init__(self, name: str, settings: dict, details: dict, owner: str,  # pylint: disable=too-many-arguments
                 status: str) -> None:
        self.name = name
        self.settings = settings
        self.details = details
        self.owner = owner
        self.status = status

        self.id = None  # pylint: disable=invalid-name
        self.creation = None

        # prune
        to_delete = [k for k, v in self.settings.items() if not v]
        for k in to_delete:
            del self.settings[k]
        to_delete = [k for k, v in self.details.items() if not v]
        for k in to_delete:
            del self.details[k]

    def to_dict(self) -> dict:
        result = {
            'name': self.name,
            'settings': self.settings,
            'details': self.details,
            'owner': self.owner,
            'status': self.status
        }

        return result

    @classmethod
    def get(cls, run_id: str) -> 'Run':
        try:
            resp = session.get(f'{cls.endpoint_uri()}/run/{run_id}')
            resp.raise_for_status()
            return Run.from_dict(resp.json())
        except HTTPError:
            cls.logger.debug('HttpError', exc_info=True)
            raise ValueError('Failed to find the run in the task store.')
        except (json.JSONDecodeError, TypeError):
            cls.logger.debug('JsonError', exc_info=True)
            raise ValueError('Failed to deserialize the response content.')

    def post(self) -> 'Run':
        try:
            resp = session.post(f'{self.endpoint_uri()}/run', json=self.to_dict())
            return Run.from_dict(resp.json())
        except HTTPError:
            self.logger.debug('HttpError', exc_info=True)
            raise ValueError('Failed to create run in the task store.')
        except (json.JSONDecodeError, TypeError):
            self.logger.debug('JsonError', exc_info=True)
            raise ValueError('Failed to deserialize the response content.')

    @staticmethod
    def from_dict(data: dict) -> 'Run':
        result = Run(name=data['name'],
                     settings=data['settings'],
                     details=data['details'],
                     owner=data.get('owner', None),
                     status=data.get('status', 'N/A'))
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
            remark = run.details.get('remark', None) or run.settings.get('a01.reserved.remark', '')
            owner = run.owner or run.details.get('creator', None) or run.details.get('a01.reserved.creator', '')
            status = run.status

            row = [run.id, run.name, time, status, remark, owner]
            if remark and remark.lower() == 'official':
                for i, column in enumerate(row):
                    row[i] = colorama.Style.BRIGHT + str(column) + colorama.Style.RESET_ALL

            yield row

    @staticmethod
    def get_table_header() -> Tuple:
        return 'Id', 'Name', 'Creation', 'Status', 'Remark', 'Owner'

    @classmethod
    def get(cls, **kwargs) -> 'RunCollection':
        try:
            url = f'{cls.endpoint_uri()}/runs'
            query = {}
            for key, value in kwargs.items():
                if value is not None:
                    query[key] = value

            if query:
                url = f'{url}?{urllib.parse.urlencode(query)}'

            resp = session.get(url)
            resp.raise_for_status()

            runs = [Run.from_dict(each) for each in resp.json()]
            runs = sorted(runs, key=lambda r: r.id, reverse=True)

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

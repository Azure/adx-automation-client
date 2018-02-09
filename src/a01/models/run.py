import json
import datetime

from requests import Session, HTTPError

from a01.communication import session
from a01.common import get_logger


class Run(object):
    def __init__(self, name: str, settings: dict, details: dict):
        self.name = name
        self.settings = settings
        self.details = details

        self.id = None
        self.creation = None

    def to_dict(self) -> dict:
        result = {
            'name': self.name,
            'settings': self.settings,
            'details': self.details
        }

        return result

    def post(self, endpoint: str, context: Session = None) -> str:
        context = context or session
        logger = get_logger('Run.post')

        try:
            resp = context.post(f'{endpoint}/run', json=self.to_dict())
            return resp.json()['id']
        except HTTPError:
            logger.debug('HttpError', exc_info=True)
            raise ValueError('Failed to create run in the task store.')
        except (json.JSONDecodeError, TypeError):
            logger.debug('JsonError', exc_info=True)
            raise ValueError('Failed to deserialize the response content.')

    @staticmethod
    def from_dict(data: dict) -> 'Run':
        result = Run(name=data['name'], settings=data['settings'], details=data['details'])
        result.id = data['id']
        result.creation = datetime.datetime.strptime(data['creation'], '%Y-%m-%dT%H:%M:%SZ')

        return result

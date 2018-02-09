from typing import List

from requests import HTTPError, Session

from a01.common import get_logger
from a01.communication import session


class Task(object):
    def __init__(self, name: str, annotation: str, settings: dict) -> None:
        self.name = name
        self.annotation = annotation,
        self.settings = settings

        self.id = None
        self.status = None
        self.result_details = {}  # dict
        self.result = None
        self.duration = None  # int

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
        result.result_details = data['result_details']
        result.result = data['result']
        result.duration = data['duration']

        return result


class TaskCollection(object):
    def __init__(self, tasks: List[Task], run_id: str) -> None:
        self.tasks = tasks
        self.run_name = run_id

    def post(self, endpoint: str, context: Session = None) -> None:
        context = context or session
        logger = get_logger('TaskCollection.post')
        try:
            payload = [t.to_dict() for t in self.tasks]
            context.post(f'{endpoint}/run/{self.run_name}/tasks', json=payload).raise_for_status()
        except HTTPError:
            logger.debug('HttpError', exc_info=True)
            raise ValueError('Failed to create tasks in the task store.')

from typing import Tuple

from a01.common import get_logger


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

    @property
    def identifier(self) -> str:
        return self.settings['classifier']['identifier']

    @property
    def command(self) -> str:
        return self.settings['execution']['command']

    @property
    def log_resource_uri(self):
        return self.result_details.get('a01.reserved.tasklogpath', None)

    @property
    def record_resource_uri(self):
        return self.result_details.get('a01.reserved.taskrecordpath', None)

    def to_dict(self) -> dict:
        result = {
            'name': self.name,
            'annotation': self.annotation,
            'settings': self.settings,
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

    def get_table_view(self) -> Tuple[str, ...]:
        return self.id, self.name, self.status, self.result, self.result_details.get('agent', None), self.duration

    @staticmethod
    def get_table_header() -> Tuple[str, ...]:
        return 'Id', 'Name', 'Status', 'Result', 'Agent', 'Duration(ms)'

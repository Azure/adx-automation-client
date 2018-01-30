import os
import logging
import functools

import requests
import coloredlogs


KUBE_STORE_NAME = 'task-store-web-service'

LOG_FILE = 'https://azureclia01log.file.core.windows.net/k8slog/{}' \
           '?sv=2017-04-17&ss=f&srt=o&sp=r&se=2019-01-01T00:00:00Z&st=2018-01-04T10:21:21Z&' \
           'spr=https&sig=I9Ajm2i8Knl3hm1rfN%2Ft2E934trzj%2FNnozLYhQ%2Bb7TE%3D'

DROID_CONTAINER_REGISTRY = 'azureclidev'

AUTHORITY_URL = 'https://login.microsoftonline.com/72f988bf-86f1-41af-91ab-2d7cd011db47'
CLIENT_ID = '85a8cba4-45e9-466b-950b-7eeaacfb09b2'
RESOURCE_ID = '00000002-0000-0000-c000-000000000000'

CONFIG_DIR = os.path.expanduser('~/.a01')
TOKEN_FILE = os.path.join(CONFIG_DIR, 'token.json')


coloredlogs.install(level=os.environ.get('A01_DEBUG', 'ERROR'))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@functools.lru_cache(maxsize=4)
def get_store_uri() -> str:
    return os.environ.get('A01_STORE_URI', 'https://a01.troydai.com')


def download_recording(task: dict, az_mode: bool) -> None:
    recording_path = LOG_FILE.format(f'{task["run_id"]}/recording_{task["id"]}.yaml')
    resp = requests.get(recording_path)
    if resp.status_code != 200:
        return

    path_paths = task['settings']['path'].split('.')
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

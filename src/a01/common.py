import os
import logging
import sys
import shlex
import functools
from subprocess import check_output, CalledProcessError

import requests
import coloredlogs


KUBE_STORE_NAME = 'task-store-web-service'

LOG_FILE = 'https://azureclia01log.file.core.windows.net/k8slog/{}' \
           '?sv=2017-04-17&ss=f&srt=o&sp=r&se=2019-01-01T00:00:00Z&st=2018-01-04T10:21:21Z&' \
           'spr=https&sig=I9Ajm2i8Knl3hm1rfN%2Ft2E934trzj%2FNnozLYhQ%2Bb7TE%3D'


coloredlogs.install(level=os.environ.get('A01_DEBUG', 'ERROR'))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@functools.lru_cache(maxsize=4)
def get_store_uri() -> str:
    cmd = f'kubectl get service {KUBE_STORE_NAME} --namespace az' + ' -ojsonpath={.status.loadBalancer.ingress[0].ip}'
    try:
        store_ip = check_output(shlex.split(cmd)).decode('utf-8')
        return f'http://{store_ip}'
    except CalledProcessError:
        logger = get_logger(__name__)
        logger.error('Failed to get the a01 task store service URI. Make sure kubectl is installed and login the '
                     'cluster.')
        sys.exit(1)


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

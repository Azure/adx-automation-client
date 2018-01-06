# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import os
import logging
import sys
import shlex
import functools
from subprocess import check_output, CalledProcessError

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
    cmd = f'kubectl get service {KUBE_STORE_NAME}' + ' -ojsonpath={.status.loadBalancer.ingress[0].ip}'
    try:
        store_ip = check_output(shlex.split(cmd)).decode('utf-8')
        return f'http://{store_ip}'
    except CalledProcessError:
        logger = get_logger(__name__)
        logger.error('Failed to get the a01 task store service URI. Make sure kubectl is installed and login the '
                     'cluster.')
        sys.exit(1)

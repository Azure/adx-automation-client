import sys
import os
import logging
import configparser

import coloredlogs

DROID_CONTAINER_REGISTRY = 'azureclidev'

AUTHORITY_URL = 'https://login.microsoftonline.com/72f988bf-86f1-41af-91ab-2d7cd011db47'
CLIENT_ID = '85a8cba4-45e9-466b-950b-7eeaacfb09b2'
RESOURCE_ID = '00000002-0000-0000-c000-000000000000'

CONFIG_DIR = os.path.expanduser('~/.a01')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'a01.ini')
TOKEN_FILE = os.path.join(CONFIG_DIR, 'token.json')

IS_WINDOWS = sys.platform.lower() in ['windows', 'win32']

coloredlogs.install(level=os.environ.get('A01_DEBUG', 'ERROR'))

NAMESPACE = 'az'

EMAIL_ACCOUNT_SECRET_NAME = 'a01monitor'
EMAIL_SERVICE_FAIL_RESET_LIMIT = 5

COMMON_IMAGE_PULL_SECRET = 'azureclidev-acr'


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class A01Config(configparser.ConfigParser):  # pylint: disable=too-many-ancestors
    def __init__(self, *args, **kwargs):
        super(A01Config, self).__init__(*args, **kwargs)
        self.read(CONFIG_FILE)
        self.logger = get_logger(__class__.__name__)

    def save(self) -> bool:
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as handler:
                self.write(handler)
            return True
        except IOError:
            get_logger(__class__.__name__).error(f'Fail to write config file {CONFIG_FILE}')
            return False

    def ensure_config(self) -> None:
        if not os.path.isfile(CONFIG_FILE) or 'endpoint' not in self:
            self.logger.error(f'Cannot load configuration file: {CONFIG_FILE}. Run a01 login --endpoint <ENDPOINT>.')
            sys.exit(1)

    @property
    def endpoint(self) -> str:
        self.ensure_config()
        return self['endpoint']['host']

    @endpoint.setter
    def endpoint(self, value) -> None:
        if 'endpoint' not in self:
            self['endpoint'] = {}
        self['endpoint']['host'] = value

    @property
    def endpoint_uri(self) -> str:
        return f'https://{self.endpoint}/api'
        # return 'http://127.0.0.1:5000/api'

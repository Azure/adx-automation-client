import sys
import requests

from a01.cli import cmd, arg
from a01.auth import AuthSettings
from a01.common import get_logger, A01Config, CONFIG_FILE


@cmd('login', desc='Log in with Microsoft account.')
@arg('endpoint', help='Host name of the target A01 system.', required=True)
@arg('service_principal', option=['--sp'], help='Login with a service principal.')
@arg('username', option=['--username', '-u'], help='The username of the service principal.')
@arg('password', option=['--password', '-p'], help='The password of the service principal.')
def login(endpoint: str, service_principal: bool = False, username: str = None, password: str = None) -> None:
    logger = get_logger('login')
    try:
        requests.get(f'https://{endpoint}/api/healthy').raise_for_status()
    except (requests.HTTPError, requests.ConnectionError):
        logger.error(f'Cannot reach endpoint https://{endpoint}/api/healthy')
        sys.exit(1)

    auth = AuthSettings()
    if service_principal:
        if not username or not password:
            logger.error('Username or password is missing.')
            sys.exit(1)

        if not auth.login_service_principal(username, password):
            logger.error(f'Fail to login using service principal {username}.')
            sys.exit(1)
    else:
        if not auth.login():
            sys.exit(1)

    config = A01Config()
    config.endpoint = endpoint
    if not config.save():
        logger.error(f'Cannot read or write to file {CONFIG_FILE}')
        sys.exit(1)
    sys.exit(0)

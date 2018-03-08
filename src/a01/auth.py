import os
import json
import sys
from datetime import datetime

import adal
import tabulate
import requests.auth

import a01.cli
from a01.common import get_logger, CONFIG_DIR, CONFIG_FILE, TOKEN_FILE, AUTHORITY_URL, CLIENT_ID, RESOURCE_ID, A01Config


class AuthenticationError(Exception):
    pass


class AuthSettings(object):
    def __init__(self):
        self.logger = get_logger(__class__.__name__)
        self._token_raw = None

        try:
            with open(TOKEN_FILE, 'r') as token_file:
                self._token_raw = json.load(token_file)
        except IOError:
            self.logger.info(f'Token file {TOKEN_FILE} missing.')
        except (json.JSONDecodeError, TypeError):
            self.logger.exception(f'Fail to parse the file {TOKEN_FILE}.')

    def _get_token_value(self, key: str) -> str:
        try:
            return self._token_raw[key]
        except (TypeError, KeyError):
            raise AuthenticationError()

    @property
    def has_login(self) -> bool:
        try:
            return self.access_token is not None
        except AuthenticationError:
            return False

    @property
    def is_service_principal(self) -> bool:
        try:
            return self.user_id is None and self.has_login
        except AuthenticationError:
            return False

    @property
    def is_expired(self) -> bool:
        expire = datetime.strptime(self._get_token_value('expiresOn'), '%Y-%m-%d %H:%M:%S.%f')
        return expire < datetime.now()

    @property
    def user_id(self) -> str:
        return self._get_token_value('userId')

    @property
    def service_principal_id(self) -> str:
        return self._get_token_value('_clientId')

    @property
    def refresh_token(self) -> str:
        return self._get_token_value('refreshToken')

    @property
    def access_token(self) -> str:
        return self._get_token_value('accessToken')

    @property
    def summary(self) -> str:
        if not self._token_raw:
            self.logger.error('Not logged in.')
            raise AuthenticationError()
        return tabulate.tabulate([(k, v) for k, v in self._token_raw.items()
                                  if k not in {'refreshToken', 'accessToken', 'tokenType'}],
                                 tablefmt='plain')

    def login(self) -> bool:
        self.logger.info('Login')
        try:
            context = self._get_auth_context()
            code = context.acquire_user_code(RESOURCE_ID, CLIENT_ID)
            self.logger.debug(f'User code: {json.dumps(code, indent=2)}')
            print(code['message'])

            self._token_raw = context.acquire_token_with_device_code(RESOURCE_ID, code, CLIENT_ID)
            self.logger.debug(f'Acquired token from authority {self._token_raw.get("_authority", "unknown")}.')
            self._save_token()
            print(f'Welcome, {self._get_token_value("givenName")}.')

            return True
        except IOError:
            return False
        except adal.AdalError:
            self.logger.exception('Fail to authenticate.')
            return False

    def login_service_principal(self, username: str, password: str) -> bool:
        self.logger.info('Login as service principal')
        try:
            context = self._get_auth_context()
            self._token_raw = context.acquire_token_with_client_credentials(resource=RESOURCE_ID,
                                                                            client_id=username,
                                                                            client_secret=password)
            self.logger.debug(f'Acquired token from authority {self._token_raw.get("_authority", "unknown")}.')
            self._save_token()
            print('Welcome')
            return True
        except adal.AdalError:
            self.logger.exception('Fail to authenticate.')
            return False

    def logout(self) -> None:
        self.logger.info('Logout')
        if self.has_login:
            self._token_raw = None
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)

    def refresh(self) -> bool:
        try:
            context = self._get_auth_context()
            access_token = context.acquire_token_with_refresh_token(self.refresh_token, CLIENT_ID, RESOURCE_ID)
            for token_key, token_value in access_token.items():
                self._token_raw[token_key] = token_value
            self._save_token()
            return True
        except (AuthenticationError, adal.AdalError):
            self.logger.error(f'Fail to acquire new access token.')
            return False

    def _save_token(self) -> None:
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(TOKEN_FILE, 'w') as token_file:
                token_file.write(json.dumps(self._token_raw, indent=2))
        except IOError:
            self.logger.exception(f'Fail to save the file {TOKEN_FILE}')
            raise

    @staticmethod
    def _get_auth_context() -> adal.AuthenticationContext:
        return adal.AuthenticationContext(AUTHORITY_URL, api_version=None)


class A01Auth(requests.auth.AuthBase):  # pylint: disable=too-few-public-methods
    def __init__(self):
        self.logger = get_logger(__class__.__name__)
        self.auth = AuthSettings()

    def __call__(self, req: requests.Request):
        if not self.auth.has_login:
            self.logger.error('Credential is missing. Please login.')
            sys.exit(1)

        if self.auth.is_expired and not self.auth.refresh():
            self.logger.error('Please login again.')
            sys.exit(1)

        req.headers['Authorization'] = self.auth.access_token
        return req


@a01.cli.cmd('login', desc='Log in with Microsoft account.')
@a01.cli.arg('endpoint', help='Host name of the target A01 system.', required=True)
@a01.cli.arg('service_principal', option=['--sp'], help='Login with a service principal.')
@a01.cli.arg('username', option=['--username', '-u'], help='The username of the service principal.')
@a01.cli.arg('password', option=['--password', '-p'], help='The password of the service principal.')
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


@a01.cli.cmd('logout', desc='Log out - clear the credentials')
def logout() -> None:
    AuthSettings().logout()


@a01.cli.cmd('whoami', desc='Describe the current credential')
def whoami() -> None:
    try:
        print(AuthSettings().summary)
    except AuthenticationError:
        print('You need to login. Usage: a01 login.')


def get_user_id() -> str:
    try:
        return AuthSettings().user_id
    except AuthenticationError:
        print('You need to login. Usage: a01 login.')
        sys.exit(1)

def get_service_principal_id() -> str:
    try:
        return AuthSettings().service_principal_id
    except AuthenticationError:
        print('You need to login. Usage: a01 login.')
        sys.exit(1)

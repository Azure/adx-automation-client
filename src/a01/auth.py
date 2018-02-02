import os
import json
import sys

import adal
import tabulate

import a01.cli
from a01.common import get_logger, CONFIG_DIR, TOKEN_FILE, AUTHORITY_URL, CLIENT_ID, RESOURCE_ID


@a01.cli.cmd('login', desc='Log in with Microsoft account.')
def login() -> None:
    logger = get_logger(__name__)

    context = adal.AuthenticationContext(AUTHORITY_URL, api_version=None)
    code = context.acquire_user_code(RESOURCE_ID, CLIENT_ID)
    logger.debug(f'Acquired user code {json.dumps(code, indent=2)}')
    print(code['message'])

    token = context.acquire_token_with_device_code(RESOURCE_ID, code, CLIENT_ID)
    logger.debug(f'Acquired token with device code {json.dumps(token, indent=2)}')

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(TOKEN_FILE, 'w') as token_file:
        token_file.write(json.dumps(token, indent=2))


@a01.cli.cmd('logout', desc='Log out - clear the credentials')
def logout() -> None:
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


@a01.cli.cmd('whoami', desc='Describe the current credential')
def whoami() -> None:
    if not os.path.exists(TOKEN_FILE):
        print('You need to login. Usage: a01 login.')
        sys.exit(0)

    with open(TOKEN_FILE) as token_file:
        cred = json.load(token_file)

    del cred['refreshToken']
    del cred['accessToken']
    del cred['tokenType']

    cred = [{'Name': k, 'Value': v} for k, v in cred.items()]
    print(tabulate.tabulate(cred))


def get_user_id() -> str:
    if not os.path.exists(TOKEN_FILE):
        print('You need to login. Usage: a01 login.')
        sys.exit(1)

    with open(TOKEN_FILE) as token_file:
        cred = json.load(token_file)

    return cred['userId']

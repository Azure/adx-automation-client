import sys
import json
import datetime

import requests.auth

from a01.common import TOKEN_FILE, AUTHORITY_URL, CLIENT_ID, RESOURCE_ID


class A01Auth(requests.auth.AuthBase):  # pylint: disable=too-few-public-methods
    def __call__(self, req: requests.Request):
        try:
            with open(TOKEN_FILE) as token_file:
                token = json.load(token_file)
            expire = datetime.datetime.strptime(token['expiresOn'], '%Y-%m-%d %H:%M:%S.%f')
            if expire < datetime.datetime.now():
                import adal
                context = adal.AuthenticationContext(AUTHORITY_URL, api_version=None)
                access_token = context.acquire_token_with_refresh_token(token['refreshToken'], CLIENT_ID, RESOURCE_ID)
                for token_key, token_value in access_token.items():
                    token[token_key] = token_value
                with open(TOKEN_FILE, 'w') as token_file:
                    token_file.write(json.dumps(token, indent=2))

        except IOError:
            print('Credential is missing. Please login.')
            sys.exit(1)
        except (TypeError, json.JSONDecodeError):
            print('Fail to parse the token file. Please login.')
            sys.exit(1)

        req.headers['Authorization'] = token['accessToken']

        return req


session = requests.Session()  # pylint: disable=invalid-name
session.auth = A01Auth()

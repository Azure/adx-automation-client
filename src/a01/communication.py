import sys
import json

import requests.auth

from a01.common import TOKEN_FILE


class A01Auth(requests.auth.AuthBase):
    def __call__(self, req: requests.Request):
        try:
            with open(TOKEN_FILE) as token_file:
                token = json.load(token_file)
        except IOError:
            print('Credential is missing. Please login.')
            sys.exit(1)
        except (TypeError, json.JSONDecodeError):
            print('Fail to parse the token file. Please login.')
            sys.exit(1)

        req.headers['Authorization'] = token['accessToken']

        return req


session = requests.Session()
session.auth = A01Auth()

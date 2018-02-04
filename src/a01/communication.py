import requests
from a01.auth import A01Auth


session = requests.Session()  # pylint: disable=invalid-name
session.auth = A01Auth()

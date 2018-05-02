from a01.cli import cmd
from a01.auth import AuthSettings, AuthenticationError


@cmd('whoami', desc='Describe the current credential')
def whoami() -> None:
    try:
        print(AuthSettings().summary)
    except AuthenticationError:
        print('You need to login. Usage: a01 login.')

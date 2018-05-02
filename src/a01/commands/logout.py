from a01.cli import cmd
from a01.auth import AuthSettings


@cmd('logout', desc='Log out - clear the credentials')
def logout() -> None:
    AuthSettings().logout()

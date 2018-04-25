import logging
import sys

from a01.auth import AuthSettings, AuthenticationError
from a01.cli import cmd, arg
from a01.operations import query_runs
from a01.output import output_in_table


@cmd('get runs', desc='Retrieve the runs.')
@arg('owner', help='Query runs by owner.')
@arg('me', help='Query runs created by me.')
@arg('last', help='Returns the last NUMBER of records. Default: 20.')
@arg('skip', help='Returns the records after skipping given number of records at the bottom. Default: 0.')
def get_runs(me: bool = False, last: int = 20, skip: int = 0,
             owner: str = None) -> None:  # pylint: disable=invalid-name
    logger = logging.getLogger(__name__)
    try:
        if me and owner:
            raise ValueError('--me and --user are mutually exclusive.')
        elif me:
            owner = AuthSettings().get_user_name()

        runs = query_runs(owner=owner, last=last, skip=skip)
        output_in_table(runs.get_table_view(), headers=runs.get_table_header())
    except ValueError as err:
        logger.error(err)
        sys.exit(1)
    except AuthenticationError as err:
        logger.error(err)
        print('You need to login. Usage: a01 login.', file=sys.stderr)
        sys.exit(1)

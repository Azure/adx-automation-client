import sys

from a01.common import get_logger
from a01.cli import cmd, arg
from a01.transport import AsyncSession


@cmd('delete run', desc='Delete a run as well as the tasks associate with it.')
@arg('run_id', help='Ids of the run to be deleted.', positional=True)
async def delete_run(run_id: str) -> None:
    async with AsyncSession() as session:
        status, _ = await session.delete_auth(f'run/{run_id}')
        if status > 200:
            get_logger(__name__).error(f'HTTP STATUS {status}')
            sys.exit(1)

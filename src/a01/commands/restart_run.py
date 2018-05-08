import sys

from a01.cli import cmd, arg
from a01.common import get_logger
from a01.transport import AsyncSession


@cmd('restart run', desc='Restart a run. This command is used when the Kubernetes Job behaves abnormally. It will '
                         'create new group of controller job and test job with the same settings.')
@arg('run_id', help='Then run to restart', positional=True)
async def restart_run(run_id: str) -> None:
    async with AsyncSession() as session:
        status, _ = await session.post_auth(f'run/{run_id}/restart')
        if status > 200:
            get_logger(__name__).error(f'HTTP STATUS {status}')
            sys.exit(1)

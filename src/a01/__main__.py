from a01 import __version__
from a01.cli import cmd


@cmd('version', desc='Print version information')
def version() -> None:
    print(__version__)


def main() -> None:
    from a01.cli import setup_commands

    __import__('a01.runs')
    __import__('a01.tasks')
    __import__('a01.images')
    __import__('a01.config')
    __import__('a01.auth')
    __import__('a01.secrets')
    parser = setup_commands()

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()

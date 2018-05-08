import a01
import a01.cli


@a01.cli.cmd('version', desc='Print version information')
def version() -> None:
    print(a01.__version__)


def main() -> None:
    __import__('a01.config')
    __import__('a01.auth')
    __import__('a01.commands')
    parser = a01.cli.setup_commands()

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()

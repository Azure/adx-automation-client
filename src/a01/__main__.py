# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------


def main() -> None:
    from a01.cli import setup_commands

    __import__('a01.runs')
    __import__('a01.tasks')
    parser = setup_commands()

    args = parser.parse_args()
    args.func(args)

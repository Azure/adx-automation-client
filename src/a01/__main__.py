# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------


from a01.cli import setup_commands
from a01.common import get_logger

logger = get_logger(__name__)


def main() -> None:
    __import__('a01.runs')
    __import__('a01.tasks')
    parser = setup_commands()

    args = parser.parse_args()
    args.func(args)

#!/bin/bash

if [ -z $TRAVIS_TAG ]; then
    echo "Skip publishing since it is not a build triggered by a tag." >&2
    exit 0
fi

cd dist
wheel_file=`ls adx_automation_cli-*-py3-none-any.whl`

version=${wheel_file/adx_automation_cli-/}
version=${version/-py3-none-any.whl/}
echo $version

az storage blob upload -c client -f $wheel_file -n archive/$wheel_file --validate-content --no-progress
az storage blob upload -c client -f $wheel_file -n adx_automation_cli_latest.whl --validate-content --no-progress

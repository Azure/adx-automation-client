#!/bin/bash

if [ -z $TRAVIS_TAG ]; then
    echo "Skip publishing since it is not a build triggered by a tag." >&2
    exit 0
fi

if ! command -v az > /dev/null 2>&1; then
    echo "deb [arch=amd64] https://packages.microsoft.com/repos/azure-cli/ `lsb_release -cs` main" | sudo tee /etc/apt/sources.list.d/azure-cli.list
    sudo apt-key adv --keyserver packages.microsoft.com --recv-keys 52E16F86FEE04B979B07E28DB02C46DF417A0893
    sudo apt-get install -y apt-transport-https
    sudo apt-get -qq update && sudo apt-get install -y azure-cli
fi


cd dist
wheel_file=`ls adx_automation_cli-*-py3-none-any.whl`

version=${wheel_file/adx_automation_cli-/}
version=${version/-py3-none-any.whl/}
echo $version

az storage blob upload -c client -f $wheel_file -n archive/$wheel_file --validate-content --no-progress
az storage blob url -c client -n archive/$wheel_file -otsv | tee ./blob_path
az storage blob upload -c client -f ./blob_path -n latest --validate-content --no-progress

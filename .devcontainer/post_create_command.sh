#!/bin/bash

pwd

sudo apt-get update -y
sudo apt-get install -y jq yq

make createPythonEnvironment
. .venv/bin/activate
echo "source .venv/bin/activate" >> ~/.bashrc
echo "source .venv/bin/activate" >> ~/.zshrc

pip install --upgrade pip
pip3 install yq huggingface_hub s5cmd
make installPythonRequirements

make createTypeScriptEnvironment
make installTypeScriptRequirements

git config --unset-all core.hooksPath
pre-commit install

alias deploylisa="make clean && npm ci && make deploy HEADLESS=true"

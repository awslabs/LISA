#!/bin/bash

pwd

sudo apt-get update -y
sudo apt-get install -y jq yq

make createPythonEnvironment
. .venv/bin/activate
echo "source .venv/bin/activate" >> ~/.bashrc
echo "source .venv/bin/activate" >> ~/.zshrc

echo "alias deploylisa='make clean && npm ci && make deploy HEADLESS=true'" >> ~/.bashrc
echo "alias deploylisa='make clean && npm ci && make deploy HEADLESS=true'" >> ~/.zshrc

python -m pip install --upgrade pip
pip3 install yq==3.4.3 huggingface_hub==0.26.3 s5cmd==2.2.2
make installPythonRequirements

make createTypeScriptEnvironment
make installTypeScriptRequirements

git config --unset-all core.hooksPath
pre-commit install

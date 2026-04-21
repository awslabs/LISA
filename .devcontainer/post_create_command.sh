#!/bin/bash

pwd

sudo apt-get update -y
sudo apt-get install -y jq

python3 -m venv .venv
. .venv/bin/activate
echo "source .venv/bin/activate" >> ~/.bashrc
echo "source .venv/bin/activate" >> ~/.zshrc

echo "alias deploylisa='npm run clean && npm ci && HEADLESS=true npm run deploy'" >> ~/.bashrc
echo "alias deploylisa='npm run clean && npm ci && HEADLESS=true npm run deploy'" >> ~/.zshrc

python -m pip install --upgrade pip
pip3 install huggingface_hub s5cmd
npm run install:python

npm install

git config --unset-all core.hooksPath
pre-commit install

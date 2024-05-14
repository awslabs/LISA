#!/usr/bin/env bash
set -e

EXIT_CODE=0

# Check if yq is installed
if ! command -v yq &> /dev/null
then
    echo "yq command not found, is yq installed on your machine?"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null
then
    echo "jq command not found, is jq installed on your machine?"
    exit 1
fi

# Parse through defined envs
for env in $(tail -n +3 config.yaml | yq e '. | keys'); do
    # Skip these keys
    if [[ $env =~ "env" || $env =~ "app_name" || $env == "-" ]]; then
        continue
    fi

    # Verify values are empty in config.yaml
    for key in profile deploymentName; do
        value=$(cat config.yaml | yq .${env}.${key})
        if [ ! -z $value ]; then
            echo "For environment=$env, key=$key must be empty, delete value=$value"
            EXIT_CODE=1
        fi
    done
done

exit $EXIT_CODE

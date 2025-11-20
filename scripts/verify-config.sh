#!/usr/bin/env bash
set -e

EXIT_CODE=0

# Get config file from pre-commit (first argument)
CONFIG_FILE="${1:-config-base.yaml}"

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
for env in $(tail -n +3 "$CONFIG_FILE" | yq -r 'keys[]'); do
    # Skip these keys
    if [[ $env =~ "env" || $env =~ "app_name" || $env == "-" ]]; then
        continue
    fi

    # Verify values are empty in config file
    for key in profile deploymentName; do
        value=$(yq -r ".${env}.${key}" "$CONFIG_FILE")
        if [ ! -z "$value" ] && [ "$value" != "null" ]; then
            echo "For environment=$env, key=$key must be empty, delete value=$value"
            EXIT_CODE=1
        fi
    done
done

exit $EXIT_CODE

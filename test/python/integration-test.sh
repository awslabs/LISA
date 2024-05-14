#!/bin/bash
# Runs the lisa-sdk pytest as an integration test

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rest-url|-r)
      REST_URL="$2"
      shift 2
      ;;
    --verify|-v)
      VERIFY="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --rest-url, -r         URL to the LISA RESTAPI."
      echo "  --verify, -v           Path to cert, the strings 'false' or 'true'."
      echo "  --help, -h             Display this help message."
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

pytest ${SCRIPT_DIR}/../../lisa-sdk/tests/ --url $REST_URL --verify $VERIFY

#!/usr/bin/env bash
set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# keyCloakDir=$(realpath $SCRIPT_DIR/../lib/authentication/keycloak)
# lambdaAuthorizerDir=$(realpath $SCRIPT_DIR/../lib/websocket-interface/functions/authorizer)
outPathCert=$SCRIPT_DIR/server.pem
outPathKey=$SCRIPT_DIR/server.key

if [[ -z $REGION ]]; then
    echo "Error: REGION must be set to generate a valid certification"
    exit 1
fi

domain="*.$REGION.elb.amazonaws.com"

# Check if the certificate and key files already exist
if [ ! -f "$outPathCert" ] || [ ! -f "$outPathKey" ]; then
  openssl req -x509 -newkey rsa:4096 -sha256 -days 365 \
    -nodes -keyout ${outPathKey} -out ${outPathCert} -subj "/CN=${domain}" \
    -addext "subjectAltName=DNS:${domain}" &> /dev/null
  echo "Certificate and key generated for $domain."
else
  echo "Certificate and key files already exist. No new files generated. Copying cached files into build directories."
fi

# cp $outPathCert $outPathKey $keyCloakDir
# cp $outPathCert $lambdaAuthorizerDir

# echo "Certificate and key written to $keyCloakDir"
# echo "Certificate written to $lambdaAuthorizerDir"

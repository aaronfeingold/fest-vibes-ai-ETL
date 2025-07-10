#!/usr/bin/env bash

# ----------------------------------------
# Local Lambda Test Script
# Sends a POST request to the AWS Lambda Runtime Interface Emulator
# running inside your local Docker container
# ----------------------------------------

set -e

DATE=$(date +%F)

curl -s -X POST http://localhost:8080/2015-03-31/functions/function/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "httpMethod": "POST",
    "queryStringParameters": { "date": "'"$DATE"'" },
    "devEnv": false
  }' | jq .

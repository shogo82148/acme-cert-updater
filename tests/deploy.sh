#!/usr/bin/env bash

# deploy a cloudformation tack for test.

set -ux

ROOT=$(cd "$(dirname "$0/")" && pwd)

aws cloudformation --region ap-northeast-1 deploy \
        --stack-name acme-cert-updater-test \
        --template-file "${ROOT}/template.yaml" \
        --capabilities CAPABILITY_IAM

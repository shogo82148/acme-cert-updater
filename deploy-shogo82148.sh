#!/usr/bin/env bash

# deploy the author's AWS Account for testing

set -uex

CURRENT=$(cd "$(dirname "$0")" && pwd)

cd "$CURRENT"
make build

sam package \
    --region ap-northeast-1 \
    --template-file "$CURRENT/.aws-sam/build/template.yaml" \
    --output-template-file "$CURRENT/.aws-sam/build/packaged-test.yaml" \
    --s3-bucket shogo82148-test \
    --s3-prefix acme-cert-updater/resource

sam deploy \
    --template "$CURRENT/.aws-sam/build/packaged-test.yaml" \
    --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_IAM \
    --stack-name acme-cert-updater-deployment-test \
    --parameter-overrides Domains=shogo82148.com Email=shogo82148@gmail.com Environment=staging BucketName=shogo82148-test Prefix=acme-cert-updater/cert HostedZone=Z1TR8BQNS8S1I7 LogLevel=DEBUG

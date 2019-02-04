#!/usr/bin/env bash

if [[ $# -lt 3 ]]; then
    echo "Usage: $(basename "$0") BUCKET_NAME OBJECT_KEY_NAME OUTPUT_DIRECTORY COMMAND"
    exit 2
fi

BUCKET=$1
OBJECT=$2
OUTPUT=$3

set -eu
JSON=$(aws s3 cp "s3://$BUCKET/$OBJECT" -)
if [[ -f "$OUTPUT/timestamp.txt" ]] && [[ ! $(echo "$JSON" | jq -r .timestamp) > $(cat "$OUTPUT/timestamp.txt") ]]; then
    exit 0
fi

aws s3 cp --only-show-errors "s3://$BUCKET/$(echo "$JSON" | jq -r .cert.cert)" "$OUTPUT"
aws s3 cp --only-show-errors "s3://$BUCKET/$(echo "$JSON" | jq -r .cert.chain)" "$OUTPUT"
aws s3 cp --only-show-errors "s3://$BUCKET/$(echo "$JSON" | jq -r .cert.fullchain)" "$OUTPUT"
aws s3 cp --only-show-errors "s3://$BUCKET/$(echo "$JSON" | jq -r .cert.privkey)" "$OUTPUT"
echo "$JSON" | jq -r .timestamp > "$OUTPUT/timestamp.txt"

shift 3
if [ $# -eq 0 ]; then
    exit 0
fi

exec "$@"

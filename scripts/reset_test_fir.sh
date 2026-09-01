#!/usr/bin/env bash

set -euo pipefail

CASE_ID="${1:-}"
DOCUMENT_ID="${2:-}"

if [[ -z "$CASE_ID" || -z "$DOCUMENT_ID" ]]; then
    echo "Usage:"
    echo "  ./scripts/reset_test_fir.sh <case_id> <document_id>"
    exit 1
fi

echo "Using AWS identity:"
aws sts get-caller-identity

echo
echo "Deleting MongoDB records..."

docker exec fir-mongodb mongosh \
    -u admin \
    -p change-me \
    --authenticationDatabase admin \
    --quiet \
    --eval "
        use criminal_intelligence;

        db.ingestion_jobs.deleteMany({
            document_id: '$DOCUMENT_ID'
        });

        db.documents.deleteOne({
            document_id: '$DOCUMENT_ID'
        });

        db.cases.deleteOne({
            case_id: '$CASE_ID'
        });
    "

echo
echo "Deleting S3 objects..."

aws s3 rm \
    "s3://fir-intelligence-documents/cases/$CASE_ID/" \
    --recursive \
    --region ap-south-1

echo
echo "✓ Test FIR deleted"
echo "  Case:     $CASE_ID"
echo "  Document: $DOCUMENT_ID"
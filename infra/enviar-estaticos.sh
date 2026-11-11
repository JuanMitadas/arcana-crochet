#!/usr/bin/env bash
# Upload the collected static files (staticfiles/) to the store bucket, under static/,
# where CloudFront serves /static/* from. Used by .github/workflows/deploy.yml.
#
#   python manage.py collectstatic --noinput   # with DEBUG=0, so names carry a hash
#   bash infra/enviar-estaticos.sh <bucket>
#
# Old files are kept (no --delete): pages cached before a deploy still point to them.
set -euo pipefail

bucket="${1:?usage: $0 <bucket>}"

# Hashed names (app.3f9a1c.css) never change content: cache for a year.
aws s3 sync staticfiles/ "s3://$bucket/static/" \
  --exclude "*.gz" --exclude "*.br" --exclude "staticfiles.json" \
  --cache-control "public, max-age=31536000, immutable" \
  --only-show-errors
echo "Static files uploaded to s3://$bucket/static/"

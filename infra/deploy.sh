#!/usr/bin/env bash
# Build and deploy UrbanWise to AWS (CloudFormation + S3 + CloudFront).
#
#   infra/deploy.sh                 deploy everything
#   ALARM_EMAIL=you@x.com infra/deploy.sh   also email alarms
#
# Needs: AWS CLI logged in, Python 3.12 venv in backend/venv, Node 20+.
set -euo pipefail

cd "$(dirname "$0")/.."
STACK=${STACK:-urbanwise}
REGION=${AWS_REGION:-ap-south-1}
PARAM=/urbanwise/gemini-api-key
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ARTIFACTS="urbanwise-artifacts-$ACCOUNT-$REGION"
BUILD=infra/build

echo "Deploying stack '$STACK' to $REGION (account $ACCOUNT)"

# 1. Bucket for the backend zip
if ! aws s3api head-bucket --bucket "$ARTIFACTS" 2>/dev/null; then
  aws s3api create-bucket --bucket "$ARTIFACTS" --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  aws s3api put-public-access-block --bucket "$ARTIFACTS" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
fi

# 2. Gemini key into SSM Parameter Store (once), straight from backend/.env.
#    Written via a private temp file so it never appears on screen or in `ps`.
if ! aws ssm get-parameter --name "$PARAM" --region "$REGION" >/dev/null 2>&1; then
  KEYFILE=$(mktemp); chmod 600 "$KEYFILE"
  grep -E '^GEMINI_API_KEY=' backend/.env | head -1 | cut -d= -f2- | tr -d '\n' > "$KEYFILE" || true
  if [ ! -s "$KEYFILE" ]; then rm -f "$KEYFILE"; echo "Put GEMINI_API_KEY in backend/.env first"; exit 1; fi
  aws ssm put-parameter --name "$PARAM" --type SecureString --value "file://$KEYFILE" --region "$REGION" >/dev/null
  rm -f "$KEYFILE"
  echo "Stored the Gemini key in SSM ($PARAM)"
fi

# 3. Secret header shared by CloudFront and the API (kept locally, git-ignored)
if [ ! -s infra/.origin-secret ]; then
  (umask 077; openssl rand -hex 32 > infra/.origin-secret)
fi

# 4. Backend zip: our code + Linux arm64 wheels for Python 3.12 (no test tools)
rm -rf "$BUILD"; mkdir -p "$BUILD/pkg"
grep -v '^pytest' backend/requirements.txt > "$BUILD/requirements.txt"
backend/venv/bin/pip install --quiet --target "$BUILD/pkg" -r "$BUILD/requirements.txt" \
  --platform manylinux2014_aarch64 --implementation cp --python-version 3.12 --only-binary=:all:
cp -R backend/app.py backend/pipeline.py backend/run.sh backend/services backend/data "$BUILD/pkg/"
find "$BUILD/pkg" -name __pycache__ -type d -prune -exec rm -rf {} +
CODE_KEY="backend-$(date -u +%Y%m%d%H%M%S).zip"
(cd "$BUILD/pkg" && zip -qr9 "../$CODE_KEY" .)
aws s3 cp --quiet "$BUILD/$CODE_KEY" "s3://$ARTIFACTS/$CODE_KEY"
echo "Uploaded backend ($(du -h "$BUILD/$CODE_KEY" | cut -f1))"

# 5. Infrastructure
aws cloudformation deploy --region "$REGION" --stack-name "$STACK" \
  --template-file infra/template.yaml --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset \
  --parameter-overrides CodeBucket="$ARTIFACTS" CodeKey="$CODE_KEY" \
    OriginSecret="$(cat infra/.origin-secret)" GeminiKeyParam="$PARAM" \
    TrustedProxies="${TRUSTED_PROXIES:-0}" AlarmEmail="${ALARM_EMAIL:-}"

output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

# 6. Frontend
(cd frontend && npm ci --silent && npm run build --silent)
SITE_BUCKET=$(output SiteBucketName)
# Hashed files in assets/ can be cached for a year, other files for an hour,
# and index.html must always be re-checked so new deploys show up.
aws s3 sync --quiet frontend/dist "s3://$SITE_BUCKET" --delete \
  --exclude "assets/*" --exclude index.html --cache-control "public,max-age=3600"
aws s3 sync --quiet frontend/dist/assets "s3://$SITE_BUCKET/assets" --delete \
  --cache-control "public,max-age=31536000,immutable"
aws s3 cp --quiet frontend/dist/index.html "s3://$SITE_BUCKET/index.html" --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id "$(output DistributionId)" --paths "/*" >/dev/null

echo "Done: $(output SiteUrl)"

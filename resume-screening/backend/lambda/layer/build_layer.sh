#!/bin/bash
# build_layer.sh — Rebuilds the Lambda layer from scratch
#
# Run this after cloning the repo or when dependencies change.
# Requires: pip, aws CLI, jq (optional)
#
# Usage:
#   cd backend/lambda/layer
#   ./build_layer.sh            # build + publish to AWS
#   ./build_layer.sh --local    # build zip only, skip AWS deploy

set -euo pipefail

LAYER_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_DIR="$LAYER_DIR/python"
ZIP_FILE="$LAYER_DIR/layer.zip"
LAYER_NAME="resume-screening-layer"
REGION="${AWS_REGION:-us-east-1}"
PYTHON_VERSION="3.14"

echo "=== Building Lambda Layer ==="
echo "Layer dir: $LAYER_DIR"

# Step 1: Install third-party packages for Linux Python 3.14
echo ""
echo "--- Installing packages for Linux x86_64 Python 3.14 ---"

# MCP SDK + dependencies (pure Python, no native extensions)
pip install \
    mcp \
    httpx \
    httpx-sse \
    anyio \
    starlette \
    uvicorn \
    sse-starlette \
    pydantic-settings \
    python-dotenv \
    python-multipart \
    pyjwt \
    cryptography \
    click \
    -t "$PYTHON_DIR" -q

# pydantic-core needs Linux-specific binary
echo "--- Installing Linux-compatible pydantic-core ---"
pip install pydantic pydantic-core pydantic-settings \
    --platform manylinux2014_x86_64 \
    --python-version 314 \
    --only-binary=:all: \
    --no-deps \
    -t "$PYTHON_DIR" -q

echo "--- Installed packages ---"
ls "$PYTHON_DIR" | grep -v "^app$" | grep -v "\.py$"

# Step 2: Build zip (include .dist-info for importlib.metadata)
echo ""
echo "--- Building layer.zip ---"
cd "$LAYER_DIR"
rm -f layer.zip
zip -r layer.zip python/ \
    -x "*.pyc" \
    -x "*/__pycache__/*" \
    -q
echo "Size: $(du -sh layer.zip | cut -f1)"

if [[ "${1:-}" == "--local" ]]; then
    echo ""
    echo "=== Done (local only) ==="
    echo "layer.zip is ready at: $ZIP_FILE"
    exit 0
fi

# Step 3: Publish to AWS Lambda
echo ""
echo "--- Publishing layer to AWS ($REGION) ---"
LAYER_ARN=$(aws lambda publish-layer-version \
    --layer-name "$LAYER_NAME" \
    --zip-file "fileb://$ZIP_FILE" \
    --compatible-runtimes python3.11 python3.12 \
    --region "$REGION" \
    --query 'LayerVersionArn' \
    --output text)

echo "Published: $LAYER_ARN"

# Step 4: Update resume-processor function
echo ""
echo "--- Updating resume-processor Lambda ---"
aws lambda update-function-configuration \
    --function-name resume-processor \
    --layers "$LAYER_ARN" \
    --region "$REGION" \
    --query 'Layers[0].Arn' \
    --output text

echo ""
echo "=== Layer deployed successfully ==="
echo "ARN: $LAYER_ARN"

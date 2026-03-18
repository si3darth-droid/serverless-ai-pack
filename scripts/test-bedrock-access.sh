#!/bin/bash
set -e

echo "🔍 Testing Amazon Bedrock Access..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

REGION=${AWS_REGION:-us-east-1}

echo -e "${BLUE}Testing in region: $REGION${NC}"
echo ""

# Test Bedrock access
echo "1. Checking Bedrock model access..."
MODELS=$(aws bedrock list-foundation-models --region $REGION 2>&1)

if echo "$MODELS" | grep -q "claude"; then
    echo -e "${GREEN}✓ Bedrock access confirmed${NC}"
    echo ""
    echo "Available Claude models:"
    echo "$MODELS" | jq -r '.modelSummaries[] | select(.modelId | contains("claude")) | .modelId' 2>/dev/null || echo "Unable to parse models"
else
    echo -e "${RED}✗ Bedrock access issue${NC}"
    echo "Error: $MODELS"
    echo ""
    echo "To enable Bedrock:"
    echo "1. Go to AWS Console > Amazon Bedrock"
    echo "2. Navigate to 'Model access' in the left sidebar"
    echo "3. Click 'Manage model access'"
    echo "4. Enable Claude models"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Bedrock access test completed!${NC}"

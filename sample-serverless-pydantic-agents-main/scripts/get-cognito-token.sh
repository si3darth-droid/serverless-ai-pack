#!/bin/bash

# Script to get Cognito authentication token
# Usage: ./scripts/get-cognito-token.sh <USER_POOL_ID> <CLIENT_ID> <USERNAME> <PASSWORD>

set -e

USER_POOL_ID=$1
CLIENT_ID=$2
USERNAME=${3:-testuser}
PASSWORD=${4:-TestPass123!}

if [ -z "$USER_POOL_ID" ] || [ -z "$CLIENT_ID" ]; then
    echo "Usage: $0 <USER_POOL_ID> <CLIENT_ID> [USERNAME] [PASSWORD]"
    echo ""
    echo "Get USER_POOL_ID and CLIENT_ID from CDK outputs:"
    echo "  aws cloudformation describe-stacks --stack-name PydanticAgentStack --query 'Stacks[0].Outputs'"
    exit 1
fi

echo "Authenticating user: $USERNAME"

# Get authentication token
TOKEN=$(aws cognito-idp initiate-auth \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id "$CLIENT_ID" \
    --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
    --query 'AuthenticationResult.IdToken' \
    --output text)

if [ -z "$TOKEN" ]; then
    echo "❌ Failed to get token"
    exit 1
fi

echo "✅ Token obtained successfully!"
echo ""
echo "Token (first 50 chars): ${TOKEN:0:50}..."
echo ""
echo "Export token to environment:"
echo "  export AUTH_TOKEN='$TOKEN'"
echo ""
echo "Use in API calls:"
echo "  curl -H \"Authorization: Bearer \$AUTH_TOKEN\" ..."
echo ""
echo "Full token:"
echo "$TOKEN"

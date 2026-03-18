#!/bin/bash

# Script to create a test user in Cognito and get authentication token
# Usage: ./scripts/setup-cognito-user.sh <USER_POOL_ID> <CLIENT_ID> <USERNAME> <PASSWORD>

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

echo "Creating Cognito user: $USERNAME"

# Create user
aws cognito-idp admin-create-user \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --user-attributes Name=email,Value="${USERNAME}@example.com" \
    --temporary-password "TempPass123!" \
    --message-action SUPPRESS \
    2>/dev/null || echo "User may already exist"

# Set permanent password
echo "Setting permanent password..."
aws cognito-idp admin-set-user-password \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --password "$PASSWORD" \
    --permanent

echo "✅ User created successfully!"
echo ""
echo "To get authentication token, run:"
echo "  ./scripts/get-cognito-token.sh $USER_POOL_ID $CLIENT_ID $USERNAME $PASSWORD"

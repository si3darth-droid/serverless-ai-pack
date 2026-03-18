#!/bin/bash

# ============================================================================
# SECURITY NOTICE: Test Credentials Only
# ============================================================================
# This script uses TEST CREDENTIALS for demonstration purposes only.
# The password "TestPass123!" is a sample Cognito test user password.
# This is NOT a production secret and is only used for testing the API.
# ============================================================================

set -e

echo "☁️  Testing AWS Deployment..."
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get stack outputs
echo -e "${BLUE}1. Getting Stack Outputs${NC}"
OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name PydanticAgentStack \
    --query 'Stacks[0].Outputs' \
    --output json)

API_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue')
STATE_MACHINE_ARN=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="StateMachineArn") | .OutputValue')
USER_POOL_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolId") | .OutputValue')
CLIENT_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolClientId") | .OutputValue')

echo "API Endpoint: $API_ENDPOINT"
echo "State Machine: $STATE_MACHINE_ARN"
echo "User Pool ID: $USER_POOL_ID"
echo ""

# Get authentication token
echo -e "${BLUE}2. Getting Authentication Token${NC}"
# Test credentials should be set as environment variables
# See README.md for setup instructions
USERNAME="${TEST_USERNAME:-testuser}"
TEST_PASSWORD="${TEST_PASSWORD:-TestPass123!}"

if [ -z "$TEST_PASSWORD" ] || [ "$TEST_PASSWORD" = "TestPass123!" ]; then
    echo -e "${RED}ERROR: Please set TEST_USERNAME and TEST_PASSWORD environment variables${NC}"
    echo "See README.md for instructions"
    exit 1
fi

# Ensure test user exists
aws cognito-idp admin-create-user \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --user-attributes Name=email,Value="${USERNAME}@example.com" \
    --temporary-password "TempPass123!" \
    --message-action SUPPRESS \
    2>/dev/null || echo "  User already exists"

aws cognito-idp admin-set-user-password \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --password "$PASSWORD" \
    --permanent \
    2>/dev/null

# Get JWT token
TOKEN=$(aws cognito-idp initiate-auth \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id "$CLIENT_ID" \
    --auth-parameters USERNAME="$USERNAME",PASSWORD="$TEST_PASSWORD" \
    --query 'AuthenticationResult.IdToken' \
    --output text)

if [ -z "$TOKEN" ] || [ "$TOKEN" == "None" ]; then
    echo -e "${RED}✗ Failed to get authentication token${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Authentication token obtained${NC}"
echo ""

# Test API Gateway endpoint with authentication
echo -e "${BLUE}3. Testing API Gateway Endpoint (with auth)${NC}"
RESPONSE=$(curl -s -X POST "${API_ENDPOINT}query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "question": "What are the benefits of serverless architecture?",
        "context": {}
    }')

echo "Response: $RESPONSE"
echo ""

if echo "$RESPONSE" | jq -e '.answer' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API test passed${NC}"
else
    echo -e "${YELLOW}⚠ API test failed or returned unexpected format${NC}"
    echo "  This may indicate authentication issues or API errors"
fi
echo ""

# Test Step Functions
echo -e "${BLUE}4. Testing Step Functions Orchestration${NC}"
EXECUTION_ARN=$(aws stepfunctions start-execution \
    --state-machine-arn "$STATE_MACHINE_ARN" \
    --input file://tests/events/test-orchestration-event.json \
    --query 'executionArn' \
    --output text)

echo "Execution ARN: $EXECUTION_ARN"
echo "Waiting for execution to complete..."
sleep 10

EXECUTION_STATUS=$(aws stepfunctions describe-execution \
    --execution-arn "$EXECUTION_ARN" \
    --query 'status' \
    --output text)

echo "Execution Status: $EXECUTION_STATUS"

if [ "$EXECUTION_STATUS" == "SUCCEEDED" ]; then
    echo -e "${GREEN}✓ Step Functions test passed${NC}"
else
    echo -e "${YELLOW}⚠ Step Functions execution status: $EXECUTION_STATUS${NC}"
fi
echo ""

# Check CloudWatch Logs
echo -e "${BLUE}5. Checking Recent CloudWatch Logs${NC}"
# Dynamically discover the Agent Lambda log group name
LOG_GROUP=$(aws logs describe-log-groups \
    --log-group-name-prefix "/aws/lambda/PydanticAgentStack-AgentFunction" \
    --query 'logGroups[0].logGroupName' \
    --output text 2>/dev/null)

if [ -n "$LOG_GROUP" ] && [ "$LOG_GROUP" != "None" ]; then
    echo "Log Group: $LOG_GROUP"
    aws logs tail "$LOG_GROUP" --since 5m --format short 2>/dev/null | tail -20 || echo "No recent logs found"
else
    echo "No Agent Lambda log group found"
fi
echo ""

echo -e "${GREEN}✅ AWS tests completed!${NC}"

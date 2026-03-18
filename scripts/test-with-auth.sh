#!/bin/bash

# ============================================================================
# SECURITY NOTICE: Test Credentials Only
# ============================================================================
# This script uses TEST CREDENTIALS for demonstration purposes only.
# The password "TestPass123!" is a sample Cognito test user password.
# This is NOT a production secret and is only used for testing the API.
# ============================================================================

# Integration test script with Cognito authentication
# Usage: ./scripts/test-with-auth.sh

set -e

echo "========================================="
echo "Integration Test with Cognito Auth"
echo "========================================="
echo ""

# Get stack outputs
echo "📋 Getting stack outputs..."
OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name PydanticAgentStack \
    --query 'Stacks[0].Outputs' \
    --output json)

API_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue')
QUERY_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="QueryEndpoint") | .OutputValue')
WORKFLOW_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="WorkflowEndpoint") | .OutputValue')
USER_POOL_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolId") | .OutputValue')
CLIENT_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolClientId") | .OutputValue')

echo "  API Endpoint: $API_ENDPOINT"
echo "  User Pool ID: $USER_POOL_ID"
echo "  Client ID: $CLIENT_ID"
echo ""

# Create test user if doesn't exist
echo "👤 Setting up test user..."
# Test credentials should be set as environment variables
# See README.md for setup instructions
USERNAME="${TEST_USERNAME:-testuser}"
TEST_PASSWORD="${TEST_PASSWORD:-TestPass123!}"

if [ -z "$TEST_PASSWORD" ] || [ "$TEST_PASSWORD" = "TestPass123!" ]; then
    echo "ERROR: Please set TEST_USERNAME and TEST_PASSWORD environment variables"
    echo "See README.md for instructions"
    exit 1
fi

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

echo "  ✅ User ready: $USERNAME"
echo ""

# Get authentication token
echo "🔐 Getting authentication token..."
TOKEN=$(aws cognito-idp initiate-auth \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id "$CLIENT_ID" \
    --auth-parameters USERNAME="$USERNAME",PASSWORD="$TEST_PASSWORD" \
    --query 'AuthenticationResult.IdToken' \
    --output text)

if [ -z "$TOKEN" ]; then
    echo "  ❌ Failed to get token"
    exit 1
fi

echo "  ✅ Token obtained (${#TOKEN} chars)"
echo ""

# Test 1: Query endpoint without auth (should fail)
echo "Test 1: Query endpoint WITHOUT auth (should fail with 401)"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$QUERY_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"question": "What is serverless?", "context": {}}')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "401" ]; then
    echo "  ✅ Correctly rejected (401 Unauthorized)"
else
    echo "  ❌ Expected 401, got $HTTP_CODE"
    echo "  Response: $BODY"
fi
echo ""

# Test 2: Query endpoint with auth (should succeed)
echo "Test 2: Query endpoint WITH auth (should succeed)"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$QUERY_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"question": "What is serverless architecture?", "context": {}}')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ Request successful (200 OK)"
    echo "  Response preview: $(echo "$BODY" | jq -r '.answer' 2>/dev/null | head -c 100)..."
else
    echo "  ❌ Expected 200, got $HTTP_CODE"
    echo "  Response: $BODY"
fi
echo ""

# Test 3: Workflow endpoint without auth (should fail)
echo "Test 3: Workflow endpoint WITHOUT auth (should fail with 401)"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$WORKFLOW_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"tasks": [{"task_type": "research", "data": {"topic": "AI"}}], "user_id": "test-user"}')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "401" ]; then
    echo "  ✅ Correctly rejected (401 Unauthorized)"
else
    echo "  ❌ Expected 401, got $HTTP_CODE"
    echo "  Response: $BODY"
fi
echo ""

# Test 4: Workflow endpoint with auth (should succeed)
echo "Test 4: Workflow endpoint WITH auth (should succeed)"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$WORKFLOW_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"tasks": [{"task_type": "research", "data": {"topic": "Machine Learning"}}], "user_id": "test-user"}')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ Request successful (200 OK)"
    EXECUTION_ARN=$(echo "$BODY" | jq -r '.executionArn' 2>/dev/null)
    echo "  Execution ARN: $EXECUTION_ARN"
else
    echo "  ❌ Expected 200, got $HTTP_CODE"
    echo "  Response: $BODY"
fi
echo ""

echo "========================================="
echo "✅ All authentication tests completed!"
echo "========================================="

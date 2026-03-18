#!/bin/bash

# Customer Service Use Case Test Script
# Tests the Pydantic AI agent with customer service scenarios

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Customer Service Agent Test Suite${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if API endpoint is set
if [ -z "$API_ENDPOINT" ]; then
    echo -e "${YELLOW}Getting API endpoint from CloudFormation...${NC}"
    API_ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name PydanticAgentStack \
        --query 'Stacks[0].Outputs[?OutputKey==`QueryEndpoint`].OutputValue' \
        --output text)
    echo -e "${GREEN}API Endpoint: $API_ENDPOINT${NC}\n"
fi

# Check if TOKEN is set
if [ -z "$TOKEN" ]; then
    echo -e "${YELLOW}Getting authentication token...${NC}"
    CLIENT_ID=$(aws cloudformation describe-stacks \
        --stack-name PydanticAgentStack \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
        --output text)
    
    TOKEN=$(aws cognito-idp initiate-auth \
        --auth-flow USER_PASSWORD_AUTH \
        --client-id $CLIENT_ID \
        --auth-parameters USERNAME=testuser,PASSWORD=TestPass123! \
        --query 'AuthenticationResult.IdToken' \
        --output text)
    echo -e "${GREEN}Token obtained successfully${NC}\n"
fi

# Test 1: Order Status Inquiry (Order Exists)
echo -e "${BLUE}Test 1: Order Status Inquiry (ORD-001)${NC}"
echo -e "${YELLOW}Question: What is the status of my order ORD-001?${NC}"
RESPONSE=$(curl -s -X POST $API_ENDPOINT \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "What is the status of my order ORD-001?", "context": {"user_id": "customer-123"}}')

echo -e "${GREEN}Response:${NC}"
echo $RESPONSE | python3 -m json.tool 2>/dev/null || echo $RESPONSE
echo ""

# Test 2: Order Not Found
echo -e "${BLUE}Test 2: Order Not Found (ORD-999)${NC}"
echo -e "${YELLOW}Question: Where is my order ORD-999?${NC}"
RESPONSE=$(curl -s -X POST $API_ENDPOINT \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "Where is my order ORD-999?", "context": {"user_id": "customer-456"}}')

echo -e "${GREEN}Response:${NC}"
echo $RESPONSE | python3 -m json.tool 2>/dev/null || echo $RESPONSE
echo ""

# Test 3: General Customer Service Question
echo -e "${BLUE}Test 3: General Question (Return Policy)${NC}"
echo -e "${YELLOW}Question: What is your return policy?${NC}"
RESPONSE=$(curl -s -X POST $API_ENDPOINT \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "What is your return policy?", "context": {}}')

echo -e "${GREEN}Response:${NC}"
echo $RESPONSE | python3 -m json.tool 2>/dev/null || echo $RESPONSE
echo ""

# Test 4: Delivered Order
echo -e "${BLUE}Test 4: Delivered Order Status (ORD-003)${NC}"
echo -e "${YELLOW}Question: Has my order ORD-003 been delivered?${NC}"
RESPONSE=$(curl -s -X POST $API_ENDPOINT \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "Has my order ORD-003 been delivered?", "context": {"user_id": "customer-789"}}')

echo -e "${GREEN}Response:${NC}"
echo $RESPONSE | python3 -m json.tool 2>/dev/null || echo $RESPONSE
echo ""

# Test 5: Processing Order
echo -e "${BLUE}Test 5: Processing Order (ORD-002)${NC}"
echo -e "${YELLOW}Question: When will my order ORD-002 ship?${NC}"
RESPONSE=$(curl -s -X POST $API_ENDPOINT \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "When will my order ORD-002 ship?", "context": {"user_id": "customer-456"}}')

echo -e "${GREEN}Response:${NC}"
echo $RESPONSE | python3 -m json.tool 2>/dev/null || echo $RESPONSE
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ All tests completed!${NC}"
echo -e "${BLUE}========================================${NC}"

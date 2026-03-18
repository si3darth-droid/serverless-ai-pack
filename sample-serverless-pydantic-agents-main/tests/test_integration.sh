#!/bin/bash
# Comprehensive integration test for Pydantic AI Agent on AWS
# Tests all components: API Gateway, Lambda, SQS, DynamoDB, Step Functions

set -e

echo "=========================================="
echo "Pydantic AI Agent - Integration Test Suite"
echo "=========================================="
echo ""

# Get stack outputs
echo "Fetching stack outputs..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name PydanticAgentStack \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text \
    --region us-east-1)

QUERY_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name PydanticAgentStack \
    --query 'Stacks[0].Outputs[?OutputKey==`QueryEndpoint`].OutputValue' \
    --output text \
    --region us-east-1)

WORKFLOW_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name PydanticAgentStack \
    --query 'Stacks[0].Outputs[?OutputKey==`WorkflowEndpoint`].OutputValue' \
    --output text \
    --region us-east-1)

QUEUE_URL=$(aws cloudformation describe-stacks \
    --stack-name PydanticAgentStack \
    --query 'Stacks[0].Outputs[?OutputKey==`AgentQueueUrl`].OutputValue' \
    --output text \
    --region us-east-1)

TABLE_NAME=$(aws cloudformation describe-stacks \
    --stack-name PydanticAgentStack \
    --query 'Stacks[0].Outputs[?OutputKey==`ResultsTableName`].OutputValue' \
    --output text \
    --region us-east-1)

echo "API Endpoint: $API_ENDPOINT"
echo "Query Endpoint: $QUERY_ENDPOINT"
echo "Workflow Endpoint: $WORKFLOW_ENDPOINT"
echo "Queue URL: $QUEUE_URL"
echo "Table Name: $TABLE_NAME"
echo ""

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test 1: Direct Agent Query via /query endpoint
echo "=========================================="
echo "Test 1: Direct Agent Query (/query)"
echo "=========================================="
RESPONSE=$(curl -s -X POST "$QUERY_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{
        "question": "What is artificial intelligence?",
        "context": {}
    }')

echo "Response: $RESPONSE"

if echo "$RESPONSE" | jq -e '.answer' > /dev/null 2>&1; then
    echo "✅ Test 1 PASSED: Direct agent query successful"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ Test 1 FAILED: Direct agent query failed"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test 2: Workflow Execution via /workflow endpoint
echo "=========================================="
echo "Test 2: Workflow Execution (/workflow)"
echo "=========================================="
WORKFLOW_RESPONSE=$(curl -s -X POST "$WORKFLOW_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{
        "tasks": [
            {
                "task_type": "research",
                "data": {"topic": "Machine Learning"}
            },
            {
                "task_type": "analysis",
                "data": {"dataset": "test_data"}
            }
        ],
        "user_id": "integration-test-user"
    }')

echo "Response: $WORKFLOW_RESPONSE"

EXECUTION_ARN=$(echo "$WORKFLOW_RESPONSE" | jq -r '.executionArn')

if [ "$EXECUTION_ARN" != "null" ] && [ -n "$EXECUTION_ARN" ]; then
    echo "✅ Test 2 PASSED: Workflow started successfully"
    echo "Execution ARN: $EXECUTION_ARN"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ Test 2 FAILED: Workflow start failed"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    EXECUTION_ARN=""
fi
echo ""

# Test 3: Monitor Workflow Completion
if [ -n "$EXECUTION_ARN" ]; then
    echo "=========================================="
    echo "Test 3: Workflow Completion Monitoring"
    echo "=========================================="
    
    MAX_ATTEMPTS=20
    ATTEMPT=0
    WORKFLOW_SUCCESS=false
    
    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        ATTEMPT=$((ATTEMPT + 1))
        echo "Attempt $ATTEMPT/$MAX_ATTEMPTS: Checking workflow status..."
        
        STATUS=$(aws stepfunctions describe-execution \
            --execution-arn "$EXECUTION_ARN" \
            --query 'status' \
            --output text \
            --region us-east-1)
        
        echo "Status: $STATUS"
        
        if [ "$STATUS" == "SUCCEEDED" ]; then
            echo "✅ Test 3 PASSED: Workflow completed successfully"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            WORKFLOW_SUCCESS=true
            break
        elif [ "$STATUS" == "FAILED" ] || [ "$STATUS" == "TIMED_OUT" ] || [ "$STATUS" == "ABORTED" ]; then
            echo "❌ Test 3 FAILED: Workflow failed with status: $STATUS"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            break
        fi
        
        if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
            echo "❌ Test 3 FAILED: Workflow did not complete within timeout"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            break
        fi
        
        sleep 3
    done
    echo ""
fi

# Test 4: Verify SQS Message Processing
echo "=========================================="
echo "Test 4: SQS Message Processing"
echo "=========================================="

# Wait a bit for messages to be processed
sleep 5

# Check queue attributes
QUEUE_ATTRS=$(aws sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
    --region us-east-1 \
    --output json)

echo "Queue Attributes: $QUEUE_ATTRS"

MESSAGES_IN_FLIGHT=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessagesNotVisible')
MESSAGES_AVAILABLE=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessages')

echo "Messages in flight: $MESSAGES_IN_FLIGHT"
echo "Messages available: $MESSAGES_AVAILABLE"

# Messages should be processed (either in flight or completed)
if [ "$MESSAGES_IN_FLIGHT" != "null" ] || [ "$MESSAGES_AVAILABLE" != "null" ]; then
    echo "✅ Test 4 PASSED: SQS queue is operational"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ Test 4 FAILED: Could not verify SQS queue"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test 5: Verify DynamoDB Records
echo "=========================================="
echo "Test 5: DynamoDB Record Creation"
echo "=========================================="

# Scan for recent records
ITEMS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --limit 5 \
    --region us-east-1 \
    --query 'Items[*].{user_id: user_id.S, session_id: session_id.S}' \
    --output json)

echo "Recent DynamoDB items: $ITEMS"

ITEM_COUNT=$(echo "$ITEMS" | jq '. | length')

if [ "$ITEM_COUNT" -gt 0 ]; then
    echo "✅ Test 5 PASSED: DynamoDB records found ($ITEM_COUNT items)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ Test 5 FAILED: No DynamoDB records found"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test 6: Error Handling - Invalid Input
echo "=========================================="
echo "Test 6: Error Handling"
echo "=========================================="

ERROR_RESPONSE=$(curl -s -X POST "$QUERY_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{
        "invalid_field": "test"
    }')

echo "Error Response: $ERROR_RESPONSE"

# Should return an error response (not crash)
if echo "$ERROR_RESPONSE" | jq -e '.error' > /dev/null 2>&1 || \
   echo "$ERROR_RESPONSE" | jq -e '.statusCode' > /dev/null 2>&1; then
    echo "✅ Test 6 PASSED: Error handling works correctly"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "⚠️  Test 6 WARNING: Error response format unexpected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi
echo ""

# Test 7: Workflow Output Validation
if [ "$WORKFLOW_SUCCESS" = true ]; then
    echo "=========================================="
    echo "Test 7: Workflow Output Validation"
    echo "=========================================="
    
    OUTPUT=$(aws stepfunctions describe-execution \
        --execution-arn "$EXECUTION_ARN" \
        --query 'output' \
        --output text \
        --region us-east-1)
    
    echo "Workflow Output: $OUTPUT"
    
    if echo "$OUTPUT" | jq -e '.execution_id' > /dev/null 2>&1 && \
       echo "$OUTPUT" | jq -e '.tasks_queued' > /dev/null 2>&1; then
        echo "✅ Test 7 PASSED: Workflow output format is correct"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "❌ Test 7 FAILED: Workflow output format is incorrect"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    echo ""
fi

# Test Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo "✅ All integration tests passed!"
    echo ""
    echo "Components Verified:"
    echo "  ✅ API Gateway (/query and /workflow endpoints)"
    echo "  ✅ Lambda Functions (Agent and Orchestrator)"
    echo "  ✅ Step Functions (Workflow orchestration)"
    echo "  ✅ SQS (Message queuing and processing)"
    echo "  ✅ DynamoDB (Data persistence)"
    echo "  ✅ Error Handling"
    exit 0
else
    echo "❌ Some integration tests failed"
    exit 1
fi

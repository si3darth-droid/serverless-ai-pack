# Customer Service Use Case Example (Serverless AI Pack)

This example demonstrates a practical customer service agent implementation using Pydantic AI on AWS serverless architecture as part of **Serverless AI Pack**.

## Scenario

An e-commerce company needs an AI-powered customer service agent that can:
- Answer customer questions about orders
- Look up order status and tracking information
- Provide helpful, empathetic responses
- Maintain conversation context

## Implementation

The customer service agent uses:
- **Specialized system prompt** for customer service context
- **Order lookup tool** to retrieve order information
- **Conversation history tool** to maintain context
- **Type-safe responses** with confidence scores

## Sample Orders

The example includes mock order data for testing:

```json
{
  "ORD-001": {
    "status": "shipped",
    "tracking": "1Z999AA10123456784",
    "eta": "2026-01-08",
    "items": ["Laptop", "Mouse"]
  },
  "ORD-002": {
    "status": "processing",
    "eta": "2026-01-10",
    "items": ["Keyboard"]
  },
  "ORD-003": {
    "status": "delivered",
    "delivered_date": "2026-01-05",
    "items": ["Monitor"]
  }
}
```

## Testing

### Test 1: Order Status Inquiry

**Request:**
```bash
curl -X POST $API_ENDPOINT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the status of my order ORD-001?",
    "context": {"user_id": "customer-123"}
  }'
```

**Expected Response:**
```json
{
  "answer": "Your order ORD-001 has been shipped! The tracking number is 1Z999AA10123456784 and the estimated delivery date is January 8, 2026. Your order includes: Laptop, Mouse.",
  "confidence": 0.98,
  "model_used": "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
}
```

### Test 2: Order Not Found

**Request:**
```bash
curl -X POST $API_ENDPOINT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Where is my order ORD-999?",
    "context": {"user_id": "customer-456"}
  }'
```

**Expected Response:**
```json
{
  "answer": "I apologize, but I couldn't find an order with ID ORD-999 in our system. Please double-check the order number or contact our support team for assistance.",
  "confidence": 0.85,
  "model_used": "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
}
```

### Test 3: General Question

**Request:**
```bash
curl -X POST $API_ENDPOINT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is your return policy?",
    "context": {}
  }'
```

**Expected Response:**
```json
{
  "answer": "Our return policy allows returns within 30 days of delivery for most items. Items must be in original condition with tags attached. To initiate a return, please contact our support team with your order number.",
  "confidence": 0.90,
  "model_used": "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
}
```

## How It Works

1. **Client sends question** to `/query` endpoint with authentication
2. **API Gateway validates** JWT token via Cognito
3. **Lambda agent receives** the question
4. **Agent analyzes** the question and identifies if order lookup is needed
5. **Agent calls tool** `get_order_status("ORD-001")` if order ID detected
6. **Tool retrieves** mock order data from in-memory store
7. **Agent formats** helpful response with order details
8. **Response returned** to client with confidence score

## Key Features Demonstrated

✅ **Tool Usage**: Agent automatically calls `get_order_status` when order ID detected
✅ **Type Safety**: All inputs/outputs validated with Pydantic models
✅ **Context Awareness**: Agent understands customer service context
✅ **Error Handling**: Graceful handling of order not found scenarios
✅ **Confidence Scoring**: Higher confidence (0.98) when data comes from database
✅ **Production Ready**: Deployed on AWS with authentication and monitoring

## Running the Example

1. **Deploy the infrastructure** (if not already deployed):
   ```bash
   cd cdk && cdk deploy
   ```

2. **Get authentication token**:
   ```bash
   export TOKEN=$(aws cognito-idp initiate-auth \
     --auth-flow USER_PASSWORD_AUTH \
     --client-id <CLIENT_ID> \
     --auth-parameters USERNAME=testuser,PASSWORD=TestPass123! \
     --query 'AuthenticationResult.IdToken' \
     --output text)
   ```

3. **Run the test script**:
   ```bash
   ./examples/customer-service/test-customer-service.sh
   ```

## Extending the Example

To adapt this for your use case:

1. **Replace mock data** with actual database queries (DynamoDB, RDS, etc.)
2. **Add more tools** for returns, refunds, account management
3. **Customize system prompt** for your brand voice and policies
4. **Add conversation history** to maintain context across multiple queries
5. **Implement escalation** to human agents for complex issues

## Architecture

```
Client Request
    ↓
API Gateway (with Cognito auth)
    ↓
Lambda (Customer Service Agent)
    ↓
Pydantic AI Agent
    ├─→ get_order_status tool → Mock Order Data
    ├─→ get_user_history tool → DynamoDB
    └─→ store_result tool → DynamoDB
    ↓
Bedrock (Claude 3.5 Sonnet)
    ↓
Response to Client
```

## Monitoring

View agent logs and tool calls:
```bash
aws logs tail /aws/lambda/PydanticAgentStack-AgentFunction --follow
```

Check for tool invocations in logs:
```
INFO: Tool called: get_order_status(order_id='ORD-001')
INFO: Tool result: {'status': 'shipped', 'tracking': '1Z999AA10123456784', ...}
```

## Cost Estimate

For 10,000 customer service queries per month:
- Lambda: ~$2 (1024 MB, 2s avg duration)
- Bedrock: ~$15 (varies by token usage)
- DynamoDB: ~$1 (on-demand pricing)
- API Gateway: ~$0.35
- **Total**: ~$18.35/month

Compare to: Traditional customer service agent salary ($3,000-5,000/month)

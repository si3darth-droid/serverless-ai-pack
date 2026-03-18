import json
import os
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.bedrock import BedrockConverseModel
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
import boto3

logger = Logger()
tracer = Tracer()

# Pydantic models for type-safe inputs/outputs
class QueryInput(BaseModel):
    question: str = Field(..., description="User question to process")
    context: Optional[dict] = Field(default=None, description="Additional context")

class AgentResponse(BaseModel):
    answer: str = Field(..., description="Agent's response")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    model_used: str = Field(..., description="Model identifier")

class AgentDependencies(BaseModel):
    user_id: str
    session_id: str
    dynamodb_table: str

# Initialize Bedrock model - provider will be inferred from environment
model = BedrockConverseModel(
    model_name=os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0')
)

# Create Pydantic AI agent
agent = Agent(
    model=model,
    output_type=AgentResponse,
    system_prompt=(
        "You are a helpful customer service AI assistant for an e-commerce company. "
        "You provide accurate, empathetic, and professional responses to customer inquiries. "
        "Always include a confidence score based on your certainty about the answer.\n\n"
        "You have access to the following tools:\n"
        "- get_order_status: Look up order information by order ID (e.g., 'ORD-001')\n"
        "- get_user_history: Retrieve recent conversation history for a user\n"
        "- store_result: Save your analysis results for future reference\n\n"
        "Guidelines:\n"
        "- When a customer mentions an order number, use get_order_status to retrieve details\n"
        "- Provide specific information from the order data (tracking, ETA, items)\n"
        "- Be empathetic and professional in your responses\n"
        "- If an order is not found, apologize and suggest contacting support\n"
        "- Use higher confidence scores (0.95-0.98) when data comes from the database\n"
        "- Use moderate confidence (0.85-0.90) for general policy questions\n"
        "- Always be helpful and customer-focused"
    )
)

@agent.tool
async def get_order_status(ctx: RunContext[AgentDependencies], order_id: str) -> dict:
    """Look up order status and details by order ID.
    
    Args:
        order_id: The order identifier (e.g., 'ORD-001')
    
    Returns:
        Dictionary containing order details including status, tracking, items, etc.
    """
    # Mock order data for demonstration
    # In production, this would query a real database
    mock_orders = {
        "ORD-001": {
            "order_id": "ORD-001",
            "status": "shipped",
            "tracking_number": "1Z999AA10123456784",
            "carrier": "UPS",
            "estimated_delivery": "2026-01-08",
            "items": ["Laptop - Dell XPS 15", "Wireless Mouse"],
            "total": 1329.98
        },
        "ORD-002": {
            "order_id": "ORD-002",
            "status": "processing",
            "tracking_number": None,
            "estimated_delivery": "2026-01-10",
            "items": ["Mechanical Keyboard"],
            "total": 149.99
        },
        "ORD-003": {
            "order_id": "ORD-003",
            "status": "delivered",
            "tracking_number": "1Z999AA10123456785",
            "delivered_date": "2026-01-05",
            "items": ["27-inch Monitor"],
            "total": 399.99
        }
    }
    
    order = mock_orders.get(order_id.upper())
    if order:
        logger.info(f"Order found: {order_id}")
        return order
    else:
        logger.info(f"Order not found: {order_id}")
        return {"status": "not_found", "order_id": order_id}

@agent.tool
async def get_user_history(ctx: RunContext[AgentDependencies], user_id: str, limit: int = 10) -> list:
    """Retrieve recent conversation history for a user.
    
    Args:
        user_id: The user's unique identifier
        limit: Maximum number of recent conversations to retrieve (default: 10)
    
    Returns:
        List of recent conversation items with results
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(ctx.deps.dynamodb_table)
    
    try:
        # Query by user_id to get recent history
        response = table.query(
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id},
            Limit=limit,
            ScanIndexForward=False  # Most recent first
        )
        items = response.get('Items', [])
        logger.info(f"Retrieved {len(items)} history items for user {user_id}")
        return items
    except Exception as e:
        logger.error(f"Error fetching user history: {e}")
        return []

@agent.tool
async def store_result(ctx: RunContext[AgentDependencies], result: dict) -> bool:
    """Store agent result in DynamoDB for future reference.
    
    Args:
        result: Dictionary containing the result data to store
    
    Returns:
        True if successful, False otherwise
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(ctx.deps.dynamodb_table)
    
    try:
        item = {
            'user_id': ctx.deps.user_id,
            'session_id': ctx.deps.session_id,
            'result': result
        }
        table.put_item(Item=item)
        logger.info(f"Stored result for user {ctx.deps.user_id}, session {ctx.deps.session_id}")
        return True
    except Exception as e:
        logger.error(f"Error storing result: {e}")
        return False

def handle_sqs_event(event: dict, context: LambdaContext) -> dict:
    """Process SQS messages (Stage 2)."""
    batch_item_failures = []
    
    for record in event['Records']:
        try:
            # Parse SQS message body
            body = json.loads(record['body'])
            query_input = QueryInput(**body)
            
            # Create dependencies
            deps = AgentDependencies(
                user_id=body.get('user_id', 'anonymous'),
                session_id=record['messageId'],
                dynamodb_table=os.environ.get('DYNAMODB_TABLE', 'agent-results')
            )
            
            # Run agent synchronously
            result = agent.run_sync(query_input.question, deps=deps)
            
            logger.info(f"SQS message processed successfully", extra={
                'messageId': record['messageId'],
                'confidence': result.output.confidence,
                'model': result.output.model_used
            })
            
        except Exception as e:
            logger.exception(f"Error processing SQS message: {record['messageId']}")
            # Add to batch failures for retry
            batch_item_failures.append({"itemIdentifier": record['messageId']})
    
    return {"batchItemFailures": batch_item_failures}


def handle_api_event(event: dict, context: LambdaContext) -> dict:
    """Process API Gateway events."""
    try:
        # Parse input
        body = json.loads(event.get('body', '{}'))
        query_input = QueryInput(**body)
        
        # Create dependencies
        deps = AgentDependencies(
            user_id=event.get('requestContext', {}).get('authorizer', {}).get('userId', 'anonymous'),
            session_id=event.get('requestContext', {}).get('requestId', 'unknown'),
            dynamodb_table=os.environ.get('DYNAMODB_TABLE', 'agent-results')
        )
        
        # Run agent synchronously
        result = agent.run_sync(query_input.question, deps=deps)
        
        # Get actual Bedrock model ID from environment
        bedrock_model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0')
        
        logger.info(f"Agent response generated", extra={
            'confidence': result.output.confidence,
            'model': bedrock_model_id
        })
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'answer': result.output.answer,
                'confidence': result.output.confidence,
                'model_used': bedrock_model_id
            })
        }
        
    except Exception as e:
        logger.exception("Error processing request")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler for Pydantic AI agent - supports API Gateway and SQS."""
    
    # Check if event is from SQS
    if 'Records' in event and event['Records'] and event['Records'][0].get('eventSource') == 'aws:sqs':
        logger.info("Processing SQS event")
        return handle_sqs_event(event, context)
    else:
        logger.info("Processing API Gateway event")
        return handle_api_event(event, context)

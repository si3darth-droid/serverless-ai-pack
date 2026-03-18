import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add lambda directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lambda'))
from agent import handler, QueryInput, AgentResponse

@pytest.fixture
def lambda_context():
    context = Mock()
    context.function_name = "test-function"
    context.request_id = "test-request-id"
    return context

@pytest.fixture
def api_event():
    return {
        "body": json.dumps({
            "question": "What is the capital of France?",
            "context": {}
        }),
        "requestContext": {
            "requestId": "test-123",
            "authorizer": {
                "userId": "user-456"
            }
        }
    }

def test_query_input_validation():
    valid_input = QueryInput(question="Test question")
    assert valid_input.question == "Test question"
    assert valid_input.context is None

@patch('agent.agent.run_sync')
@patch.dict('os.environ', {'DYNAMODB_TABLE': 'test-table'})
def test_handler_success(mock_run_sync, api_event, lambda_context):
    mock_result = Mock()
    mock_result.output = AgentResponse(
        answer="Paris",
        confidence=0.95,
        model_used="claude-3-5-sonnet"
    )
    mock_run_sync.return_value = mock_result
    
    response = handler(api_event, lambda_context)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['answer'] == "Paris"
    assert body['confidence'] == 0.95

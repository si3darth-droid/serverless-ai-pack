import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add lambda directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lambda'))
from agent import handler, QueryInput, AgentResponse, AgentDependencies

class TestQueryInput:
    def test_valid_input(self):
        """Test valid query input."""
        query = QueryInput(question="What is AI?")
        assert query.question == "What is AI?"
        assert query.context is None
    
    def test_input_with_context(self):
        """Test query input with context."""
        query = QueryInput(
            question="What is AI?",
            context={"user_type": "developer"}
        )
        assert query.context == {"user_type": "developer"}
    
    def test_empty_question_allowed(self):
        """Test that empty question is allowed (validation can be added if needed)."""
        query = QueryInput(question="")
        assert query.question == ""

class TestAgentResponse:
    def test_valid_response(self):
        """Test valid agent response."""
        response = AgentResponse(
            answer="AI is artificial intelligence",
            confidence=0.95,
            model_used="claude-3-5-sonnet"
        )
        assert response.answer == "AI is artificial intelligence"
        assert response.confidence == 0.95
    
    def test_confidence_bounds(self):
        """Test confidence score validation."""
        with pytest.raises(Exception):
            AgentResponse(
                answer="Test",
                confidence=1.5,  # Invalid: > 1.0
                model_used="test"
            )

@pytest.mark.unit
class TestLambdaHandler:
    @patch('agent.agent.run_sync')
    @patch('boto3.resource')
    def test_successful_query(self, mock_boto, mock_run_sync, lambda_context):
        """Test successful agent query."""
        # Mock agent response
        mock_result = Mock()
        mock_result.output = AgentResponse(
            answer="Paris is the capital of France",
            confidence=0.98,
            model_used="claude-3-5-sonnet"
        )
        mock_run_sync.return_value = mock_result
        
        # Create test event
        event = {
            'body': json.dumps({
                'question': 'What is the capital of France?',
                'context': {}
            }),
            'requestContext': {
                'requestId': 'test-123',
                'authorizer': {
                    'userId': 'user-456'
                }
            }
        }
        
        # Execute handler
        response = handler(event, lambda_context)
        
        # Assertions
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'answer' in body
        assert body['confidence'] == 0.98
        # Handler returns actual Bedrock model ID from environment, not the mocked agent output
        assert body['model_used'] == 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
    
    @patch('agent.agent.run_sync')
    def test_handler_error_handling(self, mock_run_sync, lambda_context):
        """Test error handling in handler."""
        mock_run_sync.side_effect = Exception("Bedrock API error")
        
        event = {
            'body': json.dumps({
                'question': 'Test question'
            }),
            'requestContext': {
                'requestId': 'test-123'
            }
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
    
    def test_invalid_json_body(self, lambda_context):
        """Test handling of invalid JSON in request body."""
        event = {
            'body': 'invalid json',
            'requestContext': {
                'requestId': 'test-123'
            }
        }
        
        response = handler(event, lambda_context)
        assert response['statusCode'] == 500

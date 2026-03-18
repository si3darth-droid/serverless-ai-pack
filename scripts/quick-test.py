#!/usr/bin/env python3
"""Quick test script for local development."""

import json
import sys
from unittest.mock import Mock, patch

# Add lambda directory to path
sys.path.insert(0, 'lambda')

def test_agent_locally():
    """Test agent function locally with mocked dependencies."""
    print("🧪 Testing Pydantic AI Agent Locally...\n")
    
    # Mock the agent run
    with patch('lambda.agent.agent.run_sync') as mock_run:
        from lambda.agent import handler, AgentResponse
        
        # Setup mock response
        mock_result = Mock()
        mock_result.data = AgentResponse(
            answer="Serverless architecture offers automatic scaling, pay-per-use pricing, and reduced operational overhead.",
            confidence=0.95,
            model_used="claude-3-5-sonnet"
        )
        mock_run.return_value = mock_result
        
        # Create test event
        event = {
            'body': json.dumps({
                'question': 'What are the benefits of serverless?',
                'context': {}
            }),
            'requestContext': {
                'requestId': 'local-test-123',
                'authorizer': {
                    'userId': 'test-user'
                }
            }
        }
        
        # Mock context
        context = Mock()
        context.function_name = 'local-test'
        context.request_id = 'test-123'
        
        # Execute handler
        response = handler(event, context)
        
        # Display results
        print(f"Status Code: {response['statusCode']}")
        print(f"Response Body:")
        body = json.loads(response['body'])
        print(json.dumps(body, indent=2))
        
        if response['statusCode'] == 200:
            print("\n✅ Local test passed!")
            return True
        else:
            print("\n❌ Local test failed!")
            return False

def test_orchestrator_locally():
    """Test orchestrator function locally."""
    print("\n🔄 Testing Task Orchestrator Locally...\n")
    
    with patch('lambda.task_orchestrator.research_agent.run_sync') as mock_research, \
         patch('lambda.task_orchestrator.analysis_agent.run_sync') as mock_analysis, \
         patch('boto3.resource'):
        
        from lambda.task_orchestrator import handler
        
        # Setup mocks
        mock_research_result = Mock()
        mock_research_result.data = "AI trends show increased adoption of serverless architectures."
        mock_research.return_value = mock_research_result
        
        mock_analysis_result = Mock()
        mock_analysis_result.data = "Analysis shows average value of 30.0"
        mock_analysis.return_value = mock_analysis_result
        
        # Create test event
        event = {
            'execution_id': 'local-exec-123',
            'tasks': [
                {'task_type': 'research', 'data': {'topic': 'AI trends'}},
                {'task_type': 'analysis', 'data': {'metrics': [10, 20, 30, 40, 50]}}
            ]
        }
        
        context = Mock()
        
        # Execute handler
        response = handler(event, context)
        
        print(f"Status Code: {response['statusCode']}")
        print(f"Results:")
        print(json.dumps(response.get('results', []), indent=2))
        
        if response['statusCode'] == 200:
            print("\n✅ Orchestrator test passed!")
            return True
        else:
            print("\n❌ Orchestrator test failed!")
            return False

if __name__ == '__main__':
    success = True
    
    try:
        success = test_agent_locally() and success
        success = test_orchestrator_locally() and success
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    sys.exit(0 if success else 1)

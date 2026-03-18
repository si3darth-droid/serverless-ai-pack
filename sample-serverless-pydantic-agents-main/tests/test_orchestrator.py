import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add lambda directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lambda'))
from task_orchestrator import handler, check_status_handler


@pytest.mark.unit
class TestOrchestratorSQSIntegration:
    """Test orchestrator SQS integration (Stage 3)"""
    
    @patch('boto3.client')
    @patch('boto3.resource')
    @patch.dict(os.environ, {
        'AGENT_QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'RESULTS_TABLE': 'test-results-table'
    })
    def test_orchestrator_queues_tasks_to_sqs(self, mock_boto_resource, mock_boto_client, lambda_context):
        """Test that orchestrator queues tasks to SQS instead of calling Bedrock."""
        # Mock SQS client
        mock_sqs = MagicMock()
        mock_boto_client.return_value = mock_sqs
        mock_sqs.send_message.return_value = {'MessageId': 'msg-123'}
        
        # Mock DynamoDB
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        
        event = {
            'tasks': [
                {'task_type': 'research', 'data': {'topic': 'AI trends'}},
                {'task_type': 'analysis', 'data': {'metrics': [1, 2, 3]}}
            ],
            'execution_id': 'test-exec-123',
            'user_id': 'test-user'
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        assert response['tasks_queued'] == 2
        assert 'queued_tasks' in response
        assert len(response['queued_tasks']) == 2
        
        # Verify SQS was called
        assert mock_sqs.send_message.call_count == 2
    
    @patch('boto3.client')
    @patch('boto3.resource')
    @patch.dict(os.environ, {
        'AGENT_QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'RESULTS_TABLE': 'test-results-table'
    })
    def test_orchestrator_stores_metadata_in_dynamodb(self, mock_boto_resource, mock_boto_client, lambda_context):
        """Test that orchestrator stores execution metadata in DynamoDB."""
        # Mock SQS
        mock_sqs = MagicMock()
        mock_boto_client.return_value = mock_sqs
        mock_sqs.send_message.return_value = {'MessageId': 'msg-456'}
        
        # Mock DynamoDB
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        
        event = {
            'tasks': [{'task_type': 'research', 'data': {'topic': 'test'}}],
            'execution_id': 'exec-789',
            'user_id': 'user-123'
        }
        
        response = handler(event, lambda_context)
        
        # Verify DynamoDB put_item was called
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['user_id'] == 'user-123'
        assert item['session_id'] == 'exec-789'
        assert item['status'] == 'processing'


@pytest.mark.unit
class TestCheckStatusHandler:
    """Test check_status_handler for workflow monitoring (Stage 6)"""
    
    @pytest.fixture
    def check_status_event(self):
        """Sample event for status checking"""
        return {
            'execution_id': 'test-exec-123',
            'user_id': 'test-user',
            'task_ids': ['msg-1', 'msg-2'],
            'current_iteration': 0,
            'max_wait_iterations': 10
        }
    
    @pytest.fixture
    def mock_context(self):
        """Mock Lambda context"""
        context = Mock()
        context.request_id = 'test-request-123'
        context.function_name = 'test-function'
        return context
    
    @patch.dict(os.environ, {
        'RESULTS_TABLE': 'test-results-table',
        'AWS_REGION': 'us-east-1'
    })
    @patch('boto3.resource')
    def test_check_status_processing(self, mock_boto_resource, check_status_event, mock_context):
        """Test status check when tasks are still processing"""
        # Mock DynamoDB response - tasks still processing
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            'Item': {
                'user_id': 'test-user',
                'session_id': 'test-exec-123',
                'execution_id': 'test-exec-123',
                'status': 'processing',
                'task_count': 2
            }
        }
        
        result = check_status_handler(check_status_event, mock_context)
        
        assert result['status'] == 'PROCESSING'
        assert result['execution_id'] == 'test-exec-123'
        assert result['processing_count'] == 2
        assert result['current_iteration'] == 1
    
    @patch.dict(os.environ, {
        'RESULTS_TABLE': 'test-results-table',
        'AWS_REGION': 'us-east-1'
    })
    @patch('boto3.resource')
    def test_check_status_completed(self, mock_boto_resource, check_status_event, mock_context):
        """Test status check when all tasks are completed"""
        # Mock DynamoDB response - tasks completed
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            'Item': {
                'user_id': 'test-user',
                'session_id': 'test-exec-123',
                'execution_id': 'test-exec-123',
                'status': 'completed',
                'task_count': 2
            }
        }
        
        result = check_status_handler(check_status_event, mock_context)
        
        assert result['status'] == 'COMPLETED'
        assert result['completed_count'] == 2
        assert result['failed_count'] == 0
        assert result['processing_count'] == 0
    
    @patch.dict(os.environ, {
        'RESULTS_TABLE': 'test-results-table',
        'AWS_REGION': 'us-east-1'
    })
    @patch('boto3.resource')
    def test_check_status_timeout(self, mock_boto_resource, check_status_event, mock_context):
        """Test status check when max iterations reached"""
        # Set current iteration to max
        check_status_event['current_iteration'] = 10
        
        # Mock DynamoDB response - tasks still processing
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            'Item': {
                'user_id': 'test-user',
                'session_id': 'test-exec-123',
                'status': 'processing',
                'task_count': 2
            }
        }
        
        result = check_status_handler(check_status_event, mock_context)
        
        assert result['status'] == 'TIMEOUT'
        assert result['current_iteration'] == 11
    
    @patch.dict(os.environ, {
        'RESULTS_TABLE': 'test-results-table',
        'AWS_REGION': 'us-east-1'
    })
    @patch('boto3.resource')
    def test_check_status_failed(self, mock_boto_resource, check_status_event, mock_context):
        """Test status check when tasks failed"""
        # Mock DynamoDB response - tasks failed
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            'Item': {
                'user_id': 'test-user',
                'session_id': 'test-exec-123',
                'status': 'failed',
                'task_count': 2
            }
        }
        
        result = check_status_handler(check_status_event, mock_context)
        
        assert result['status'] == 'PARTIAL'
        assert result['failed_count'] == 2
    
    @patch.dict(os.environ, {
        'RESULTS_TABLE': 'test-results-table',
        'AWS_REGION': 'us-east-1'
    })
    @patch('boto3.resource')
    def test_check_status_missing_execution(self, mock_boto_resource, mock_context):
        """Test status check with missing execution_id"""
        event = {'task_ids': ['msg-1']}
        
        result = check_status_handler(event, mock_context)
        
        assert result['status'] == 'ERROR'
        assert 'error' in result
    
    @patch.dict(os.environ, {
        'RESULTS_TABLE': 'test-results-table',
        'AWS_REGION': 'us-east-1'
    })
    @patch('boto3.resource')
    def test_check_status_dynamodb_error(self, mock_boto_resource, check_status_event, mock_context):
        """Test status check when DynamoDB query fails"""
        # Mock DynamoDB error
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.side_effect = Exception("DynamoDB error")
        
        result = check_status_handler(check_status_event, mock_context)
        
        # Should still return a result with processing status
        assert result['status'] == 'PROCESSING'
        assert result['processing_count'] == 2  # Falls back to task_ids count

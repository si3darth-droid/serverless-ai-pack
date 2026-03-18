import pytest
import os
from unittest.mock import Mock

# ============================================================================
# SECURITY NOTICE: Mock Credentials for Unit Testing Only
# ============================================================================
# The credentials below are MOCK VALUES for local unit testing purposes only.
# These are NOT real AWS credentials and are never used for actual AWS access.
# They are required to satisfy boto3 client initialization in test environment.
# Real values like 'testing' are standard mock values in the Python testing community.
# ============================================================================

@pytest.fixture(autouse=True)
def aws_credentials():
    """Mock AWS credentials for testing."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'  # nosec - standard mock value
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'     # nosec - standard mock value
    os.environ['AWS_SESSION_TOKEN'] = 'testing'      # nosec - standard mock value
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    os.environ['DYNAMODB_TABLE'] = 'test-table'
    os.environ['BEDROCK_MODEL_ID'] = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'

@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = 'test-function'
    context.function_version = '$LATEST'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
    context.memory_limit_in_mb = 1024
    context.request_id = 'test-request-id-123'
    context.log_group_name = '/aws/lambda/test-function'
    context.log_stream_name = '2024/01/01/[$LATEST]test'
    return context

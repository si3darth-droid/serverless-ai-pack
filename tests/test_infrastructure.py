"""
Infrastructure tests for CDK stack
Consolidates all infrastructure/CDK tests from stage-specific files
"""
import pytest
import json
from aws_cdk import App
from cdk.stacks.agent_stack import PydanticAgentStack


class TestAPIGateway:
    """Test API Gateway configuration"""
    
    def test_api_gateway_exists(self):
        """Test that API Gateway is created."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        api_gateways = [
            r for r in resources.values()
            if r.get("Type") == "AWS::ApiGateway::RestApi"
        ]
        
        assert len(api_gateways) > 0, "API Gateway not found"
    
    def test_query_endpoint_exists(self):
        """Test that /query endpoint exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        api_resources = [
            r for r in resources.values()
            if r.get("Type") == "AWS::ApiGateway::Resource"
        ]
        
        query_resources = [
            r for r in api_resources
            if r.get("Properties", {}).get("PathPart") == "query"
        ]
        
        assert len(query_resources) > 0, "Query endpoint not found"
    
    def test_workflow_endpoint_exists(self):
        """Test that /workflow endpoint exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        api_resources = [
            r for r in resources.values()
            if r.get("Type") == "AWS::ApiGateway::Resource"
        ]
        
        workflow_resources = [
            r for r in api_resources
            if r.get("Properties", {}).get("PathPart") == "workflow"
        ]
        
        assert len(workflow_resources) > 0, "Workflow endpoint not found"
    
    def test_stepfunctions_integration(self):
        """Test that API Gateway has Step Functions integration."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        methods = [
            r for r in resources.values()
            if r.get("Type") == "AWS::ApiGateway::Method"
        ]
        
        stepfn_integrations = []
        for m in methods:
            integration = m.get("Properties", {}).get("Integration", {})
            if integration.get("Type") == "AWS":
                uri = integration.get("Uri", "")
                uri_str = json.dumps(uri) if isinstance(uri, dict) else str(uri)
                if "states" in uri_str and "StartExecution" in uri_str:
                    stepfn_integrations.append(m)
        
        assert len(stepfn_integrations) > 0, "Step Functions integration not found"


class TestLambdaFunctions:
    """Test Lambda function configuration"""
    
    def test_agent_lambda_exists(self):
        """Test that Agent Lambda function exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        agent_lambdas = [
            r for r in resources.values()
            if r.get("Type") == "AWS::Lambda::Function" and
            "AgentFunction" in json.dumps(r)
        ]
        
        assert len(agent_lambdas) > 0, "Agent Lambda not found"
    
    def test_orchestrator_lambda_exists(self):
        """Test that Orchestrator Lambda function exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        orchestrator_lambdas = [
            r for r in resources.values()
            if r.get("Type") == "AWS::Lambda::Function" and
            "OrchestratorFunction" in json.dumps(r)
        ]
        
        assert len(orchestrator_lambdas) > 0, "Orchestrator Lambda not found"
    
    def test_orchestrator_has_queue_url_env(self):
        """Test that orchestrator has AGENT_QUEUE_URL environment variable."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        orchestrator = None
        for resource in resources.values():
            if resource.get("Type") == "AWS::Lambda::Function":
                props = resource.get("Properties", {})
                if "task_orchestrator" in json.dumps(props):
                    orchestrator = resource
                    break
        
        assert orchestrator is not None, "Orchestrator Lambda not found"
        
        env_vars = orchestrator.get("Properties", {}).get("Environment", {}).get("Variables", {})
        assert "AGENT_QUEUE_URL" in env_vars or "AGENT_QUEUE_URL" in json.dumps(env_vars), \
            "AGENT_QUEUE_URL not found in orchestrator environment"


class TestSQS:
    """Test SQS queue configuration"""
    
    def test_sqs_queue_exists(self):
        """Test that SQS queue exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        queues = [
            r for r in resources.values()
            if r.get("Type") == "AWS::SQS::Queue"
        ]
        
        # Should have at least 2 queues (main queue and DLQ)
        assert len(queues) >= 2, f"SQS queues not found. Found {len(queues)} queues"
    
    def test_dlq_exists(self):
        """Test that Dead Letter Queue exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        dlqs = [
            r for r in resources.values()
            if r.get("Type") == "AWS::SQS::Queue" and
            "DLQ" in json.dumps(r)
        ]
        
        assert len(dlqs) > 0, "Dead Letter Queue not found"
    
    def test_event_source_mapping_exists(self):
        """Test that Lambda event source mapping exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        event_sources = [
            r for r in resources.values()
            if r.get("Type") == "AWS::Lambda::EventSourceMapping"
        ]
        
        assert len(event_sources) > 0, "Event source mapping not found"
    
    def test_event_source_batch_config(self):
        """Test event source mapping batch configuration."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        event_source = None
        for r in resources.values():
            if r.get("Type") == "AWS::Lambda::EventSourceMapping":
                event_source = r
                break
        
        assert event_source is not None
        props = event_source.get("Properties", {})
        assert "BatchSize" in props or "MaximumBatchingWindowInSeconds" in props


class TestStepFunctions:
    """Test Step Functions configuration"""
    
    def test_state_machine_exists(self):
        """Test that Step Functions state machine exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        state_machines = [
            r for r in resources.values()
            if r.get("Type") == "AWS::StepFunctions::StateMachine"
        ]
        
        assert len(state_machines) > 0, "State machine not found"
    
    def test_state_machine_has_logging(self):
        """Test that state machine has CloudWatch logging enabled."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        state_machine = None
        for r in resources.values():
            if r.get("Type") == "AWS::StepFunctions::StateMachine":
                state_machine = r
                break
        
        assert state_machine is not None
        props = state_machine.get("Properties", {})
        assert "LoggingConfiguration" in props or "TracingConfiguration" in props


class TestIAM:
    """Test IAM roles and permissions"""
    
    def test_api_gateway_role_exists(self):
        """Test that IAM role for API Gateway exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        roles = [
            r for r in resources.values()
            if r.get("Type") == "AWS::IAM::Role"
        ]
        
        api_roles = [
            r for r in roles
            if "apigateway.amazonaws.com" in json.dumps(r.get("Properties", {}))
        ]
        
        assert len(api_roles) > 0, "API Gateway IAM role not found"
    
    def test_orchestrator_has_sqs_permissions(self):
        """Test that orchestrator has SQS send permissions."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        policies = [
            r for r in resources.values()
            if r.get("Type") == "AWS::IAM::Policy"
        ]
        
        sqs_send_found = False
        for policy in policies:
            policy_doc = json.dumps(policy.get("Properties", {}))
            if "OrchestratorFunction" in policy_doc and "sqs:SendMessage" in policy_doc:
                sqs_send_found = True
                break
        
        assert sqs_send_found, "Orchestrator should have SQS send permissions"
    
    def test_agent_has_bedrock_permissions(self):
        """Test that agent Lambda has Bedrock permissions."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        policies = [
            r for r in resources.values()
            if r.get("Type") == "AWS::IAM::Policy"
        ]
        
        bedrock_found = False
        for policy in policies:
            policy_doc = json.dumps(policy.get("Properties", {}))
            if "AgentFunction" in policy_doc and "bedrock:InvokeModel" in policy_doc:
                bedrock_found = True
                break
        
        assert bedrock_found, "Agent should have Bedrock permissions"


class TestDynamoDB:
    """Test DynamoDB configuration"""
    
    def test_results_table_exists(self):
        """Test that DynamoDB results table exists."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        tables = [
            r for r in resources.values()
            if r.get("Type") == "AWS::DynamoDB::Table"
        ]
        
        assert len(tables) > 0, "DynamoDB table not found"
    
    def test_table_has_correct_keys(self):
        """Test that table has correct partition and sort keys."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        table = None
        for r in resources.values():
            if r.get("Type") == "AWS::DynamoDB::Table":
                table = r
                break
        
        assert table is not None
        props = table.get("Properties", {})
        key_schema = props.get("KeySchema", [])
        
        partition_key = next((k for k in key_schema if k.get("KeyType") == "HASH"), None)
        sort_key = next((k for k in key_schema if k.get("KeyType") == "RANGE"), None)
        
        assert partition_key is not None, "Partition key not found"
        assert sort_key is not None, "Sort key not found"


class TestStackOutputs:
    """Test CloudFormation stack outputs"""
    
    def test_api_endpoint_output(self):
        """Test that API endpoint is exported."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        outputs = template.get("Outputs", {})
        
        api_endpoint_found = any("ApiEndpoint" in key for key in outputs.keys())
        assert api_endpoint_found, "API endpoint output not found"
    
    def test_queue_outputs(self):
        """Test that queue URL and ARN are exported."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        outputs = template.get("Outputs", {})
        
        output_keys = list(outputs.keys())
        queue_url_found = any("AgentQueueUrl" in key for key in output_keys)
        queue_arn_found = any("AgentQueueArn" in key for key in output_keys)
        
        assert queue_url_found, "Queue URL output not found"
        assert queue_arn_found, "Queue ARN output not found"
    
    def test_state_machine_output(self):
        """Test that state machine ARN is exported."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        outputs = template.get("Outputs", {})
        
        state_machine_found = any("StateMachineArn" in key for key in outputs.keys())
        assert state_machine_found, "State machine ARN output not found"


class TestCompleteConfiguration:
    """Test that all components are properly configured together"""
    
    def test_all_components_exist(self):
        """Test that all required components exist."""
        app = App()
        stack = PydanticAgentStack(app, "TestStack")
        template = app.synth().get_stack_by_name("TestStack").template
        resources = template.get("Resources", {})
        
        has_api = any(r.get("Type") == "AWS::ApiGateway::RestApi" for r in resources.values())
        has_lambda = any(r.get("Type") == "AWS::Lambda::Function" for r in resources.values())
        has_sqs = any(r.get("Type") == "AWS::SQS::Queue" for r in resources.values())
        has_dynamodb = any(r.get("Type") == "AWS::DynamoDB::Table" for r in resources.values())
        has_stepfn = any(r.get("Type") == "AWS::StepFunctions::StateMachine" for r in resources.values())
        has_event_source = any(r.get("Type") == "AWS::Lambda::EventSourceMapping" for r in resources.values())
        
        assert has_api, "API Gateway should exist"
        assert has_lambda, "Lambda functions should exist"
        assert has_sqs, "SQS queue should exist"
        assert has_dynamodb, "DynamoDB table should exist"
        assert has_stepfn, "Step Functions state machine should exist"
        assert has_event_source, "Event source mapping should exist"

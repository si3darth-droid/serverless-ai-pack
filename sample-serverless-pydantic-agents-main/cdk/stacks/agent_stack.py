from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_ecr as ecr,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_sqs as sqs,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_iam as iam,
    aws_logs as logs,
    aws_cognito as cognito,
    aws_wafv2 as wafv2,
    aws_kms as kms,
    RemovalPolicy
)
from constructs import Construct
import json

class PydanticAgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # KMS key for encryption
        encryption_key = kms.Key(
            self, "EncryptionKey",
            description="KMS key for encrypting DynamoDB, SQS, and CloudWatch Logs",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Grant CloudWatch Logs permission to use the KMS key
        encryption_key.add_to_resource_policy(
            iam.PolicyStatement(
                principals=[iam.ServicePrincipal(f"logs.{self.region}.amazonaws.com")],
                actions=["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:CreateGrant", "kms:DescribeKey"],
                resources=["*"],
                conditions={
                    "ArnLike": {
                        "kms:EncryptionContext:aws:logs:arn": f"arn:aws:logs:{self.region}:{self.account}:*"
                    }
                }
            )
        )

        # DynamoDB table for agent results
        results_table = dynamodb.Table(
            self, "AgentResultsTable",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="session_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=encryption_key
        )

        # Dead Letter Queue with encryption
        dlq = sqs.Queue(
            self, "AgentDLQ",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=encryption_key
        )

        # SQS queue for async processing
        agent_queue = sqs.Queue(
            self, "AgentQueue",
            visibility_timeout=Duration.minutes(5),
            retention_period=Duration.days(7),
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=encryption_key,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq
            )
        )

        # Lambda function for Pydantic AI agent
        agent_function = lambda_.DockerImageFunction(
            self, "AgentFunction",
            code=lambda_.DockerImageCode.from_ecr(
                repository=ecr.Repository.from_repository_name(
                    self, "AgentECRRepo",
                    repository_name="pydantic-ai-agent"
                ),
                tag_or_digest="latest"  # Use specific digest for production: sha256:abc123...
            ),
            memory_size=1024,
            timeout=Duration.minutes(5),
            environment={
                "DYNAMODB_TABLE": results_table.table_name,
                "BEDROCK_MODEL_ID": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "POWERTOOLS_SERVICE_NAME": "pydantic-agent",
                "LOG_LEVEL": "INFO"
            },
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Grant Lambda access to KMS key for SQS decryption
        encryption_key.grant_decrypt(agent_function)

        # Grant permissions
        results_table.grant_read_write_data(agent_function)
        agent_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:*:{self.account}:inference-profile/*"
                ]
            )
        )
        
        # Add SQS as event source for Lambda (Stage 2)
        agent_function.add_event_source(
            lambda_events.SqsEventSource(
                agent_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
                report_batch_item_failures=True
            )
        )
        
        # Grant Lambda permission to receive from SQS
        agent_queue.grant_consume_messages(agent_function)

        # Cognito User Pool for API authentication
        user_pool = cognito.UserPool(
            self, "AgentUserPool",
            user_pool_name="pydantic-agent-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=True
            ),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False
            ),
            removal_policy=RemovalPolicy.DESTROY
        )

        # Cognito User Pool Client
        user_pool_client = user_pool.add_client(
            "AgentAppClient",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True
            ),
            generate_secret=False,
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30)
        )

        # API Gateway
        api = apigw.RestApi(
            self, "AgentApi",
            rest_api_name="Pydantic AI Agent API",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigw.MethodLoggingLevel.INFO,
                tracing_enabled=True
            )
        )

        # Cognito Authorizer for API Gateway
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "AgentAuthorizer",
            cognito_user_pools=[user_pool]
        )

        # Add /query endpoint with Cognito authorization
        agent_integration = apigw.LambdaIntegration(agent_function)
        api.root.add_resource("query").add_method(
            "POST",
            agent_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )
        
        # Store API reference for later use with Step Functions
        self.api = api

        # AWS WAF for API Gateway protection
        web_acl = wafv2.CfnWebACL(
            self, "ApiGatewayWAF",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="PydanticAgentWAF",
                sampled_requests_enabled=True
            ),
            rules=[
                # Rule 1: Rate limiting - 100 requests per 5 minutes per IP
                wafv2.CfnWebACL.RuleProperty(
                    name="RateLimitRule",
                    priority=1,
                    statement=wafv2.CfnWebACL.StatementProperty(
                        rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                            limit=100,
                            aggregate_key_type="IP"
                        )
                    ),
                    action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="RateLimitRule",
                        sampled_requests_enabled=True
                    )
                ),
                # Rule 2: AWS Managed Core Rule Set (OWASP Top 10 protection)
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=2,
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesCommonRuleSet"
                        )
                    ),
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWSManagedRulesCommonRuleSet",
                        sampled_requests_enabled=True
                    )
                )
            ]
        )

        # Associate WAF with API Gateway
        wafv2.CfnWebACLAssociation(
            self, "ApiGatewayWAFAssociation",
            resource_arn=f"arn:aws:apigateway:{self.region}::/restapis/{api.rest_api_id}/stages/{api.deployment_stage.stage_name}",
            web_acl_arn=web_acl.attr_arn
        )

        # Task orchestrator Lambda - queues tasks to SQS for parallel processing
        # Note: This is NOT a multi-agent system. The same agent processes all tasks.
        orchestrator_function = lambda_.DockerImageFunction(
            self, "OrchestratorFunction",
            code=lambda_.DockerImageCode.from_ecr(
                repository=ecr.Repository.from_repository_name(
                    self, "OrchestratorECRRepo",
                    repository_name="pydantic-ai-agent"
                ),
                tag_or_digest="latest",  # Use specific digest for production: sha256:abc123...
                cmd=["task_orchestrator.handler"]
            ),
            memory_size=2048,
            timeout=Duration.minutes(10),
            environment={
                "RESULTS_TABLE": results_table.table_name,
                "AGENT_QUEUE_URL": agent_queue.queue_url  # Stage 3: Add queue URL
            },
            tracing=lambda_.Tracing.ACTIVE
        )

        results_table.grant_read_write_data(orchestrator_function)
        
        # Stage 3: Grant orchestrator permission to send to SQS
        agent_queue.grant_send_messages(orchestrator_function)
        
        # Grant orchestrator access to KMS key for SQS encryption
        encryption_key.grant_encrypt(orchestrator_function)

        # Step Functions for enhanced orchestration with error handling and retry logic
        
        # Task to queue work items to SQS
        queue_tasks = tasks.LambdaInvoke(
            self, "QueueTasks",
            lambda_function=orchestrator_function,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
            payload=sfn.TaskInput.from_object({
                "tasks.$": "$.tasks",
                "user_id.$": "$.user_id",
                "execution_id.$": "$$.Execution.Name"
            })
        )
        
        # Success state with result aggregation
        success_state = sfn.Succeed(
            self, "WorkflowSuccess",
            comment="Tasks queued successfully for async processing"
        )
        
        # Error handling state
        error_handler = sfn.Pass(
            self, "LogError",
            parameters={
                "error.$": "$.error",
                "cause.$": "$.cause",
                "timestamp.$": "$$.State.EnteredTime"
            }
        )
        
        error_handler.next(sfn.Fail(
            self, "WorkflowFailed",
            error="WorkflowError",
            cause="An error occurred during workflow execution"
        ))
        
        # Define workflow with retry logic and error handling
        definition = queue_tasks \
            .add_retry(
                errors=["States.TaskFailed", "States.Timeout"],
                interval=Duration.seconds(2),
                max_attempts=3,
                backoff_rate=2.0
            ) \
            .add_catch(error_handler, errors=["States.ALL"], result_path="$.error") \
            .next(success_state)

        state_machine = sfn.StateMachine(
            self, "AgentOrchestration",
            definition=definition,
            timeout=Duration.minutes(5),
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=logs.LogGroup(
                    self, "StateMachineLogs",
                    retention=logs.RetentionDays.ONE_WEEK,
                    removal_policy=RemovalPolicy.DESTROY,
                    encryption_key=encryption_key
                ),
                level=sfn.LogLevel.ALL,
                include_execution_data=True
            )
        )

        # IAM role for API Gateway to invoke Step Functions
        api_stepfn_role = iam.Role(
            self, "ApiStepFnRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            description="Role for API Gateway to start Step Functions execution"
        )
        
        state_machine.grant_start_execution(api_stepfn_role)
        
        # API Gateway integration for Step Functions
        workflow_integration = apigw.AwsIntegration(
            service="states",
            action="StartExecution",
            integration_http_method="POST",
            options=apigw.IntegrationOptions(
                credentials_role=api_stepfn_role,
                request_templates={
                    "application/json": json.dumps({
                        "stateMachineArn": state_machine.state_machine_arn,
                        "input": "$util.escapeJavaScript($input.json('$'))"
                    })
                },
                integration_responses=[
                    apigw.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": json.dumps({
                                "executionArn": "$input.path('$.executionArn')",
                                "startDate": "$input.path('$.startDate')"
                            })
                        }
                    ),
                    apigw.IntegrationResponse(
                        status_code="400",
                        selection_pattern="4\\d{2}",
                        response_templates={
                            "application/json": json.dumps({
                                "error": "Bad Request",
                                "message": "$input.path('$.errorMessage')"
                            })
                        }
                    )
                ]
            )
        )
        
        # Add /workflow endpoint with Cognito authorization
        workflow_resource = self.api.root.add_resource("workflow")
        workflow_resource.add_method(
            "POST",
            workflow_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_models={
                        "application/json": apigw.Model.EMPTY_MODEL
                    }
                ),
                apigw.MethodResponse(
                    status_code="400",
                    response_models={
                        "application/json": apigw.Model.ERROR_MODEL
                    }
                )
            ]
        )

        # Outputs
        CfnOutput(self, "ApiEndpoint", value=self.api.url)
        CfnOutput(self, "QueryEndpoint", value=f"{self.api.url}query")
        CfnOutput(self, "WorkflowEndpoint", value=f"{self.api.url}workflow")
        CfnOutput(self, "ResultsTableName", value=results_table.table_name)
        CfnOutput(self, "StateMachineArn", value=state_machine.state_machine_arn)
        CfnOutput(self, "AgentQueueUrl", value=agent_queue.queue_url)
        CfnOutput(self, "AgentQueueArn", value=agent_queue.queue_arn)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "CognitoRegion", value=self.region)
        CfnOutput(self, "WAFWebACLArn", value=web_acl.attr_arn)
        CfnOutput(self, "KMSKeyId", value=encryption_key.key_id)
        CfnOutput(self, "KMSKeyArn", value=encryption_key.key_arn)

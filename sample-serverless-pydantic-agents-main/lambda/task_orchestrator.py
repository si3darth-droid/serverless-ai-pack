import json
import os
from typing import List
from pydantic import BaseModel
from aws_lambda_powertools import Logger
import boto3

logger = Logger()

class TaskInput(BaseModel):
    task_type: str
    data: dict

class TaskQueuedResult(BaseModel):
    task_type: str
    message_id: str
    queued: bool

def handler(event: dict, context) -> dict:
    """Queue tasks to SQS for parallel processing by the same agent (Stage 3)."""
    try:
        tasks: List[TaskInput] = [TaskInput(**task) for task in event.get('tasks', [])]
        queue_url = os.environ.get('AGENT_QUEUE_URL')
        execution_id = event.get('execution_id', context.request_id if hasattr(context, 'request_id') else 'unknown')
        
        if not queue_url:
            raise ValueError("AGENT_QUEUE_URL environment variable not set")
        
        sqs = boto3.client('sqs')
        queued_tasks = []
        
        # Queue tasks to SQS for parallel processing by Agent Lambda
        # Note: All tasks are processed by the SAME agent, just in parallel
        for task in tasks:
            # Create message body for Agent Lambda
            message_body = {
                "question": f"Process {task.task_type} task: {json.dumps(task.data)}",
                "context": {
                    "task_type": task.task_type,
                    "execution_id": execution_id,
                    "original_data": task.data
                },
                "user_id": event.get('user_id', 'orchestrator')
            }
            
            # Send message to SQS
            response = sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    'task_type': {
                        'StringValue': task.task_type,
                        'DataType': 'String'
                    },
                    'execution_id': {
                        'StringValue': execution_id,
                        'DataType': 'String'
                    }
                }
            )
            
            queued_tasks.append(TaskQueuedResult(
                task_type=task.task_type,
                message_id=response['MessageId'],
                queued=True
            ))
            
            logger.info(f"Queued task to SQS", extra={
                'task_type': task.task_type,
                'message_id': response['MessageId'],
                'execution_id': execution_id
            })
        
        # Store orchestration metadata in DynamoDB
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ.get('RESULTS_TABLE', 'orchestration-results'))
        user_id = str(event.get('user_id', 'orchestrator'))
        
        table.put_item(Item={
            'user_id': user_id,
            'session_id': execution_id,
            'execution_id': execution_id,
            'status': 'processing',
            'task_count': len(tasks),
            'queued_tasks': [t.model_dump() for t in queued_tasks],
            'timestamp': context.request_id if hasattr(context, 'request_id') else 'unknown'
        })
        
        return {
            'statusCode': 200,
            'execution_id': execution_id,
            'user_id': user_id,
            'task_ids': [t.message_id for t in queued_tasks],
            'tasks_queued': len(queued_tasks),
            'queued_tasks': [t.model_dump() for t in queued_tasks],
            'message': f'Successfully queued {len(queued_tasks)} tasks for processing'
        }
        
    except Exception as e:
        logger.exception("Orchestration error")
        return {
            'statusCode': 500,
            'error': str(e),
            'message': 'Failed to queue tasks'
        }

def check_status_handler(event: dict, context) -> dict:
    """Check status of queued tasks by polling DynamoDB (Stage 6)."""
    try:
        execution_id = event.get('execution_id')
        task_ids = event.get('task_ids', [])
        current_iteration = event.get('current_iteration', 0)
        max_iterations = event.get('max_wait_iterations', 10)
        
        if not execution_id:
            raise ValueError("execution_id is required")
        
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ.get('RESULTS_TABLE'))
        
        # Query DynamoDB for task results
        # In a real implementation, you'd query by execution_id
        # For now, we'll check if tasks have been processed
        
        completed_count = 0
        failed_count = 0
        processing_count = 0
        task_statuses = []
        
        # Check orchestration metadata
        try:
            response = table.get_item(
                Key={
                    'user_id': event.get('user_id', 'orchestrator'),
                    'session_id': execution_id
                }
            )
            
            if 'Item' in response:
                item = response['Item']
                status = item.get('status', 'unknown')
                
                # Check if all tasks are completed
                if status == 'completed':
                    completed_count = item.get('task_count', 0)
                elif status == 'failed':
                    failed_count = item.get('task_count', 0)
                else:
                    processing_count = item.get('task_count', 0)
        except Exception as e:
            logger.warning(f"Could not fetch orchestration status: {e}")
            processing_count = len(task_ids)
        
        # Determine overall status
        if completed_count > 0 and failed_count == 0 and processing_count == 0:
            overall_status = "COMPLETED"
        elif failed_count > 0 and processing_count == 0:
            # All tasks failed or some completed with some failed
            overall_status = "PARTIAL"
        elif completed_count > 0 and (failed_count > 0 or processing_count > 0):
            overall_status = "PARTIAL"
        elif current_iteration >= max_iterations:
            overall_status = "TIMEOUT"
        else:
            overall_status = "PROCESSING"
        
        result = {
            'status': overall_status,
            'execution_id': execution_id,
            'completed_count': completed_count,
            'failed_count': failed_count,
            'processing_count': processing_count,
            'current_iteration': current_iteration + 1,
            'max_wait_iterations': max_iterations,
            'timestamp': str(context.request_id if hasattr(context, 'request_id') else 'unknown')
        }
        
        logger.info(f"Status check result", extra=result)
        return result
        
    except Exception as e:
        logger.exception("Status check error")
        return {
            'status': 'ERROR',
            'error': str(e),
            'execution_id': event.get('execution_id', 'unknown'),
            'timestamp': str(context.request_id if hasattr(context, 'request_id') else 'unknown')
        }

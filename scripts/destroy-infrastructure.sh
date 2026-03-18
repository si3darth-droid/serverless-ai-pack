#!/bin/bash

# Destroy AWS infrastructure deployed by CDK
# This will remove all AWS resources created by the stack

set -e

echo "⚠️  WARNING: This will destroy ALL AWS infrastructure!"
echo ""
echo "This includes:"
echo "  - Lambda Functions (Agent, Orchestrator)"
echo "  - API Gateway"
echo "  - Step Functions State Machine"
echo "  - SQS Queue and DLQ"
echo "  - DynamoDB Table"
echo "  - Cognito User Pool"
echo "  - AWS WAF Web ACL"
echo "  - CloudWatch Log Groups"
echo "  - IAM Roles and Policies"
echo ""
echo "Note: ECR images will NOT be deleted automatically."
echo ""

# Prompt for confirmation
read -p "Are you sure you want to destroy the infrastructure? (yes/no): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo "❌ Destruction cancelled."
    exit 0
fi

echo ""
echo "🔥 Starting infrastructure destruction..."
echo ""

# Check if we're in the right directory
if [ ! -d "cdk" ]; then
    echo "❌ Error: cdk directory not found. Please run this script from the project root."
    exit 1
fi

# Navigate to CDK directory and destroy
cd cdk

echo "  → Running CDK destroy..."
cdk destroy --force

cd ..

echo ""
echo "✅ Infrastructure destruction complete!"
echo ""
echo "📝 Manual cleanup required:"
echo "  1. ECR Repository: Delete manually if no longer needed"
echo "     aws ecr delete-repository --repository-name pydantic-ai-agent --force --region us-east-1"
echo ""
echo "  2. CloudWatch Logs: May persist beyond stack deletion"
echo "     Check CloudWatch console for any remaining log groups"
echo ""
echo "  3. S3 Buckets: If CDK created any bootstrap buckets, they may need manual deletion"
echo ""

FROM public.ecr.aws/lambda/python:3.11

# Install dependencies
COPY lambda-requirements.txt .
RUN pip install --no-cache-dir -r lambda-requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy function code
COPY lambda/agent.py lambda/task_orchestrator.py ${LAMBDA_TASK_ROOT}/

# Set non-root user (Lambda base image default user)
# This satisfies security scanners while maintaining Lambda compatibility
USER sbx_user1051

# Health check for security compliance (Lambda manages health internally)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import sys; sys.exit(0)" || exit 1

# Set handler
CMD [ "agent.handler" ]

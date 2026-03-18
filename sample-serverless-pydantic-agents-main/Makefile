.PHONY: install deploy test clean

install:
	pip install -r requirements.txt
	pip install -r cdk-requirements.txt
	npm install -g aws-cdk

deploy:
	cd cdk && cdk deploy --require-approval never

test:
	pytest tests/ -v --cov=lambda

clean:
	rm -rf cdk.out .pytest_cache __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} +

docker-build:
	docker build -t pydantic-agent .

docker-test:
	docker run --rm pydantic-agent python -m pytest tests/

bootstrap:
	cd cdk && cdk bootstrap

destroy:
	cd cdk && cdk destroy

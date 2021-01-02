help: ## Show this text.
	# http://postd.cc/auto-documented-makefile/
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: help build test validate

build: ## Build SAM application.
	sam build --use-container --debug
	cp README.md .aws-sam/build/
	cp LICENSE .aws-sam/build/

test: ## run tests
	python -m pytest tests/ -v

validate: ## validate SAM template
	sam validate

release: build ## Release the application to AWS Serverless Application Repository
	sam package \
		--template-file .aws-sam/build/template.yaml \
		--output-template-file .aws-sam/build/packaged.yaml \
		--s3-bucket shogo82148-sam
	sam publish \
		--template .aws-sam/build/packaged.yaml \
		--region us-east-1

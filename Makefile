help: ## Show this text.
	# http://postd.cc/auto-documented-makefile/
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: help build test validate

build: ## Build SAM application.
	pipenv lock -r > updater/requirements.txt
	sam build --use-container

test: ## run tests
	python -m pytest tests/ -v

validate: ## validate SAM template
	sam validate

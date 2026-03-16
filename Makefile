SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: \
	bootstrap createPythonEnvironment installPythonRequirements \
	createTypeScriptEnvironment installTypeScriptRequirements install \
	deploy destroy \
	clean cleanTypeScript cleanPython cleanCfn cleanMisc \
	help dockerCheck dockerLogin listStacks modelCheck buildNpmModules buildArchive \
	test test-coverage test-lambda test-mcp-workbench test-sdk test-rest-api \
	test-sdk-integ test-integ test-rag-integ test-metadata-integ \
	lock-poetry validate-deps require-aws-config require-yq

#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
HEADLESS ?= false
DOCKER_CMD ?= $(or $(CDK_DOCKER),docker)
PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
YQ ?= yq
NPM ?= npm
CDK ?= npx cdk
EXTRA_CDK_ARGS ?=
CC ?=
CXX ?=

# Helper to read config from config-custom.yaml, then config-base.yaml, then default
# Usage: $(call get_config,.property,default_value)
define get_config
$(strip $(shell \
	if test -f "$(PROJECT_DIR)/config-custom.yaml"; then \
		val="$$( $(YQ) -r '$(1) // ""' "$(PROJECT_DIR)/config-custom.yaml" 2>/dev/null || true )"; \
		if test -n "$$val" && test "$$val" != "null"; then \
			printf '%s' "$$val"; exit 0; \
		fi; \
	fi; \
	if test -f "$(PROJECT_DIR)/config-base.yaml"; then \
		val="$$( $(YQ) -r '$(1) // ""' "$(PROJECT_DIR)/config-base.yaml" 2>/dev/null || true )"; \
		if test -n "$$val" && test "$$val" != "null"; then \
			printf '%s' "$$val"; exit 0; \
		fi; \
	fi; \
	printf '%s' "$(2)" \
))
endef

# Optional CLI/config values
PROFILE ?= $(call get_config,.profile,)
DEPLOYMENT_NAME ?= $(call get_config,.deploymentName,prod)
ACCOUNT_NUMBER ?= $(call get_config,.accountNumber,)
REGION ?= $(call get_config,.region,)
PARTITION ?= $(call get_config,.partition,aws)

# Derived domain for ECR login
DOMAIN ?=
ifeq ($(strip $(DOMAIN)),)
	ifneq ($(findstring isob,$(REGION)),)
		DOMAIN := sc2s.sgov.gov
	else ifneq ($(findstring iso,$(REGION)),)
		DOMAIN := c2s.ic.gov
	else
		DOMAIN := amazonaws.com
	endif
endif

# Config values
APP_NAME := $(call get_config,.appName,lisa)
DEPLOYMENT_STAGE := $(call get_config,.deploymentStage,prod)
MODEL_BUCKET := $(call get_config,.s3BucketModels,)
DOMAIN_NAME := $(call get_config,.apiGatewayConfig.domainName,)

ifeq ($(strip $(DOMAIN_NAME)),)
	BASE_URL := /$(DEPLOYMENT_STAGE)/
else
	BASE_URL := /
endif

# Account IDs for ECR login (unique)
ACCOUNT_NUMBERS_ECR_RAW := $(shell \
	{ \
		test -f "$(PROJECT_DIR)/config-custom.yaml" && $(YQ) -r '.accountNumbersEcr[]? // ""' "$(PROJECT_DIR)/config-custom.yaml" 2>/dev/null; \
		printf '%s\n' "$(ACCOUNT_NUMBER)"; \
	} | awk 'NF' | sort -u \
)
ACCOUNT_NUMBERS_ECR := $(strip $(ACCOUNT_NUMBERS_ECR_RAW))

# Model IDs
MODEL_IDS := $(strip $(shell \
	test -f "$(PROJECT_DIR)/config-custom.yaml" && \
	$(YQ) -r '.ecsModels[]?.modelName // ""' "$(PROJECT_DIR)/config-custom.yaml" 2>/dev/null || true \
))

# Stack selector
STACK ?= $(DEPLOYMENT_STAGE)/*
ifneq ($(findstring $(DEPLOYMENT_STAGE),$(STACK)),$(DEPLOYMENT_STAGE))
	override STACK := $(DEPLOYMENT_STAGE)/$(STACK)
endif

#################################################################################
# VALIDATION                                                                    #
#################################################################################

## Ensure yq is installed
require-yq:
	@command -v "$(YQ)" >/dev/null 2>&1 || { \
		echo "Error: '$(YQ)' is required but not installed."; \
		exit 1; \
	}

## Ensure required AWS deployment config is present
require-aws-config:
	@if [[ -z "$(strip $(ACCOUNT_NUMBER))" ]]; then \
		echo "Error: accountNumber must be set via ACCOUNT_NUMBER or config files."; \
		exit 1; \
	fi
	@if [[ -z "$(strip $(REGION))" ]]; then \
		echo "Error: region must be set via REGION or config files."; \
		exit 1; \
	fi

#################################################################################
# COMMANDS                                                                      #
#################################################################################

## Bootstrap AWS account with CDK bootstrap
bootstrap: require-yq require-aws-config
	@printf "Bootstrapping: %s | %s | %s\n" "$(ACCOUNT_NUMBER)" "$(REGION)" "$(PARTITION)"
	@$(CDK) bootstrap \
		aws://$(ACCOUNT_NUMBER)/$(REGION) \
		$(if $(strip $(PROFILE)),--profile $(PROFILE)) \
		--partition $(PARTITION) \
		--cloudformation-execution-policies arn:$(PARTITION):iam::aws:policy/AdministratorAccess

## Set up Python virtual environment
createPythonEnvironment:
	$(PYTHON) -m venv .venv
	@printf ">>> New virtual environment created. Activate with: source .venv/bin/activate\n"

## Install Python dependencies for development
installPythonRequirements:
	$(if $(strip $(CC)),CC="$(CC)" )$(if $(strip $(CXX)),CXX="$(CXX)" )$(PIP) install --upgrade pip
	$(if $(strip $(CC)),CC="$(CC)" )$(if $(strip $(CXX)),CXX="$(CXX)" )$(PIP) install --prefer-binary -r requirements-dev.txt
	$(if $(strip $(CC)),CC="$(CC)" )$(if $(strip $(CXX)),CXX="$(CXX)" )$(PIP) install -e lisa-sdk
	$(if $(strip $(CC)),CC="$(CC)" )$(if $(strip $(CXX)),CXX="$(CXX)" )$(PIP) install -e lib/serve/mcp-workbench

## Verify Node/npm environment exists
createTypeScriptEnvironment:
	@command -v node >/dev/null 2>&1 || { echo "Error: node is not installed."; exit 1; }
	@command -v $(NPM) >/dev/null 2>&1 || { echo "Error: npm is not installed."; exit 1; }
	@echo "Node and npm detected."

## Install TypeScript dependencies
installTypeScriptRequirements:
	$(NPM) install

## Install all development dependencies
install: installPythonRequirements installTypeScriptRequirements

## Make sure Docker is running
dockerCheck:
	@command -v "$(DOCKER_CMD)" >/dev/null 2>&1 || { \
		echo "Error: docker command '$(DOCKER_CMD)' not found."; \
		exit 1; \
	}
	@$(DOCKER_CMD) ps >/dev/null 2>&1 || { \
		echo "Error: Docker is not running or not accessible via '$(DOCKER_CMD)'."; \
		exit 1; \
	}

## Check if models are uploaded
modelCheck:
	@echo "PROJECT_DIR: $(PROJECT_DIR)"
	@access_token=""; \
	localModelDir="./models"; \
	for MODEL_ID in $(MODEL_IDS); do \
		"$(PROJECT_DIR)/scripts/check-for-models.sh" -m "$$MODEL_ID" -s "$(MODEL_BUCKET)"; \
		if [ $$? -ne 0 ]; then \
			mkdir -p "$$localModelDir"; \
			echo; \
			echo "Preparing and uploading model artifacts for: $$MODEL_ID"; \
			printf "Would you like to continue? [y/N] "; \
			read -r confirm_download; \
			if [ "$${confirm_download:-N}" = "y" ] || [ "$${confirm_download:-N}" = "Y" ]; then \
				if [ -z "$$access_token" ]; then \
					if [ -n "$$HUGGINGFACE_TOKEN" ]; then \
						access_token="$$HUGGINGFACE_TOKEN"; \
					elif [ -f ".hf_token_cache" ]; then \
						access_token="$$(cat .hf_token_cache)"; \
					else \
						printf "What is your Hugging Face access token? "; \
						read -r access_token; \
						printf "%s" "$$access_token" > .hf_token_cache; \
					fi; \
				fi; \
				"$(PROJECT_DIR)/scripts/prepare-and-upload-model.sh" \
					-m "$$MODEL_ID" \
					-s "$(MODEL_BUCKET)" \
					-a "$$access_token" \
					-d "$$localModelDir"; \
			fi; \
		fi; \
	done

## Delete all generated artifacts
clean: cleanTypeScript cleanPython cleanCfn cleanMisc

## Delete all compiled Python files and related artifacts
cleanPython:
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	@find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
	@find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	@find . -type d -name ".tox" -prune -exec rm -rf {} +

## Delete TypeScript artifacts and related folders
cleanTypeScript:
	@find . -type f -name "*.js.map" -delete
	@find . -type d \( -name "dist" -o -name "build" -o -name ".tscache" -o -name ".jest_cache" -o -name "node_modules" -o -name "coverage" \) -prune -exec rm -rf {} +
	@find . -type d -name "cdk.out" -prune -exec rm -rf {} +

## Delete CloudFormation outputs
cleanCfn:
	@find . -type d -name "cdk.out" -prune -exec rm -rf {} +

## Delete miscellaneous local files
cleanMisc:
	@find . -type f -name "*.DS_Store" -delete
	@rm -f .hf_token_cache

## Login Docker CLI to Amazon ECR for all configured accounts
dockerLogin: require-aws-config dockerCheck
	@for account in $(ACCOUNT_NUMBERS_ECR); do \
		echo "Logging into $$account.dkr.ecr.$(REGION).$(DOMAIN)"; \
		aws ecr get-login-password --region "$(REGION)" $(if $(strip $(PROFILE)),--profile "$(PROFILE)") | \
			$(DOCKER_CMD) login --username AWS --password-stdin "$$account.dkr.ecr.$(REGION).$(DOMAIN)" >/dev/null; \
	done

## List CDK stacks
listStacks:
	@$(CDK) list

## Build frontend npm modules
buildNpmModules:
	BASE_URL="$(BASE_URL)" $(NPM) run build

## Build archive assets
buildArchive:
	BUILD_ASSETS=true $(NPM) run build

define print_config
	@printf "\n"
	@printf "DEPLOYING %s STACK APP INFRASTRUCTURE\n" "$(STACK)"
	@printf -- "-----------------------------------\n"
	@printf "Account Number         %s\n" "$(ACCOUNT_NUMBER)"
	@printf "Region                 %s\n" "$(REGION)"
	@printf "Partition              %s\n" "$(PARTITION)"
	@printf "Domain                 %s\n" "$(DOMAIN)"
	@printf "App Name               %s\n" "$(APP_NAME)"
	@printf "Deployment Stage       %s\n" "$(DEPLOYMENT_STAGE)"
	@printf "Deployment Name        %s\n" "$(DEPLOYMENT_NAME)"
	@if [[ -n "$(PROFILE)" ]]; then \
		printf "Deployment Profile     %s\n" "$(PROFILE)"; \
	fi
	@printf -- "-----------------------------------\n"
endef

## Deploy infrastructure
deploy: require-yq require-aws-config install dockerCheck dockerLogin cleanMisc modelCheck buildNpmModules
	$(call print_config)
ifeq ($(HEADLESS),true)
	@$(CDK) deploy "$(STACK)" $(if $(strip $(PROFILE)),--profile "$(PROFILE)") --require-approval never $(EXTRA_CDK_ARGS)
else
	@printf "Is the configuration correct? [y/N] "; \
	read -r confirm_config; \
	if [[ "$${confirm_config:-N}" == "y" || "$${confirm_config:-N}" == "Y" ]]; then \
		$(CDK) deploy "$(STACK)" $(if $(strip $(PROFILE)),--profile "$(PROFILE)") $(EXTRA_CDK_ARGS); \
	else \
		echo "Deployment cancelled."; \
	fi
endif

## Destroy infrastructure
destroy: require-yq require-aws-config cleanMisc
	$(call print_config)
ifeq ($(HEADLESS),true)
	@$(CDK) destroy "$(STACK)" --force $(if $(strip $(PROFILE)),--profile "$(PROFILE)") $(EXTRA_CDK_ARGS)
else
	@printf "Is the configuration correct? [y/N] "; \
	read -r confirm_config; \
	if [[ "$${confirm_config:-N}" == "y" || "$${confirm_config:-N}" == "Y" ]]; then \
		$(CDK) destroy "$(STACK)" --force $(if $(strip $(PROFILE)),--profile "$(PROFILE)") $(EXTRA_CDK_ARGS); \
	else \
		echo "Destroy cancelled."; \
	fi
endif

#################################################################################
# TESTS                                                                        #
#################################################################################

## Run all Python unit tests (non-integration) with coverage report
test-coverage:
	@echo "Running lambda tests with coverage..."
	@pytest test/lambda --verbose \
		--cov=lambda \
		--cov-report=term-missing \
		--cov-report=html:build/coverage \
		--cov-report=xml:build/coverage/coverage.xml \
		--cov-fail-under=83
	@echo
	@echo "Running MCP Workbench tests with coverage..."
	@pytest test/mcp-workbench --verbose \
		--cov=lib/serve/mcp-workbench/src \
		--cov-report=term-missing \
		--cov-report=html:build/coverage-mcp \
		--cov-report=xml:build/coverage-mcp/coverage.xml \
		--cov-append \
		--cov-fail-under=83
	@echo
	@echo "Running SDK tests with coverage..."
	@pytest test/sdk --verbose \
		--cov=lisa-sdk/lisapy \
		--cov-report=term-missing \
		--cov-report=html:build/coverage-sdk \
		--cov-report=xml:build/coverage-sdk/coverage.xml \
		--cov-append \
		--cov-fail-under=80
	@echo
	@echo "Running REST API tests with coverage..."
	@pytest test/rest-api --verbose \
		--cov=lib/serve/rest-api/src \
		--cov-config=lib/serve/rest-api/.coveragerc \
		--cov-report=term-missing \
		--cov-report=html:build/coverage-rest-api \
		--cov-report=xml:build/coverage-rest-api/coverage.xml \
		--cov-append \
		--cov-fail-under=80

## Run all Python unit tests (non-integration) without coverage
test:
	@echo "Running lambda tests..."
	@pytest test/lambda --verbose
	@echo
	@echo "Running MCP Workbench tests..."
	@pytest test/mcp-workbench --verbose
	@echo
	@echo "Running SDK tests..."
	@pytest test/sdk --verbose
	@echo
	@echo "Running REST API tests..."
	@pytest test/rest-api --verbose

## Run lambda tests only
test-lambda:
	pytest test/lambda --verbose

## Run MCP Workbench tests only
test-mcp-workbench:
	pytest test/mcp-workbench --verbose

## Run LISA SDK unit tests only
test-sdk:
	pytest test/sdk --verbose

## Run REST API unit tests only
test-rest-api:
	pytest test/rest-api --verbose

## Run LISA SDK integration tests (requires deployed LISA environment)
test-sdk-integ:
	@echo "Running LISA SDK integration tests..."
	@echo "Note: These tests require a deployed LISA environment with:"
	@echo "  - --api or --url argument for API endpoint"
	@echo "  - --region, --deployment, --profile arguments"
	@echo "  - AWS credentials configured"
	@echo
	@echo "Example: pytest test/integration/sdk --api https://your-api.com --region us-west-2"
	@echo
	pytest test/integration/sdk --verbose

## Run integration tests (Python-based)
test-integ:
	pytest test/python --verbose

## Run RAG integration tests (requires deployed LISA environment)
test-rag-integ:
	@echo "Running RAG integration tests..."
	@echo "Note: These tests require a deployed LISA environment with:"
	@echo "  - LISA_API_URL environment variable set"
	@echo "  - LISA_DEPLOYMENT_NAME environment variable set"
	@echo "  - AWS credentials configured"
	@echo
	pytest test/integration --verbose

## Run repository metadata preservation integration tests
test-metadata-integ:
	pytest test/integration/test_repository_update_metadata_preservation.py --verbose

## Regenerate Poetry lock files
lock-poetry:
	@echo "Regenerating Poetry lock files..."
	@cd lisa-sdk && poetry lock && echo "✓ lisa-sdk/poetry.lock updated"

## Validate all requirements files can be installed
validate-deps:
	@echo "Validating requirements files..."
	@for req in $$(find . -name "requirements*.txt" -not -path "./node_modules/*" -not -path "./.venv/*"); do \
		echo "Checking $$req..."; \
		if pip-compile --dry-run --quiet "$$req" 2>&1 | grep -Ei "error|conflict" >/dev/null; then \
			echo "✗ $$req has conflicts"; \
		else \
			echo "✓ $$req is valid"; \
		fi; \
	done

#################################################################################
# SELF-DOCUMENTING COMMANDS                                                     #
#################################################################################

.DEFAULT_GOAL := help

help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)"
	@echo
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" $(MAKEFILE_LIST) \
	| LC_ALL=C sort --ignore-case \
	| awk -F '---' \
		-v ncol="$$(tput cols)" \
		-v indent=35 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf "%s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}' \
	| more $(shell test "$$(uname)" = Darwin && echo '--no-init --raw-control-chars')
.PHONY: \
	bootstrap createPythonEnvironment installPythonRequirements \
	createTypeScriptEnvironment installTypeScriptRequirements \
	deploy destroy \
	clean cleanTypeScript cleanPython cleanCfn cleanMisc \
	help dockerCheck dockerLogin listStacks modelCheck buildNpmModules

#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
HEADLESS = false
DOCKER_CMD ?= $(or $(CDK_DOCKER),docker)

# Function to read config with fallback to base config and default value
# Usage: VAR := $(call get_config,property,default_value)
define get_config
$(shell test -f $(PROJECT_DIR)/config-custom.yaml && yq -r $(1) $(PROJECT_DIR)/config-custom.yaml 2>/dev/null | grep -v '^null$$' || \
        (test -f $(PROJECT_DIR)/config-base.yaml && yq -r $(1) $(PROJECT_DIR)/config-base.yaml 2>/dev/null | grep -v '^null$$') || \
        echo "$(2)")
endef

# PROFILE (optional argument)
ifeq (${PROFILE},)
PROFILE := $(call get_config,.profile,)
ifeq ($(PROFILE),)
$(warning profile is not set in command line using PROFILE variable or config files, attempting deployment without this variable)
endif
endif

# DEPLOYMENT_NAME
ifeq (${DEPLOYMENT_NAME},)
DEPLOYMENT_NAME := $(call get_config,.deploymentName,prod)
endif

# ACCOUNT_NUMBER
ifeq (${ACCOUNT_NUMBER},)
ACCOUNT_NUMBER := $(call get_config,.accountNumber,)
endif

ifeq (${ACCOUNT_NUMBER},)
$(error accountNumber must be set in command line using ACCOUNT_NUMBER variable or config files)
endif

# REGION
ifeq (${REGION},)
REGION := $(call get_config,.region,)
endif

ifeq (${REGION},)
$(error region must be set in command line using REGION variable or config files)
endif

# PARTITION
ifeq (${PARTITION},)
PARTITION := $(call get_config,.partition,aws)
endif

# DOMAIN - used for the docker login
ifeq (${DOMAIN},)
ifeq ($(findstring isob,${REGION}),isob)
DOMAIN := sc2s.sgov.gov
else ifeq ($(findstring iso,${REGION}),iso)
DOMAIN := c2s.ic.gov
else
DOMAIN := amazonaws.com
endif
endif

# Arguments defined through config files

# APP_NAME
APP_NAME := $(call get_config,.appName,lisa)

# DEPLOYMENT_STAGE
DEPLOYMENT_STAGE := $(call get_config,.deploymentStage,prod)

# ACCOUNT_NUMBERS_ECR - AWS account numbers that need to be logged into with Docker CLI to use ECR
ACCOUNT_NUMBERS_ECR := $(shell test -f $(PROJECT_DIR)/config-custom.yaml && yq '.accountNumbersEcr[]' $(PROJECT_DIR)/config-custom.yaml 2>/dev/null || echo "")

# Append deployed account number to array for dockerLogin rule
ACCOUNT_NUMBERS_ECR := $(ACCOUNT_NUMBERS_ECR) $(ACCOUNT_NUMBER)

# STACK
ifeq ($(STACK),)
	STACK := $(DEPLOYMENT_STAGE)/*
endif

ifneq ($(findstring $(DEPLOYMENT_STAGE),$(STACK)),$(DEPLOYMENT_STAGE))
	override STACK := $(DEPLOYMENT_STAGE)/$(STACK)
endif

# MODEL_IDS - IDs of models to deploy
MODEL_IDS := $(shell test -f $(PROJECT_DIR)/config-custom.yaml && yq '.ecsModels[].modelName' $(PROJECT_DIR)/config-custom.yaml 2>/dev/null || echo "")

# MODEL_BUCKET - S3 bucket containing model artifacts
MODEL_BUCKET := $(call get_config,.s3BucketModels,)

# BASE_URL - Base URL for web UI assets based on domain name and deployment stage
DOMAIN_NAME := $(call get_config,.apiGatewayConfig.domainName,)
ifeq ($(DOMAIN_NAME),)
BASE_URL := /$(DEPLOYMENT_STAGE)/
else
BASE_URL := /
endif

#################################################################################
# COMMANDS                                                                      #
#################################################################################

## Bootstrap AWS Account with CDK bootstrap
bootstrap:
	@printf "Bootstrapping: $(ACCOUNT_NUMBER) | $(REGION) | $(PARTITION)\n"

ifdef PROFILE
	@npx cdk bootstrap \
		--profile $(PROFILE) \
		aws://$(ACCOUNT_NUMBER)/$(REGION) \
		--partition $(PARTITION) \
		--cloudformation-execution-policies arn:$(PARTITION):iam::aws:policy/AdministratorAccess
else
	@npx cdk bootstrap \
		aws://$(ACCOUNT_NUMBER)/$(REGION) \
		--partition $(PARTITION) \
		--cloudformation-execution-policies arn:$(PARTITION):iam::aws:policy/AdministratorAccess
endif


## Set up Python interpreter environment to match LISA deployed version
createPythonEnvironment:
	python3.13 -m venv .venv
	@printf ">>> New virtual environment created. To activate run: 'source .venv/bin/activate'"


## Install Python dependencies for development
installPythonRequirements:
	CC=/usr/bin/gcc10-gcc CXX=/usr/bin/gcc10-g++ pip3 install pip --upgrade
	CC=/usr/bin/gcc10-gcc CXX=/usr/bin/gcc10-g++ pip3 install --prefer-binary -r requirements-dev.txt
	CC=/usr/bin/gcc10-gcc CXX=/usr/bin/gcc10-g++ pip3 install -e lisa-sdk

## Set up TypeScript interpreter environment
createTypeScriptEnvironment:
	npm init


## Install TypeScript dependencies for development
installTypeScriptRequirements:
	npm install

install: installPythonRequirements installTypeScriptRequirements

## Make sure Docker is running
dockerCheck:
	@cmd_output=$$($(DOCKER_CMD) ps); \
	if [ $$? != 0 ]; then \
		echo "Process $(DOCKER_CMD) is not running. Exiting..."; \
		exit 1; \
	fi; \


## Check if models are uploaded
modelCheck:
	@access_token=""; \
	for MODEL_ID in $(MODEL_IDS); do \
		$(PROJECT_DIR)/scripts/check-for-models.sh -m $$MODEL_ID -s $(MODEL_BUCKET); \
		if [ $$? != 0 ]; then \
			localModelDir="./models"; \
			if [ ! -d "$$localModelDir" ]; then \
				mkdir "$$localModelDir"; \
			fi; \
			echo; \
			echo "Preparing to download, convert, and upload safetensors for model: $$MODEL_ID"; \
			echo "Local directory: '$$localModelDir' will be used to store downloaded and converted model weights"; \
			echo "Note: sudo privileges required to remove model dir due to docker mount using root"; \
			echo "Would you like to continue? [y/N] "; \
			read confirm_download; \
			if [ $${confirm_download:-'N'} = 'y' ]; then \
				mkdir -p $$localModelDir; \
				if [ -z "$$access_token" ]; then \
					if [ -n "$$HUGGINGFACE_TOKEN" ]; then \
						access_token="$$HUGGINGFACE_TOKEN"; \
					elif [ -f ".hf_token_cache" ]; then \
						access_token=$$(cat .hf_token_cache); \
					else \
						echo "What is your huggingface access token? "; \
						read access_token; \
						echo "$$access_token" > .hf_token_cache; \
					fi; \
				fi; \
				echo "Converting and uploading safetensors for model: $$MODEL_ID"; \
				tgiImage=$$(yq -r '[.ecsModels[] | select(.inferenceContainer == "tgi") | .baseImage] | first' $(PROJECT_DIR)/config-custom.yaml); \
				if [ "$$tgiImage" = "null" ] || [ -z "$$tgiImage" ]; then \
					tgiImage="ghcr.io/huggingface/text-generation-inference:latest"; \
				fi; \
				echo "Using TGI image: $$tgiImage"; \
				$(PROJECT_DIR)/scripts/convert-and-upload-model.sh -m $$MODEL_ID -s $(MODEL_BUCKET) -a $$access_token -t $$tgiImage -d $$localModelDir; \
			fi; \
		fi; \
	done

## Run all clean commands
clean: cleanTypeScript cleanPython cleanCfn cleanMisc


## Delete all compiled Python files and related artifacts
cleanPython:
	@find . -type f -name "*.py[co]" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type d -name "*.egg-info" -exec rm -rf {} +
	@find . -type d -name "dist" -exec rm -rf {} +
	@find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@find . -type d -name ".tox" -exec rm -rf {} +


## Delete TypeScript artifacts and related folders
cleanTypeScript:
	@find . -type f -name "*.js.map" -delete
	@find . -type d -name "dist" -exec rm -rf {} +
	@find . -type d -name "build" -exec rm -rf {} +
	@find . -type d -name ".tscache" -exec rm -rf {} +
	@find . -type d -name ".jest_cache" -exec rm -rf {} +
	@find . -type d -name "node_modules" -exec rm -rf {} +
	@find . -type d -name "cdk.out" -exec rm -rf {} +
	@find . -type d -name "coverage" -exec rm -rf {} +


## Delete CloudFormation outputs
cleanCfn:
	@find . -type d -name "cdk.out" -exec rm -rf {} +


## Delete all misc files
cleanMisc:
	@find . -type f -name "*.DS_Store" -delete
	@rm -f .hf_token_cache


## Login Docker CLI to Amazon Elastic Container Registry
dockerLogin: dockerCheck
ifdef PROFILE
	@$(foreach ACCOUNT,$(ACCOUNT_NUMBERS_ECR), \
		aws ecr get-login-password --region ${REGION} --profile ${PROFILE} | $(DOCKER_CMD) login --username AWS --password-stdin ${ACCOUNT}.dkr.ecr.${REGION}.${DOMAIN} >/dev/null 2>&1; \
	)
else
	@$(foreach ACCOUNT,$(ACCOUNT_NUMBERS_ECR), \
		aws ecr get-login-password --region ${REGION} | $(DOCKER_CMD) login --username AWS --password-stdin ${ACCOUNT}.dkr.ecr.${REGION}.${DOMAIN} >/dev/null 2>&1; \
	)
endif


listStacks:
	@npx cdk list

buildNpmModules:
	BASE_URL=$(BASE_URL) npm run build

buildArchive:
	BUILD_ASSETS=true npm run build

define print_config
    @printf "\n \
    DEPLOYING $(STACK) STACK APP INFRASTRUCTURE \n \
    -----------------------------------\n \
    Account Number         $(ACCOUNT_NUMBER)\n \
    Region                 $(REGION)\n \
    Partition              $(PARTITION)\n \
    Domain                 $(DOMAIN)\n \
    App Name               $(APP_NAME)\n \
    Deployment Stage       $(DEPLOYMENT_STAGE)\n \
    Deployment Name        $(DEPLOYMENT_NAME)"
    @if [ -n "$(PROFILE)" ]; then \
        printf "\n Deployment Profile     $(PROFILE)"; \
    fi
    @printf "\n-----------------------------------\n"
endef

## Deploy all infrastructure
deploy: installPythonRequirements dockerCheck dockerLogin cleanMisc modelCheck buildNpmModules
	$(call print_config)
ifeq ($(HEADLESS),true)
	npx cdk deploy ${STACK} $(if $(PROFILE),--profile ${PROFILE}) --require-approval never -c ${ENV}='$(shell echo '${${ENV}}')';
else
	@printf "Is the configuration correct? [y/N]  "\
	&& read confirm_config &&\
	if [ $${confirm_config:-'N'} = 'y' ]; then \
		npx cdk deploy ${STACK} $(if $(PROFILE),--profile ${PROFILE})  -c ${ENV}='$(shell echo '${${ENV}}')'; \
	fi;
endif


## Tear down all infrastructure
destroy: cleanMisc
	$(call print_config)
ifeq ($(HEADLESS),true)
	npx cdk destroy ${STACK} --force $(if $(PROFILE),--profile ${PROFILE});
else
	@printf "Is the configuration correct? [y/N]  "\
	&& read confirm_config &&\
	if [ $${confirm_config:-'N'} = 'y' ]; then \
		npx cdk destroy ${STACK} --force $(if $(PROFILE),--profile ${PROFILE}); \
	fi;
endif



#################################################################################
# SELF DOCUMENTING COMMANDS                                                     #
#################################################################################

.DEFAULT_GOAL := help

# Inspired by <http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html>
# sed script explained:
# /^##/:
# 	* save line in hold space
# 	* purge line
# 	* Loop:
# 		* append newline + line to hold space
# 		* go to next line
# 		* if line starts with doc comment, strip comment character off and loop
# 	* remove target prerequisites
# 	* append hold space (+ newline) to line
# 	* replace newline plus comments by `---`
# 	* print line
# Separate expressions are necessary because labels cannot be delimited by
# semicolon; see <http://stackoverflow.com/a/11799865/1968>

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
	}" ${MAKEFILE_LIST} \
	| LC_ALL='C' sort --ignore-case \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
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
	| more $(shell test $(shell uname) = Darwin && echo '--no-init --raw-control-chars')

## Run Python tests with coverage report
test-coverage:
	pytest --verbose \
          --cov lambda \
          --cov-report term-missing \
          --cov-report html:build/coverage \
          --cov-report xml:build/coverage/coverage.xml \
          --cov-fail-under 83

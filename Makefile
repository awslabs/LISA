.PHONY: \
	bootstrap createPythonEnvironment installPythonRequirements \
	createTypeScriptEnvironment installTypeScriptRequirements \
	deploy destroy \
	clean cleanTypeScript cleanPython cleanCfn cleanMisc \
	help dockerCheck dockerLogin listStacks modelCheck buildEcsDeployer

#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

# Arguments defined through command line or config.yaml

# ENV
ifeq (${ENV},)
ENV := $(shell cat $(PROJECT_DIR)/config.yaml | yq '.env')
endif

ifeq (${ENV},)
$(error env must be set in command line using ENV variable or config.yaml)
endif

# PROFILE (optional argument)
ifeq (${PROFILE},)
TEMP_PROFILE := $(shell cat $(PROJECT_DIR)/config.yaml | yq .$(ENV).profile)
ifneq ($(TEMP_PROFILE), null)
PROFILE := ${TEMP_PROFILE}
else
$(warning profile is not set in the command line using PROFILE variable or config.yaml, attempting deployment without this variable)
endif
endif

# DEPLOYMENT_NAME
ifeq (${DEPLOYMENT_NAME},)
DEPLOYMENT_NAME := $(shell cat $(PROJECT_DIR)/config.yaml | yq .$(ENV).deploymentName)
endif

ifeq (${DEPLOYMENT_NAME},)
$(error deploymentName must be set in command line using DEPLOYMENT_NAME variable or config.yaml)
endif

# ACCOUNT_NUMBER
ifeq (${ACCOUNT_NUMBER},)
ACCOUNT_NUMBER := $(shell cat $(PROJECT_DIR)/config.yaml | yq .$(ENV).accountNumber)
endif

ifeq (${ACCOUNT_NUMBER},)
$(error accountNumber must be set in command line using ACCOUNT_NUMBER variable or config.yaml)
endif

# REGION
ifeq (${REGION},)
REGION := $(shell cat $(PROJECT_DIR)/config.yaml | yq .$(ENV).region)
endif

ifeq (${REGION},)
$(error region must be set in command line using REGION variable or config.yaml)
endif

# URL_SUFFIX - used for the docker login
ifeq ($(findstring iso,${REGION}),)
URL_SUFFIX := amazonaws.com
else
URL_SUFFIX := c2s.ic.gov
endif

# Arguments defined through config.yaml

# APP_NAME
APP_NAME := $(shell cat $(PROJECT_DIR)/config.yaml | yq .$(ENV).appName)
ifeq (${APP_NAME},)
$(error appName must be set in config.yaml)
endif

# DEPLOYMENT_STAGE
DEPLOYMENT_STAGE := $(shell cat $(PROJECT_DIR)/config.yaml | yq .$(ENV).deploymentStage)
ifeq (${DEPLOYMENT_STAGE},)
$(error deploymentStage must be set in config.yaml)
endif

# ACCOUNT_NUMBERS_ECR - AWS account numbers that need to be logged into with Docker CLI to use ECR
ACCOUNT_NUMBERS_ECR := $(shell cat $(PROJECT_DIR)/config.yaml | yq .$(ENV).accountNumbersEcr[])

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
MODEL_IDS := $(shell cat $(PROJECT_DIR)/config.yaml | yq '.$(ENV).ecsModels[].modelName')

# MODEL_BUCKET - S3 bucket containing model artifacts
MODEL_BUCKET := $(shell cat $(PROJECT_DIR)/config.yaml | yq '.$(ENV).s3BucketModels')


#################################################################################
# COMMANDS                                                                      #
#################################################################################

## Bootstrap AWS Account with CDK bootstrap
bootstrap:
	@printf "Bootstrapping: $(ACCOUNT_NUMBER) | $(REGION)\n"

ifdef PROFILE
	@cdk bootstrap \
		--profile $(PROFILE) \
		aws://$(ACCOUNT_NUMBER)/$(REGION) \
		--cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess
else
	@cdk bootstrap \
		aws://$(ACCOUNT_NUMBER)/$(REGION) \
		--cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess
endif


## Set up Python interpreter environment
createPythonEnvironment:
	python3 -m venv .venv
	@printf ">>> New virtual environment created. To activate run: 'source .venv/bin/activate'"


## Install Python dependencies for development
installPythonRequirements:
	pip3 install pip --upgrade
	pip3 install -r requirements-dev.txt


## Set up TypeScript interpreter environment
createTypeScriptEnvironment:
	npm init


## Install TypeScript dependencies for development
installTypeScriptRequirements:
	npm install


## Make sure Docker is running
dockerCheck:
	@cmd_output=$$(finch ps); \
	if \
		[ $$? != 0 ]; \
		then \
			echo $$cmd_output; \
			exit 1; \
	fi; \

## Check if models are uploaded
modelCheck:
	@$(foreach MODEL_ID,$(MODEL_IDS), \
		$(PROJECT_DIR)/scripts/check-for-models.sh -m $(MODEL_ID) -s $(MODEL_BUCKET); \
		if \
			[ $$? != 0 ]; \
			then \
				localModelDir="./models"; \
				if \
					[ ! -d "$localModelDir" ]; \
					then \
						mkdir "$localModelDir"; \
				fi; \
				echo; \
				echo "Preparing to download, convert, and upload safetensors for model: $(MODEL_ID)"; \
				echo "Local directory: '$$localModelDir' will be used to store downloaded and converted model weights"; \
				echo "Note: sudo privileges required to remove model dir due to docker mount using root"; \
				echo "Would you like to continue? [y/N] "; \
				read confirm_download; \
				if \
					[ $${confirm_download:-'N'} = 'y' ]; \
					then \
						mkdir -p $$localModelDir; \
						echo "What is your huggingface access token? "; \
						read -s access_token; \
						echo "Converting and uploading safetensors for model: $(MODEL_ID)"; \
						tgiImage=$$(yq '[.$(ENV).ecsModels[] | select(.inferenceContainer == "tgi") | .baseImage] | first' $(PROJECT_DIR)/config.yaml); \
						echo $$tgiImage; \
						$(PROJECT_DIR)/scripts/convert-and-upload-model.sh -m $(MODEL_ID) -s $(MODEL_BUCKET) -a $$access_token -t $$tgiImage -d $$localModelDir; \
				fi; \
		fi; \
	)

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


## Delete CloudFormation outputs
cleanCfn:
	@find . -type d -name "cdk.out" -exec rm -rf {} +


## Delete all misc files
cleanMisc:
	@find . -type f -name "*.DS_Store" -delete


## Login Docker CLI to Amazon Elastic Container Registry
dockerLogin: dockerCheck
ifdef PROFILE
	@$(foreach ACCOUNT,$(ACCOUNT_NUMBERS_ECR), \
		aws ecr get-login-password --region ${REGION} --profile ${PROFILE} | finch login --username AWS --password-stdin $(ACCOUNT).dkr.ecr.${REGION}.${URL_SUFFIX} >/dev/null 2>&1; \
	)
else
	@$(foreach ACCOUNT,$(ACCOUNT_NUMBERS_ECR), \
		aws ecr get-login-password --region ${REGION} | finch login --username AWS --password-stdin $(ACCOUNT).dkr.ecr.${REGION}.${URL_SUFFIX} >/dev/null 2>&1; \
	)
endif

listStacks:
	@npx cdk list

buildEcsDeployer:
	@cd ./ecs_model_deployer && npm install && npm run build &> /dev/null

## Deploy all infrastructure
deploy: dockerCheck dockerLogin cleanMisc modelCheck buildEcsDeployer
ifdef PROFILE
	@printf "\n \
	DEPLOYING $(STACK) STACK APP INFRASTRUCTURE \n \
	-----------------------------------\n \
	Deployment Profile     ${PROFILE}\n \
	Account Number         ${ACCOUNT_NUMBER}\n \
	Region                 ${REGION}\n \
	App Name               ${APP_NAME}\n \
	Deployment Stage       ${DEPLOYMENT_STAGE}\n \
	Deployment Name        ${DEPLOYMENT_NAME}\n \
	-----------------------------------\n \
	Is the configuration correct? [y/N]  "\
	&& read confirm_config &&\
	if \
		[ $${confirm_config:-'N'} = 'y' ]; \
		then \
			npx cdk deploy ${STACK} \
				--profile ${PROFILE} \
				-c ${ENV}='$(shell echo '${${ENV}}')'; \
	fi;
else
	@printf "\n \
	DEPLOYING $(STACK) STACK APP INFRASTRUCTURE \n \
	-----------------------------------\n \
	Account Number         ${ACCOUNT_NUMBER}\n \
	Region                 ${REGION}\n \
	App Name               ${APP_NAME}\n \
	Deployment Stage       ${DEPLOYMENT_STAGE}\n \
	Deployment Name        ${DEPLOYMENT_NAME}\n \
	-----------------------------------\n \
	Is the configuration correct? [y/N]  "\
	&& read confirm_config &&\
	if \
		[ $${confirm_config:-'N'} = 'y' ]; \
		then \
			npx cdk deploy ${STACK} \
				-c ${ENV}='$(shell echo '${${ENV}}')'; \
	fi;
endif


## Tear down all infrastructure
destroy: cleanMisc
ifdef PROFILE
	@printf "\n \
	DESTROYING $(STACK) STACK APP INFRASTRUCTURE \n \
	-----------------------------------\n \
	Deployment Profile     ${PROFILE}\n \
	Account Number         ${ACCOUNT_NUMBER}\n \
	Region                 ${REGION}\n \
	App Name               ${APP_NAME}\n \
	Deployment Stage       ${DEPLOYMENT_STAGE}\n \
	Deployment Name        ${DEPLOYMENT_NAME}\n \
	-----------------------------------\n \
	Is the configuration correct? [y/N]  "\
	&& read confirm_config &&\
	if \
		[ $${confirm_config:-'N'} = 'y' ]; \
		then \
			npx cdk destroy ${STACK} \
				--force \
				--profile ${PROFILE}; \
	fi;
else
	@printf "\n \
	DESTROYING $(STACK) STACK APP INFRASTRUCTURE \n \
	-----------------------------------\n \
	Account Number         ${ACCOUNT_NUMBER}\n \
	Region                 ${REGION}\n \
	App Name               ${APP_NAME}\n \
	Deployment Stage       ${DEPLOYMENT_STAGE}\n \
	Deployment Name        ${DEPLOYMENT_NAME}\n \
	-----------------------------------\n \
	Is the configuration correct? [y/N]  "\
	&& read confirm_config &&\
	if \
		[ $${confirm_config:-'N'} = 'y' ]; \
		then \
			npx cdk destroy ${STACK} \
				--force; \
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

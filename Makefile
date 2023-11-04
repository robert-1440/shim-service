PYTHON_BASE_DIR ?= ~/PycharmProjects

BUILDER_DIR ?= $(PYTHON_BASE_DIR)/terraform-builder

BUILDER_CMD ?= $(PYTHON) $(BUILDER_DIR)/builder/builder.py

PYTHON_UTILS_DIR ?= $(PYTHON_BASE_DIR)/PythonUtils

API_BUILDER=${PYTHON_UTILS_DIR}/api_builder/cli.py

PYTHON ?= python3


PUSH_S3 ?= $(PYTHON) $(PYTHON_UTILS_DIR)/tools/push_s3.py

DOC_BUCKET ?= ls-doc-bucket-448499095521-us-west-1

API_SPEC ?= target/listing-service-api.yaml

OUTPUT_PATH=.
OUR_DIR=${PWD}
REGION ?= us-west-1
ACCOUNT ?= 433933949595
AWS_PROFILE ?= MyRepStudio
SERVICE_DIR=${OUR_DIR}/python/shim-service/
SERVICE_DIST=$(SERVICE_DIR)dist/
LAMBDA_ZIPS_DIR=$(SERVICE_DIST)lambda-zips
LAMBDA_LAYERS_DIR=$(SERVICE_DIST)layers


ifeq ($(origin WORKSPACE), undefined)
	PROJECT = shim-service
	WORKSPACE = default
	TERRAFORM_DIR=terraform
	GATEWAY_DOMAIN_NAME=null
	NO_GATEWAY_DOMAIN=true
	BT_ARGS=--var configServiceUrl=https://sswki1xsfd.execute-api.us-west-1.amazonaws.com
else
	PROJECT = shim-service-$(WORKSPACE)
	TERRAFORM_DIR=terraform-$(WORKSPACE)
	GATEWAY_DOMAIN_NAME=shim-service-$(WORKSPACE).1440.io
	NO_GATEWAY_DOMAIN=false
	BT_ARGS=--var configServiceUrl=https://configuration.1440.io
endif


MAKE_TERRAFORM=make AWS_PROFILE=$(AWS_PROFILE) TERRAFORM_DIR=$(TERRAFORM_DIR) -f InfraMakefile

check-api:
	@${PYTHON} ${API_BUILDER} . validate


gen-doc:
	@echo "Generating documentation ..."
	@${PYTHON} ${API_BUILDER} . doc --zip target

gen-doc-open:
	@${PYTHON} ${API_BUILDER} . doc --create --clean ${TMPDIR}/docs -open

clean-oas:
	@rm -f $(API_SPEC)

oas: clean-oas $(API_SPEC)

$(API_SPEC):
	@${PYTHON} ${API_BUILDER} . oas -o $(API_SPEC)

push-doc:
	@$(PUSH_S3) $(DOC_BUCKET) target/shim-service.zip -target others/shim-service --trim-zip-root -apply


check-doc:
	@${PUSH_S3} ${DOC_BUCKET} target/shim-service.zip --trim-zip-root -target others/shim-service

gp: gen-doc push-doc


build-terraform bt: $(API_SPEC)
	 @$(BUILDER_CMD) --var region=$(REGION) \
			--var region-var=aws_region \
 			--var lambda-zips-dir=$(LAMBDA_ZIPS_DIR) \
 			--var lambda-layers-dir=$(LAMBDA_LAYERS_DIR) \
 			--var api-spec=$(API_SPEC) \
			--var gatewayDomainName=$(GATEWAY_DOMAIN_NAME) \
			--var noGatewayDomain=$(NO_GATEWAY_DOMAIN) \
			--var project=$(PROJECT) --create --path $(OUTPUT_PATH) --terraform-folder $(TERRAFORM_DIR) \
			$(BT_ARGS) \
			--aws ./infra/src



init:
	$(MAKE_TERRAFORM) init

plan:
	@$(MAKE_TERRAFORM) plan

apply:
	@$(MAKE_TERRAFORM) apply

destroy:
	@$(MAKE_TERRAFORM) destroy



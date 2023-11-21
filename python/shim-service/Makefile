PYTHON ?= python3

PYTHON_BASE_DIR ?= ~/PycharmProjects

BUILDER_DIR ?= $(PYTHON_BASE_DIR)/terraform-builder

BUILDER_CMD ?= $(PYTHON) $(BUILDER_DIR)/builder/builder.py

OUR_DIR=${PWD}

OUTPUT_PATH = .
DIST=dist/
LAYERS_DIR = $(DIST)layers/
LAMBDA_ZIPS_DIR=$(DIST)lambda-zips/
PROFILES = web pubsub-poller live-agent-poller notification-publisher scheduler table-listener
LAYERS = requests common gcp crypto platform-events

.PHONY: default qp fast-package package lambda-zips lambda-zip-files clean-lambda-zips layers clean build-all-layers service-keys


default: all-tests
	@:

$(LAYERS_DIR)%.zip: Dockerfile | $(LAYERS_DIR)
	@rm -fr $(LAYERS_DIR)python
	@docker rm -f build-archives 2> /dev/null
	@docker build --quiet --build-arg requirements_file=$(subst $(LAYERS_DIR),,$(subst -layer.zip,,$@))_requirements.txt -t build-py-targets-image .
	@docker create --quiet -it --name build-archives build-py-targets-image bash
	@docker cp --quiet build-archives:/var/task/python $(LAYERS_DIR)python
	@docker rm -f build-archives
	@cd $(LAYERS_DIR) ; zip -q -r $(notdir $@) python
	@rm -fr $(LAYERS_DIR)python

$(LAYERS_DIR):
	@mkdir -p $(LAYERS_DIR)

$(LAMBDA_ZIPS_DIR):
	@mkdir -p $(LAMBDA_ZIPS_DIR)

$(LAMBDA_ZIPS_DIR)%.zip:
	python3 archiver.py ACTIVE_PROFILES=$* $@

service-keys:
	@python3 src/tools/deploy_service_keys.py $(KEYS_TOKEN) $(KEYS_OPTIONS)

tests: all-tests

all-tests:
	@$(PYTHON) tests/run_tests.py --cov


package: all-tests qp
	@:

qp: layers lambda-zips fast-package

fast-package fp: lambda-zips
	@:

clean-lambda-zips:
	@rm -fr $(LAMBDA_ZIPS_DIR)

lambda-zips: clean-lambda-zips lambda-zip-files

# Default target to build all lambda ZIP files
lambda-zip-files: $(foreach profile, $(PROFILES), $(LAMBDA_ZIPS_DIR)$(profile).zip)
	@:


build-all-layers: $(addprefix $(LAYERS_DIR),$(addsuffix -layer.zip, $(LAYERS)))
	@:

layers: build-all-layers
	@:

clean:
	@rm -fr $(DIST) ; mkdir $(DIST)

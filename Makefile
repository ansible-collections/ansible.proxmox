# Helpers for local and CI ansible-test runs.
SHELL := /bin/bash

PYTHON_BIN ?= python3
ANSIBLE_CORE_SPEC ?= ansible-core
UNIT_PYTHON_VERSION ?= 3.12
SANITY_TARGETS ?=
UNIT_TARGETS ?=
INTEGRATION_TARGETS ?=
CLI_ARGS ?=

INSTALLED_COLLECTION_ROOT ?= $(HOME)/.ansible/collections/ansible_collections/ansible/proxmox

# Use the checkout directly when it is already in Ansible's collection layout.
ifeq ($(patsubst %/ansible_collections/ansible/proxmox,MATCH,$(realpath $(CURDIR))),MATCH)
COLLECTION_ROOT ?= .
IN_COLLECTION_TREE := 1
else
COLLECTION_ROOT ?= $(INSTALLED_COLLECTION_ROOT)
IN_COLLECTION_TREE :=
endif

ANSIBLE_COLLECTIONS_PATH ?= $(abspath $(COLLECTION_ROOT)/../../..)
INTEGRATION_CONFIG := $(COLLECTION_ROOT)/tests/integration/integration_config.yml
INTEGRATION_CONFIG_TEMPLATE := $(COLLECTION_ROOT)/tests/integration/integration_config.yml.tpl
INTEGRATION_CONFIG_SCRIPT := $(COLLECTION_ROOT)/tests/integration/generate_integration_config.sh

.PHONY: install-integration-reqs
install-integration-reqs:
	$(PYTHON_BIN) -m pip install --upgrade pip wheel --disable-pip-version-check
	$(PYTHON_BIN) -m pip install "$(ANSIBLE_CORE_SPEC)" -r requirements.txt -r tests/integration/requirements.txt --disable-pip-version-check

.PHONY: install-collection
install-collection:
ifndef IN_COLLECTION_TREE
	ansible-galaxy collection install --force --upgrade -p ~/.ansible/collections .
endif

.PHONY: upgrade-collections
upgrade-collections: install-integration-reqs install-collection

.PHONY: generate-integration-config
generate-integration-config: install-collection $(INTEGRATION_CONFIG)

$(INTEGRATION_CONFIG): $(INTEGRATION_CONFIG_TEMPLATE) $(INTEGRATION_CONFIG_SCRIPT)
	cd "$(COLLECTION_ROOT)" && bash tests/integration/generate_integration_config.sh

.PHONY: integration integration-ci
integration: upgrade-collections generate-integration-config
	cd "$(COLLECTION_ROOT)"; \
	ansible --version; \
	ansible-test --version; \
	ANSIBLE_COLLECTIONS_PATH="$(ANSIBLE_COLLECTIONS_PATH)" \
		ANSIBLE_ROLES_PATH="$(COLLECTION_ROOT)/tests/integration/targets" \
		ansible-test integration $(INTEGRATION_TARGETS) $(CLI_ARGS)

integration-ci: integration

.PHONY: units
units: install-collection
	cd "$(COLLECTION_ROOT)"; \
	ansible-test units --docker --python $(UNIT_PYTHON_VERSION) --coverage $(UNIT_TARGETS); \
	ansible-test coverage combine --requirements --export tests/output/coverage/; \
	ansible-test coverage report --requirements --docker --omit 'tests/*' --show-missing;

.PHONY: units-coverage
units-coverage: units
	cd "$(COLLECTION_ROOT)"; \
	ansible-test coverage xml --requirements; \
	cp tests/output/reports/coverage.xml $(CURDIR)/coverage-units.xml;

.PHONY: sanity
sanity: install-collection
	cd "$(COLLECTION_ROOT)"; \
	ansible-test sanity -v --color --coverage --junit \
			--docker default $(SANITY_TARGETS)

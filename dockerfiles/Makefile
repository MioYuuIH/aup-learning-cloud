# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.

SHELL := /bin/bash

K3S_IMAGES_DIR ?= /var/lib/rancher/k3s/agent/images

# Registry mirror configuration (optional)
# Set these to use alternative registry mirrors for base images
# Use registry address without https:// prefix
# Example: make hub MIRROR_DOCKER=docker.mirrors.example.com MIRROR_QUAY=quay.mirrors.example.com
MIRROR_DOCKER ?=
MIRROR_QUAY ?=

# Build args for docker build (constructed from mirror settings)
BUILD_ARGS :=
ifneq ($(MIRROR_DOCKER),)
  BUILD_ARGS += --build-arg NODE_IMAGE=$(MIRROR_DOCKER)/node:20-alpine
  BUILD_ARGS += --build-arg BASE_IMAGE=$(MIRROR_DOCKER)/ubuntu:24.04
endif
ifneq ($(MIRROR_QUAY),)
  BUILD_ARGS += --build-arg HUB_IMAGE=$(MIRROR_QUAY)/jupyterhub/k8s-hub:4.1.0
  BUILD_ARGS += --build-arg BASE_IMAGE=$(MIRROR_QUAY)/jupyter/base-notebook
endif

.PHONY: all base base-cpu base-gfx1151 hub courses cv dl llm

# Build all images
all: base hub courses

# --- Base Images ---
base: base-cpu base-gfx1151

base-cpu:
	@echo "-------------------------------------------"; \
	 	echo "Building Base Image (cpu)..."; \
		echo "-------------------------------------------";

	cd Base && docker build $(BUILD_ARGS) -t ghcr.io/amdresearch/auplc-default:latest --file Dockerfile.cpu .
	$(MAKE) save-image IMAGE=ghcr.io/amdresearch/auplc-default:latest

base-gfx1151:
	@echo "-------------------------------------------"; \
	 	echo "Building Base Image (gfx1151)..."; \
		echo "-------------------------------------------";

	cd Base && docker build $(BUILD_ARGS) -t ghcr.io/amdresearch/base-gfx1151:v0.1-full --file Dockerfile.gfx1151 .

# --- Hub Image ---
hub:
	@echo "-------------------------------------------"; \
	 	echo "Building Hub Image..."; \
		echo "-------------------------------------------";

	cd Hub && NODE_IMAGE="$(if $(MIRROR_DOCKER),$(MIRROR_DOCKER)/node:20-alpine,)" \
		HUB_IMAGE="$(if $(MIRROR_QUAY),$(MIRROR_QUAY)/jupyterhub/k8s-hub:4.1.0,)" \
		bash ./build.sh
	$(MAKE) save-image IMAGE=ghcr.io/amdresearch/auplc-hub:latest

# --- Course Images ---
courses: cv dl llm

cv:
	@echo "-------------------------------------------"; \
		echo "Building CV Course Image..."; \
		echo "-------------------------------------------";

	cd Courses/CV && bash ./build.sh
	$(MAKE) save-image IMAGE=ghcr.io/amdresearch/auplc-cv:latest

dl:
	@echo "-------------------------------------------"; \
		echo "Building DL Course Image..."; \
		echo "-------------------------------------------";

	cd Courses/DL && bash ./build.sh
	$(MAKE) save-image IMAGE=ghcr.io/amdresearch/auplc-dl:latest

llm:
	@echo "-------------------------------------------"; \
		echo "Building LLM Course Image..."; \
		echo "-------------------------------------------";

	cd Courses/LLM && bash ./build.sh
	$(MAKE) save-image IMAGE=ghcr.io/amdresearch/auplc-llm:latest

# --- Export Images ---
save-image:
	@if [ -n "$(K3S_IMAGES_DIR)" ]; then \
		echo "Exporting $(IMAGE) to $(K3S_IMAGES_DIR)..."; \
		filename=$$(basename $(IMAGE)); \
		filename=$$(echo $$filename | sed 's/:/-/g').tar; \
		out_path="$(K3S_IMAGES_DIR)/$$filename"; \
		echo "-------------------------------------------"; \
		echo "Export: $(IMAGE)"; \
		echo "Save to : $$out_path"; \
		sudo docker save "$(IMAGE)" -o "$$out_path" && echo "✅ Success" || (echo "❌ ERROR"; exit 1); \
		echo "-------------------------------------------"; \
	else \
		echo "K3S_IMAGES_DIR not set. Skipping export for $(IMAGE)."; \
	fi

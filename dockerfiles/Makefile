# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.

SHELL := /bin/bash

K3S_IMAGES_DIR ?= /var/lib/rancher/k3s/agent/images

.PHONY: all base base-cpu base-gfx1151 hub courses cv dl llm

# Build all images
all: base hub courses

# --- Base Images ---
base: base-cpu base-gfx1151

base-cpu:
	@echo "-------------------------------------------"; \
	 	echo "Building Base Image (cpu)..."; \
		echo "-------------------------------------------";

	cd Base && docker build -t ghcr.io/amdresearch/auplc-default:latest --file Dockerfile.cpu .
	$(MAKE) save-image IMAGE=ghcr.io/amdresearch/auplc-default:latest

base-gfx1151:
	@echo "-------------------------------------------"; \
	 	echo "Building Base Image (gfx1151)..."; \
		echo "-------------------------------------------";

	cd Base && docker build -t ghcr.io/amdresearch/base-gfx1151:v0.1-full --file Dockerfile.gfx1151 .

# --- Hub Image ---
hub:
	@echo "-------------------------------------------"; \
	 	echo "Building Hub Image..."; \
		echo "-------------------------------------------";

	cd Hub && ./build.sh
	$(MAKE) save-image IMAGE=ghcr.io/amdresearch/auplc-hub:latest

# --- Course Images ---
courses: cv dl llm

cv:
	@echo "-------------------------------------------"; \
		echo "Building CV Course Image..."; \
		echo "-------------------------------------------";

	cd Courses/CV && ./build.sh
	$(MAKE) save-image IMAGE=ghcr.io/amdresearch/auplc-cv:latest

dl:
	@echo "-------------------------------------------"; \
		echo "Building DL Course Image..."; \
		echo "-------------------------------------------";

	cd Courses/DL && ./build.sh
	$(MAKE) save-image IMAGE=ghcr.io/amdresearch/auplc-dl:latest

llm:
	@echo "-------------------------------------------"; \
		echo "Building LLM Course Image..."; \
		echo "-------------------------------------------";

	cd Courses/LLM && ./build.sh
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

#!/bin/bash
# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Configuration
DOCKER_REGISTRY="your-registry"  # Replace with your registry
IMAGE_NAME="admin-backend"
IMAGE_TAG="latest"

# Build the Docker image
echo "Building Docker image..."
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" ./backend

# Tag the image for the registry
echo "Tagging image for registry..."
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

# Push the image to the registry
echo "Pushing image to registry..."
docker push "${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "Done!"

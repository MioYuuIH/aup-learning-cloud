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

# ========== Global build arguments ==========
ARG NODE_IMAGE=node:20-alpine
ARG HUB_IMAGE=quay.io/jupyterhub/k8s-hub:4.1.0
ARG NPM_REGISTRY=
ARG PIP_INDEX_URL=

# ========== Stage 1: Build Admin UI ==========
FROM ${NODE_IMAGE} AS admin-ui-builder
ARG NPM_REGISTRY

WORKDIR /app

# Install pnpm and configure registry if specified
RUN corepack enable && corepack prepare pnpm@latest --activate
RUN if [ -n "${NPM_REGISTRY}" ]; then pnpm config set registry "${NPM_REGISTRY}"; fi

# Copy package files
COPY runtime/jupyterhub/frontend/admin-ui/package.json runtime/jupyterhub/frontend/admin-ui/pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source files
COPY runtime/jupyterhub/frontend/admin-ui/ ./

# Build the React app
RUN pnpm run build

# ========== Stage 2: Final Hub Image ==========
FROM ${HUB_IMAGE}
ARG PIP_INDEX_URL

# Switch to root for setup
USER root

# Install uv (much faster than pip)
RUN pip install --no-cache-dir uv

# Create the needed folders
RUN mkdir -p /tmp/custom_templates/static/css /tmp/custom_templates/static/js \
    /usr/local/share/jupyterhub/static/admin-ui

# Copy template files with correct permissions
COPY --chmod=644 runtime/jupyterhub/frontend/templates/ /tmp/custom_templates/

# Copy admin-ui build output
COPY --from=admin-ui-builder /app/dist/ /usr/local/share/jupyterhub/static/admin-ui/

# Fix permissions
RUN chown -R 1000:1000 /usr/local/share/jupyterhub/static/admin-ui/

# Install Python packages with uv (10-100x faster than pip)
COPY runtime/jupyterhub/requirements.txt /tmp/requirements.txt
RUN if [ -n "${PIP_INDEX_URL}" ]; then \
        uv pip install --system --index-url "${PIP_INDEX_URL}" -r /tmp/requirements.txt; \
    else \
        uv pip install --system -r /tmp/requirements.txt; \
    fi

# Copy core business logic package
COPY runtime/jupyterhub/core/ /usr/local/lib/core/

# Ensure correct permissions for core (755 for dirs, 644 for files)
RUN chown -R 1000:1000 /usr/local/lib/core/ && \
    find /usr/local/lib/core/ -type d -exec chmod 755 {} \; && \
    find /usr/local/lib/core/ -type f -exec chmod 644 {} \;

# Add core to Python path
ENV PYTHONPATH="/usr/local/lib"

# Switch back to jovyan user
USER jovyan

# Set environment variable for template path
ENV JUPYTERHUB_TEMPLATE_PATH=/tmp/custom_templates

RUN echo "=== Verifying template files ===" && \
    ls -la /tmp/custom_templates && \
    echo "=== Checking for resource_options_form.html ===" && \
    ls -la /tmp/custom_templates/resource_options_form.html && \
    echo "=== Checking static directory ===" && \
    ls -la /tmp/custom_templates/static/ && \
    echo "=== Checking admin-ui ===" && \
    ls -la /usr/local/share/jupyterhub/static/admin-ui/ && \
    echo "=== Template verification complete ==="

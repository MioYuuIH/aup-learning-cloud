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

# ========== Stage 1: Build Admin UI ==========
ARG NODE_IMAGE=node:20-alpine
ARG NPM_REGISTRY=
FROM ${NODE_IMAGE} AS admin-ui-builder

WORKDIR /app

# Install pnpm and configure registry if specified
RUN corepack enable && corepack prepare pnpm@latest --activate
RUN if [ -n "${NPM_REGISTRY}" ]; then pnpm config set registry "${NPM_REGISTRY}"; fi

# Copy package files
COPY admin-ui/package.json admin-ui/pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source files
COPY admin-ui/ ./

# Build the React app
RUN pnpm run build

# ========== Stage 2: Final Hub Image ==========
ARG HUB_IMAGE=quay.io/jupyterhub/k8s-hub:4.1.0
ARG PIP_INDEX_URL=
FROM ${HUB_IMAGE}

# Switch to root for setup
USER root

# Create the needed folders
RUN mkdir -p /tmp/custom_templates
RUN mkdir -p /tmp/custom_templates/static/css
RUN mkdir -p /tmp/custom_templates/static/js
RUN mkdir -p /usr/local/share/jupyterhub/static/admin-ui

# Copy template files with correct permissions
COPY --chmod=644 templates/ /tmp/custom_templates/

# Copy admin-ui build output
COPY --from=admin-ui-builder /app/dist/ /usr/local/share/jupyterhub/static/admin-ui/

# Fix permissions
RUN chown -R 1000:1000 /usr/local/share/jupyterhub/static/admin-ui/

# Install Python packages as root
RUN if [ -n "${PIP_INDEX_URL}" ]; then \
        pip install -i "${PIP_INDEX_URL}" jupyterhub-multiauthenticator jupyterhub-firstuseauthenticator pydantic; \
    else \
        pip install jupyterhub-multiauthenticator jupyterhub-firstuseauthenticator pydantic; \
    fi

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

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

# Global build arguments
ARG NODE_IMAGE=node:20-alpine
ARG HUB_IMAGE=quay.io/jupyterhub/k8s-hub:4.1.0
ARG NPM_REGISTRY=
ARG PIP_INDEX_URL=

# Stage 1: Build frontend (monorepo)
FROM ${NODE_IMAGE} AS frontend-builder
ARG NPM_REGISTRY

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10.27.0 --activate
RUN if [ -n "${NPM_REGISTRY}" ]; then pnpm config set registry "${NPM_REGISTRY}"; fi

# Copy monorepo configuration and lockfile
COPY runtime/hub/frontend/pnpm-workspace.yaml runtime/hub/frontend/pnpm-lock.yaml runtime/hub/frontend/.npmrc runtime/hub/frontend/package.json runtime/hub/frontend/tsconfig.base.json ./

# Copy package.json files for dependency installation
COPY runtime/hub/frontend/packages/shared/package.json ./packages/shared/
COPY runtime/hub/frontend/apps/admin/package.json ./apps/admin/
COPY runtime/hub/frontend/apps/spawn/package.json ./apps/spawn/

# Install dependencies with frozen lockfile
RUN pnpm install --frozen-lockfile

# Copy source code
COPY runtime/hub/frontend/packages/ ./packages/
COPY runtime/hub/frontend/apps/ ./apps/

# Build all packages
RUN pnpm run build

# Stage 2: Final Hub image
FROM ${HUB_IMAGE}
ARG PIP_INDEX_URL

USER root

# Frontend: templates and static files
RUN mkdir -p /tmp/custom_templates/static/css /tmp/custom_templates/static/js \
    /usr/local/share/jupyterhub/static/admin-ui \
    /usr/local/share/jupyterhub/static/spawn-ui

COPY --chmod=644 runtime/hub/frontend/templates/ /tmp/custom_templates/
COPY --from=frontend-builder /app/apps/admin/dist/ /usr/local/share/jupyterhub/static/admin-ui/
COPY --from=frontend-builder /app/apps/spawn/dist/ /usr/local/share/jupyterhub/static/spawn-ui/
RUN chown -R 1000:1000 /usr/local/share/jupyterhub/static/admin-ui/ \
    /usr/local/share/jupyterhub/static/spawn-ui/

# Backend: Python dependencies and core logic
RUN pip install --no-cache-dir uv

COPY runtime/hub/requirements.txt /tmp/requirements.txt
RUN if [ -n "${PIP_INDEX_URL}" ]; then \
        uv pip install --system --index-url "${PIP_INDEX_URL}" -r /tmp/requirements.txt; \
    else \
        uv pip install --system -r /tmp/requirements.txt; \
    fi

COPY runtime/hub/core/ /usr/local/lib/core/
RUN chown -R 1000:1000 /usr/local/lib/core/ && \
    find /usr/local/lib/core/ -type d -exec chmod 755 {} \; && \
    find /usr/local/lib/core/ -type f -exec chmod 644 {} \;

ENV PYTHONPATH="/usr/local/lib"

# Finalize
USER jovyan
ENV JUPYTERHUB_TEMPLATE_PATH=/tmp/custom_templates

RUN ls -la /tmp/custom_templates && \
    ls -la /usr/local/share/jupyterhub/static/admin-ui/ && \
    ls -la /usr/local/share/jupyterhub/static/spawn-ui/

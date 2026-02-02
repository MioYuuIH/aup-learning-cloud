# Single-Node Deployment

This guide provides step-by-step instructions for manually deploying AUP Learning Cloud on a single node. This deployment is suitable for development, testing, and demo environments.

:::{seealso}
For quick automated installation, see the [Quick Start](quick-start.md) guide.
:::

## Prerequisites

### Hardware Requirements

- **Device**: AMD Ryzen™ AI Halo Device (e.g., AI Max+ 395, AI Max 390)
- **Memory**: 32GB+ RAM (64GB recommended for production-like testing)
- **Storage**: 500GB+ SSD
- **Network**: Stable internet connection for downloading images

### Software Requirements

- **Operating System**: Ubuntu 24.04.3 LTS
- **Docker**: Version 20.10 or later
- **Root/Sudo Access**: Required for installation

## Installation Steps

### 1. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Add current user to docker group
sudo usermod -aG docker $USER

# Apply group changes (or logout/login)
newgrp docker

# Install Build Tools
sudo apt install build-essential

# Verify installation
docker --version
```

:::{seealso}
See [Docker Post-installation Steps](https://docs.docker.com/engine/install/linux-postinstall/) for detailed configuration.
:::

### 2. Install K3s

K3s is a lightweight Kubernetes distribution optimized for resource-constrained environments.

```bash
# Install K3s
curl -sfL https://get.k3s.io | sh -

# Verify installation
sudo k3s kubectl get nodes
```

### 3. Configure kubectl

```bash
# Create kubectl config directory
mkdir -p ~/.kube

# Copy K3s config
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config

# Fix permissions
sudo chown $USER:$USER ~/.kube/config

# Verify
kubectl get nodes
```

### 4. Install Helm

Helm is the package manager for Kubernetes.

```bash
# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify installation
helm version
```

### 5. Clone the Repository

```bash
# Clone the repository
git clone https://github.com/AMDResearch/aup-learning-cloud.git
cd aup-learning-cloud
```

### 6. Build Docker Images

```bash
# Navigate to dockerfiles directory
cd dockerfiles

# Build all images
make all

# This will build:
# - Base CPU image
# - JupyterHub hub image
# - Course images (DL, LLM, CV)
```

:::{note}
Building images may take 30-60 minutes depending on your internet connection and hardware.
:::

### 7. Configure JupyterHub

Edit the configuration file `runtime/values.yaml`:

```bash
cd ../runtime
nano values.yaml
```

Key settings to configure:

- Network access (NodePort or Domain)
- Authentication (GitHub OAuth or Native)
- Storage (NFS settings)
- Resource limits

See [JupyterHub Configuration](../jupyterhub/index.md) for detailed configuration options.

### 8. Deploy JupyterHub

```bash
# Deploy using Helm
bash scripts/helm_upgrade.bash
```

### 9. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n jupyterhub

# Check services
kubectl get svc -n jupyterhub

# Get admin credentials (if auto-admin is enabled)
kubectl -n jupyterhub get secret jupyterhub-admin-credentials \
  -o go-template='{{index .data "admin-password" | base64decode}}'
```

## Access JupyterHub

- **NodePort (default)**: <http://localhost:30890> or <http://node-ip:30890>
- **Domain**: <https://your-domain.com> (if configured)

## Post-Installation

### Configure Authentication

See [Authentication Guide](../jupyterhub/authentication-guide.md) to set up:
- GitHub OAuth
- Native Authenticator
- User management

### Configure Resource Quotas

See [User Quota System](../jupyterhub/quota-system.md) to configure resource limits and tracking.

### Manage Users

See [User Management Guide](../jupyterhub/user-management.md) for batch user operations.

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n jupyterhub

# Check logs
kubectl logs <pod-name> -n jupyterhub
```

### Image Pull Errors

```bash
# Check events
kubectl get events -n jupyterhub

# Verify images are available
docker images | grep ghcr.io/amdresearch
```

### Connection Issues

```bash
# Check service status
kubectl get svc -n jupyterhub

# Check ingress (if using domain)
kubectl get ingress -n jupyterhub
```

## Upgrading

To upgrade JupyterHub after configuration changes:

```bash
cd runtime
bash scripts/helm_upgrade.bash
```

To rebuild images after code changes:

```bash
cd dockerfiles
make all
```

## Uninstalling

To completely remove the installation:

```bash
cd deploy
sudo ./single-node.sh uninstall
```

## Next Steps

- [Configure JupyterHub](../jupyterhub/index.md)
- [Set up Authentication](../jupyterhub/authentication-guide.md)
- [Manage Users](../jupyterhub/user-management.md)
- [Configure Quotas](../jupyterhub/quota-system.md)

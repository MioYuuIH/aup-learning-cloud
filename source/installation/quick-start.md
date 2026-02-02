# Quick Start

The simplest way to deploy AUP Learning Cloud on a single machine in a development or demo environment.

## Prerequisites

- **Hardware**: AMD Ryzen™ AI Halo Device (e.g., AI Max+ 395, AI Max 390)
- **Memory**: 32GB+ RAM (64GB recommended)
- **Storage**: 500GB+ SSD
- **OS**: Ubuntu 24.04.3 LTS
- **Docker**: Install Docker and configure for non-root access

### Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Add current user to docker group
sudo usermod -aG docker $USER

# Apply group changes without logout (or logout/login instead)
newgrp docker

# Install Build Tools
sudo apt install build-essential
```

:::{seealso}
See [Docker Post-installation Steps](https://docs.docker.com/engine/install/linux-postinstall/) and [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) for details.
:::

## Installation

```bash
git clone https://github.com/AMDResearch/aup-learning-cloud.git
cd aup-learning-cloud/deploy/
sudo ./single-node.sh install
```

After installation completes, open <http://localhost:30890> in your browser. No login credentials are required - you will be automatically logged in.

## Script Commands

| Command | Description |
|---------|-------------|
| `install` | Full installation (K3s, tools, GPU plugin, images, JupyterHub) |
| `uninstall` | Complete removal of all components |
| `upgrade-runtime` | Upgrade JupyterHub deployment |
| `build-images` | Build and import container images |
| `install-tools` | Install Helm and K9s only |
| `install-runtime` | Deploy JupyterHub only |
| `remove-runtime` | Remove JupyterHub only |

### Examples

```bash
# Upgrade JupyterHub after configuration changes
sudo ./single-node.sh upgrade-runtime

# Rebuild images after modifying Dockerfiles
sudo ./single-node.sh build-images
```

## Next Steps

After installation:

1. Access JupyterHub at <http://localhost:30890>
2. Review the [JupyterHub Configuration](../jupyterhub/index.md) guide
3. Set up [Authentication](../jupyterhub/authentication-guide.md) if needed
4. Configure [User Management](../jupyterhub/user-management.md) for your environment
5. Explore the available learning toolkits

:::{tip}
For manual installation or more control, see the [Single-Node Deployment](single-node.md) guide.
:::

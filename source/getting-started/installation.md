# Installation Guide

This guide provides detailed installation instructions for different deployment scenarios.

## Deployment Options

1. **Single-Node Deployment** - For development and demo environments
2. **Multi-Node Cluster Deployment** - For production environments

## Single-Node Deployment

For the quickest deployment, see the [Quick Start](quick-start.md) guide.

### Manual Installation

For users who prefer step-by-step manual installation or need more control over the deployment process.

#### Prerequisites

Same as Quick Start:
- AMD Ryzen™ AI Halo Device
- 32GB+ RAM (64GB recommended)
- 500GB+ SSD
- Ubuntu 24.04.3 LTS
- Docker installed and configured

#### Installation Steps

1. **Install K3s**:
   ```bash
   curl -sfL https://get.k3s.io | sh -
   ```

2. **Configure kubectl**:
   ```bash
   mkdir -p ~/.kube
   sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
   sudo chown $USER:$USER ~/.kube/config
   ```

3. **Install Helm**:
   ```bash
   curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
   ```

4. **Clone the repository**:
   ```bash
   git clone https://github.com/AMDResearch/aup-learning-cloud.git
   cd aup-learning-cloud
   ```

5. **Build Docker images**:
   ```bash
   cd dockerfiles
   make all
   ```

6. **Deploy JupyterHub**:
   ```bash
   cd ../runtime
   bash scripts/helm_upgrade.bash
   ```

## Multi-Node Cluster Deployment

For production deployments with multiple nodes, use the Ansible playbooks provided in the `deploy/ansible` directory.

### Prerequisites

- Multiple AMD Ryzen™ AI Halo devices
- Ubuntu 24.04.3 LTS on all nodes
- SSH access configured between nodes
- Ansible installed on control node

### Deployment Steps

1. **Update inventory file**:
   Edit `deploy/ansible/inventory.yml` with your node information.

2. **Run base setup**:
   ```bash
   cd deploy/ansible
   ansible-playbook playbooks/pb-base.yml
   ```

3. **Install K3s cluster**:
   ```bash
   ansible-playbook playbooks/pb-k3s-site.yml
   ```

4. **Configure NFS provisioner**:
   Follow the guide in `deploy/k8s/nfs-provisioner/README.md`

5. **Deploy JupyterHub**:
   ```bash
   cd runtime
   bash scripts/helm_upgrade.bash
   ```

## Configuration

After installation, you'll need to configure various aspects of your deployment:

### Network Access

Choose between NodePort or Domain access. See [JupyterHub Configuration](../jupyterhub/index.md) for details.

### Authentication

Set up GitHub OAuth or Native Authentication. See [Authentication Guide](../jupyterhub/authentication-guide.md).

### User Management

Configure user accounts and permissions. See [User Management Guide](../jupyterhub/user-management.md).

### Resource Quotas

Set up resource usage tracking and limits. See [User Quota System](../jupyterhub/quota-system.md).

## Verification

After deployment, verify your installation:

```bash
# Check all pods are running
kubectl get pods -n jupyterhub

# Check services
kubectl get svc -n jupyterhub

# Access JupyterHub
# For NodePort: http://<node-ip>:30890
# For Domain: https://<your-domain>
```

## Troubleshooting

### Common Issues

1. **Pods not starting**: Check resource availability
   ```bash
   kubectl describe pod <pod-name> -n jupyterhub
   ```

2. **Image pull errors**: Verify image availability and pull secrets
   ```bash
   kubectl get events -n jupyterhub
   ```

3. **Connection refused**: Check service and ingress configuration
   ```bash
   kubectl get svc,ingress -n jupyterhub
   ```

## Next Steps

- Configure [Authentication](../jupyterhub/authentication-guide.md)
- Set up [User Management](../jupyterhub/user-management.md)
- Review [Admin Manual](../user-guide/admin-manual.md)

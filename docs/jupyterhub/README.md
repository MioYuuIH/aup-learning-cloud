<!-- Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.  Portions of this notebook consist of AI-generated content. -->
<!--
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-->

# JupyterHub Configuration Guide

## Documentation

- [Authentication Guide](./authentication-guide.md) - Setup GitHub OAuth and native authentication
- [User Management Guide](./user-management.md) - Batch user operations with scripts
- [User Quota System](./quota-system.md) - Resource usage tracking and quota management
- [GitHub OAuth Setup](./How_to_Setup_GitHub_OAuth.md) - Step-by-step OAuth configuration

---

## Configuration Files Overview

The Helm chart uses a layered configuration approach:

| File | Purpose |
|------|---------|
| `runtime/jupyterhub/values.yaml` | Chart defaults (accelerators, resources, teams, quota settings) |
| `runtime/values.yaml` | Deployment overrides (environment-specific settings) |
| `runtime/values.local.yaml` | Local development overrides (gitignored) |

### Helm Merge Behavior

- **Maps/Objects**: Deep merge (new keys added, same keys override)
- **Arrays/Lists**: Complete replacement

Deploy with:
```bash
# Production
helm upgrade jupyterhub ./jupyterhub -n jupyterhub -f values.yaml

# Local development
helm upgrade jupyterhub ./jupyterhub -n jupyterhub -f values.yaml -f values.local.yaml
```

---

## Custom Configuration

All custom settings are under the `custom` section. Chart defaults are in `runtime/jupyterhub/values.yaml`.

### Authentication Mode

```yaml
custom:
  authMode: "auto-login"  # auto-login | dummy | github | multi
```

| Mode | Description |
|------|-------------|
| `auto-login` | No credentials, auto-login as 'student' (single-node dev) |
| `dummy` | Accept any username/password (testing) |
| `github` | GitHub OAuth only |
| `multi` | GitHub OAuth + Local accounts |

### Admin User Auto-Creation

```yaml
custom:
  adminUser:
    enabled: true  # Generate admin credentials on install
```

When enabled, credentials are stored in a Kubernetes secret:
```bash
# Get admin password
kubectl -n jupyterhub get secret jupyterhub-admin-credentials \
  -o jsonpath='{.data.admin-password}' | base64 -d

# Get API token
kubectl -n jupyterhub get secret jupyterhub-admin-credentials \
  -o jsonpath='{.data.api-token}' | base64 -d
```

### Accelerators (GPU/NPU)

Define available hardware accelerators:

```yaml
custom:
  accelerators:
    phx:
      displayName: "AMD Radeon 780M (Phoenix Point iGPU)"
      description: "RDNA 3.0 (gfx1103) | Compute Units 12 | 4GB LPDDR5X"
      nodeSelector:
        node-type: phx
      env:
        HSA_OVERRIDE_GFX_VERSION: "11.0.0"
      quotaRate: 2
    my-custom-gpu:
      displayName: "My Custom GPU"
      nodeSelector:
        node-type: my-gpu
      quotaRate: 3
```

### Resources (Images & Requirements)

Define container images and resource requirements:

```yaml
custom:
  resources:
    images:
      cpu: "ghcr.io/amdresearch/auplc-default:latest"
      Course-CV: "ghcr.io/amdresearch/auplc-cv:latest"
      my-course: "my-registry/my-image:latest"

    requirements:
      cpu:
        cpu: "2"
        memory: "4Gi"
        memory_limit: "6Gi"
      Course-CV:
        cpu: "4"
        memory: "16Gi"
        memory_limit: "24Gi"
        amd.com/gpu: "1"
      my-course:
        cpu: "4"
        memory: "8Gi"
```

### Teams Mapping

Map teams to allowed resources:

```yaml
custom:
  teams:
    mapping:
      cpu:
        - cpu
      gpu:
        - Course-CV
        - Course-DL
      native-users:
        - cpu
        - Course-CV
```

**Note**: Arrays are completely replaced when overriding. If you override `teams.mapping.gpu`, the entire list is replaced, not merged.

### Quota System

```yaml
custom:
  quota:
    enabled: null        # null = auto-detect based on authMode
    cpuRate: 1           # Quota rate for CPU-only containers
    minimumToStart: 10   # Minimum quota to start a container
    defaultQuota: 0      # Default quota for new users

    refreshRules:
      daily-topup:
        enabled: true
        schedule: "0 0 * * *"
        action: add
        amount: 100
        maxBalance: 500
        targets:
          includeUnlimited: false
          balanceBelow: 400
```

See [quota-system.md](./quota-system.md) for detailed documentation.

---

## Hub Configuration

### Hub Image

```yaml
hub:
  image:
    name: ghcr.io/amdresearch/auplc-hub
    tag: latest
    pullPolicy: IfNotPresent
```

### Login Page Announcement

```yaml
hub:
  extraFiles:
    announcement.txt:
      mountPath: /usr/local/share/jupyterhub/static/announcement.txt
      stringData: |
        <div class="announcement-box" style="padding: 1em; border: 1px solid #ccc;">
          <h3>Welcome!</h3>
          <p>Your announcement here.</p>
        </div>
```

### GitHub OAuth

```yaml
hub:
  config:
    GitHubOAuthenticator:
      oauth_callback_url: "https://<Your.domain>/hub/github/oauth_callback"
      client_id: "YOUR_CLIENT_ID"
      client_secret: "YOUR_CLIENT_SECRET"
      allowed_organizations:
        - YOUR-ORG-NAME
      scope:
        - read:user
        - read:org
```

See [How_to_Setup_GitHub_OAuth.md](./How_to_Setup_GitHub_OAuth.md) for setup instructions.

---

## Network Settings

### NodePort Access

```yaml
proxy:
  service:
    type: NodePort
    nodePorts:
      http: 30890

ingress:
  enabled: false
```

Access via `http://<node-ip>:30890`

### Domain Access with Ingress

```yaml
proxy:
  service:
    type: ClusterIP

ingress:
  enabled: true
  ingressClassName: traefik
  hosts:
    - your.domain.com
  tls:
    - hosts:
        - your.domain.com
      secretName: jupyter-tls-cert
```

---

## Storage Settings

### NFS Storage (Production)

```yaml
hub:
  db:
    pvc:
      storageClassName: nfs-client

singleuser:
  storage:
    dynamic:
      storageClass: nfs-client
```

See [deploy/k8s/nfs-provisioner](../../deploy/k8s/nfs-provisioner) for NFS setup.

### Local Storage (Development)

```yaml
hub:
  db:
    pvc:
      storageClassName: hostpath

singleuser:
  storage:
    dynamic:
      storageClass: hostpath
```

---

## PrePuller Settings

Pre-download images to all nodes for faster container startup:

```yaml
prePuller:
  hook:
    enabled: true
  continuous:
    enabled: true
  extraImages:
    aup-cpu-notebook:
      name: ghcr.io/amdresearch/auplc-default
      tag: latest
```

For faster deployment (images pulled on-demand):

```yaml
prePuller:
  hook:
    enabled: false
  continuous:
    enabled: false
```

---

## Applying Changes

After modifying configuration:

```bash
helm upgrade jupyterhub ./jupyterhub -n jupyterhub -f values.yaml
```

Or use the helper script:

```bash
./scripts/helm_upgrade.bash
```

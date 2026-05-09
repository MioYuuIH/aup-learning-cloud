<!-- Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved. -->
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

# Showroom Airgap Deployment

This guide describes an exhibition cabinet deployment that is prepared while
the network is available and can keep running when the venue has no internet
access.

## Target Topology

```text
Venue network
        |
      WAN
[Cabinet Wi-Fi router/AP]
  LAN: 10.88.0.1/24
  DHCP/DNS/NAT: visitors, temporary devices, and internet egress
        |
[Cabinet switch]
        |
        +-- 10.88.0.10  master workstation
        |                k3s server
        |                JupyterHub
        |                host-level Zot registry
        |                Cloudflare tunnel when internet is available
        |                local operational data
        |
        +-- 10.88.0.20+ compute workers
                         k3s agent only
                         add/remove between demos
```

The cabinet machines are compute-only workers. Do not run the control plane,
Zot, Cloudflare tunnel, Hub database, or other required state on a removable
compute node.

The recommended first deployment keeps routing simple: the cabinet router/AP
owns DHCP, DNS forwarding, the default gateway, and NAT. The master workstation
does not act as a software router.

## Addressing Plan

| Address | Purpose |
| --- | --- |
| `10.88.0.1` | Cabinet router/AP LAN gateway |
| `10.88.0.10` | Fixed master workstation |
| `10.88.0.20-10.88.0.80` | Compute workers, preferably DHCP reservations |
| `10.88.0.100-10.88.0.199` | Visitor and temporary-device DHCP range |

Configure the cabinet router/AP with:

```text
LAN IP:        10.88.0.1
Subnet mask:   255.255.255.0
DHCP:          enabled
DHCP pool:     10.88.0.100-10.88.0.199
Gateway:       10.88.0.1
DNS server:    10.88.0.1
WAN:           DHCP from the venue or company network
```

Use DHCP reservations on the cabinet router/AP when possible:

```text
auplc-master  -> 10.88.0.10
compute-01    -> 10.88.0.20
compute-02    -> 10.88.0.21
compute-03    -> 10.88.0.22
```

With reservations, the Ubuntu hosts can keep `dhcp4: true` and still receive
stable addresses. If the router/AP does not support reservations, configure
static IPs on each Ubuntu host instead. The network interface name in the
examples below is `enp1s0`; replace it with the actual interface connected to
the cabinet switch.

Example master workstation netplan:

```yaml
network:
  version: 2
  ethernets:
    enp1s0:
      dhcp4: false
      addresses:
        - 10.88.0.10/24
      routes:
        - to: default
          via: 10.88.0.1
      nameservers:
        addresses:
          - 10.88.0.1
          - 1.1.1.1
```

Example compute worker netplan:

```yaml
network:
  version: 2
  ethernets:
    enp1s0:
      dhcp4: false
      addresses:
        - 10.88.0.20/24
      routes:
        - to: default
          via: 10.88.0.1
      nameservers:
        addresses:
          - 10.88.0.1
          - 1.1.1.1
```

Local entrypoint:

```text
http://10.88.0.10:30890
```

Optional local DNS entry on the router/AP:

```text
aup.local -> 10.88.0.10
```

Then visitors can open `http://aup.local` if the router/AP supports local DNS.
Otherwise, use `http://10.88.0.10:30890` directly.

Online entrypoint when the venue network works:

```text
https://<YOUR-SHOWROOM-DOMAIN>
  -> Cloudflare tunnel
  -> http://10.88.0.10:30890
```

## Online Preparation Phase

Run this phase before moving the cabinet to the exhibition area.

1. Configure the router/AP LAN as `10.88.0.1/24`.
2. Configure the router/AP DHCP pool as `10.88.0.100-10.88.0.199`.
3. Add DHCP reservations for the master and compute workers when supported.
4. Configure the master workstation as `10.88.0.10`.
5. Configure compute workers as `10.88.0.20+`.
6. Install Zot on the master workstation as a host-level service.
7. Copy `deploy/airgap/zot/config.yaml` to `/etc/zot/config.yaml`.
8. Copy `deploy/airgap/zot/zot.service` to `/etc/systemd/system/zot.service`.
9. Start Zot:

   ```bash
   sudo mkdir -p /etc/zot /var/lib/auplc/zot
   sudo systemctl daemon-reload
   sudo systemctl enable --now zot
   curl http://10.88.0.10:5000/v2/_catalog
   ```

10. Copy `deploy/airgap/k3s/registries.yaml` to every node at
   `/etc/rancher/k3s/registries.yaml` before starting k3s.
11. Preload all required images into Zot under the prefixed paths used by
   `registries.yaml`.
12. Install k3s server on the master workstation.
13. Join compute workers as k3s agents.
14. Label each compute worker:

    ```bash
    kubectl label node <node-name> auplc.node-role=compute --overwrite
    ```

15. Deploy the online overlay if GitHub OAuth and Cloudflare are ready:

    ```bash
    cd runtime
    helm upgrade --install jupyterhub ./chart -n jupyterhub --create-namespace \
      -f values.yaml -f values.showroom-online.yaml
    ```

16. Deploy the offline overlay for a full no-internet rehearsal:

    ```bash
    cd runtime
    helm upgrade --install jupyterhub ./chart -n jupyterhub --create-namespace \
      -f values.yaml -f values.showroom-offline.yaml
    ```

17. Disconnect the WAN side and verify that the local entrypoint and core
    courses still start.

## Ansible Cluster Bring-up

Use Ansible after the cabinet LAN, host-level Zot, and the node IPs are ready.
The example inventory is `deploy/ansible/inventory.showroom-airgap.yml.example`.

1. Copy the example inventory and edit it for the actual node count, hostnames,
   interface names, and token:

   ```bash
   cd deploy/ansible
   cp inventory.showroom-airgap.yml.example inventory.showroom-airgap.yml
   vim inventory.showroom-airgap.yml
   ```

2. Confirm SSH access from the Ansible controller to every node:

   ```bash
   ansible -i inventory.showroom-airgap.yml all -m ping
   ```

3. Replace `flannel-iface: enp1s0` in `server_config_yaml` if the master
   workstation uses a different switch-facing interface. Check with:

   ```bash
   ip -br link
   ip route get 10.88.0.1
   ```

4. If you are using k3s airgap artifacts, copy them to every node at the same
   path and uncomment `airgap_dir` in the inventory. If the preparation network
   is still available and Zot already contains every required image, you can
   leave `airgap_dir` commented for the first bring-up.

5. Run the base preparation playbook:

   ```bash
   sudo ansible-playbook -i inventory.showroom-airgap.yml playbooks/pb-base.yml
   ```

6. Install the k3s cluster:

   ```bash
   sudo ansible-playbook -i inventory.showroom-airgap.yml playbooks/pb-k3s-site.yml
   ```

   The inventory writes `/etc/rancher/k3s/registries.yaml` on all nodes, points
   containerd at `http://10.88.0.10:5000`, and labels agent nodes with
   `auplc.node-role=compute`.

7. Install ROCm on the compute nodes if required for the course images:

   ```bash
   sudo ansible-playbook -i inventory.showroom-airgap.yml playbooks/pb-rocm.yml
   ```

8. Verify the cluster from the master workstation:

   ```bash
   kubectl get nodes -o wide
   kubectl get nodes --show-labels
   ```

9. If a worker was added manually or missed the label, fix it before deploying
   the showroom overlays:

   ```bash
   kubectl label node <node-name> auplc.node-role=compute --overwrite
   ```

## Zot Image Preload Checklist

Zot solves container-image availability. It does not automatically make pip
packages, Hugging Face models, or notebook datasets available offline.

Preload at least these image families:

```text
registry.k8s.io/*                 k3s and Kubernetes support images
quay.io/jupyterhub/*              JupyterHub chart support images
ghcr.io/amdresearch/auplc-hub     Hub image
ghcr.io/amdresearch/auplc-default Base CPU image
ghcr.io/amdresearch/auplc-base    Base GPU image
ghcr.io/amdresearch/auplc-cv      CV course image
ghcr.io/amdresearch/auplc-dl      DL course image
ghcr.io/amdresearch/auplc-llm     LLM course image
ghcr.io/amdresearch/auplc-physim  PhySim course image
```

Example target names in Zot:

```text
10.88.0.10:5000/ghcr.io/amdresearch/auplc-hub:latest
10.88.0.10:5000/ghcr.io/amdresearch/auplc-cv:latest
10.88.0.10:5000/registry.k8s.io/pause:3.10.1
```

Use your preferred registry tooling during the online preparation phase to copy
from the public registries into the Zot endpoint. Verify that a worker can pull
from Zot before the exhibition network is disconnected.

## Authentication Modes

Use two overlays instead of editing one file during the event.

### Online Mode

`runtime/values.showroom-online.yaml` enables `custom.authMode: "multi"` so the
same login page offers GitHub OAuth and native accounts. Use this mode when the
Cloudflare tunnel and GitHub OAuth callback URL are working.

Before deploying online mode, replace these values:

```text
<YOUR-SHOWROOM-DOMAIN>
<YOUR-GITHUB-ORG>
<GITHUB-OAUTH-CLIENT-ID>
<GITHUB-OAUTH-CLIENT-SECRET>
```

### Offline Mode

`runtime/values.showroom-offline.yaml` keeps `custom.authMode: "multi"`, but
the native login path is the expected path. The overlay pre-creates these local
JupyterHub users:

```text
admin
demo01-demo12
```

Set their passwords before the exhibition through the Admin UI or the existing
user-management workflow. Do not use `auto-login` for multi-user exhibitions;
all visitors would share one JupyterHub user and one server.

## Compute Worker Operations

Workers may be added or removed between demos. Avoid unplugging a worker while
visitors are actively using notebooks on it.

Join a worker:

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://10.88.0.10:6443 \
  K3S_TOKEN=<cluster-token> \
  sh -

kubectl label node <node-name> auplc.node-role=compute --overwrite
```

Remove a worker during a break:

```bash
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
kubectl delete node <node-name>
```

If a worker is unplugged unexpectedly, remove the stale node before the next
demo:

```bash
kubectl delete node <node-name>
```

## Offline Course Assets

Container images are only one layer of the offline plan. Validate these course
assets separately:

| Course | Offline risk |
| --- | --- |
| CV | Datasets, YOLO/SAM weights, and runtime pip installs |
| DL | FashionMNIST, MNIST, CIFAR, sklearn datasets, and raw GitHub CSV files |
| LLM | Hugging Face models, tokenizers, datasets, and runtime pip installs |
| PhySim | Appears closest to self-contained, but still needs a disconnected test run |

The first showroom pass does not rewrite course notebooks to local asset paths.
Treat each course as offline-ready only after a disconnected end-to-end run.

## Validation Checklist

Before the exhibition:

- `curl http://10.88.0.10:5000/v2/_catalog` returns from the master workstation.
- `kubectl get nodes` shows the master and all expected compute workers ready.
- Every compute worker has `auplc.node-role=compute`.
- `helm template` succeeds with both showroom overlays.
- `http://10.88.0.10:30890` works from the cabinet Wi-Fi.
- GitHub OAuth works through the Cloudflare domain in online mode.
- Native `demo01-demo12` users can log in in offline mode.
- Course images pull from Zot after disconnecting the WAN side.
- The selected demo notebooks run without internet for the parts you plan to show.

## Known Limits

- Zot must start before k3s if k3s depends on mirrored system images.
- The offline overlay still renders a GitHub login option because the current
  multi-auth mode always includes GitHub plus native accounts. Use native login
  when disconnected.
- The default `local-path` storage is node-local. If user data must survive
  worker removal, add a dedicated shared-storage design before using this in a
  long-running classroom.
- Cloudflare tunnel and GitHub OAuth are online enhancements, not offline
  dependencies.

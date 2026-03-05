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


# Kubernetes Components

Kubernetes resource configurations for AUP Learning Cloud cluster.

For full instructions, see [Multi-Node Cluster Deployment](https://amdresearch.github.io/aup-learning-cloud/installation/multi-node.html).

## Contents

- `nfs-provisioner/` — NFS dynamic provisioner Helm values

## Quick Reference

```bash
# Deploy AMD GPU device plugin
kubectl create -f https://raw.githubusercontent.com/ROCm/k8s-device-plugin/master/k8s-ds-amdgpu-dp.yaml

# Label nodes by GPU type
kubectl label nodes <NODE_NAME> node-type=strix-halo

# Verify GPU detection
kubectl describe node <node-name> | grep amd.com/gpu
```

### Node Label Mapping

| node-type     | Hardware |
|---------------|----------|
| `phx`         | Phoenix (AMD 7940HS / 7640HS) |
| `dgpu`        | Discrete GPU (Radeon 9070XT, W9700) |
| `strix`       | Strix (AMD AI 370 / 350) |
| `strix-halo`  | Strix-Halo (AMD AI MAX 395) |

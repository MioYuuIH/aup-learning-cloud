# Showroom Airgap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-pass showroom deployment baseline that can be prepared online and run offline from a fixed master workstation with flexible compute workers.

**Architecture:** The master workstation owns all stateful infrastructure: k3s server, Hub, host-level Zot, Cloudflare tunnel, and local storage. Compute machines join only as k3s agents and may be added or removed between demos. The repository changes are configuration examples and SOP documentation; course image and notebook rewrites are intentionally left for later runtime validation.

**Tech Stack:** Helm values overlays, k3s containerd registry mirrors, Zot registry, JupyterHub multi authentication, Markdown deployment documentation.

---

### Task 1: Add showroom Helm overlays

**Files:**
- Create: `runtime/values.showroom-online.yaml`
- Create: `runtime/values.showroom-offline.yaml`

- [ ] **Step 1: Create the online overlay**

Add a values file that keeps NodePort access, enables GitHub OAuth plus native fallback, enables external HTTPS cookie handling, and pre-pulls course images through the local registry mirror.

- [ ] **Step 2: Create the offline overlay**

Add a values file that keeps the same local NodePort entrypoint and demo user pool but documents native-account-only use when GitHub and Cloudflare are unavailable.

- [ ] **Step 3: Validate Helm rendering**

Run: `helm template jupyterhub runtime/chart -n jupyterhub -f runtime/values.yaml -f runtime/values.showroom-online.yaml >/tmp/auplc-showroom-online.yaml`

Run: `helm template jupyterhub runtime/chart -n jupyterhub -f runtime/values.yaml -f runtime/values.showroom-offline.yaml >/tmp/auplc-showroom-offline.yaml`

Expected: both commands exit 0.

### Task 2: Add host-level Zot and k3s registry examples

**Files:**
- Create: `deploy/airgap/zot/config.yaml`
- Create: `deploy/airgap/zot/zot.service`
- Create: `deploy/airgap/k3s/registries.yaml`

- [ ] **Step 1: Add Zot config**

Create a minimal host-level Zot configuration listening on the master workstation at port 5000 with data under `/var/lib/auplc/zot`.

- [ ] **Step 2: Add systemd unit**

Create a unit file that starts `/usr/local/bin/zot serve /etc/zot/config.yaml` before k3s uses the registry mirror.

- [ ] **Step 3: Add k3s registry mirror example**

Create a `registries.yaml` example that maps `docker.io`, `ghcr.io`, `quay.io`, and `registry.k8s.io` to `http://10.88.0.10:5000/<registry>`.

### Task 3: Add showroom airgap SOP

**Files:**
- Create: `deploy/docs/showroom-airgap.md`
- Modify: `deploy/README.md`

- [ ] **Step 1: Document topology**

Describe the cabinet Wi-Fi router, fixed master workstation, compute-only worker pool, local NodePort entrypoint, and optional Cloudflare tunnel entrypoint.

- [ ] **Step 2: Document preparation and runtime flow**

Split the SOP into online preparation, offline runtime, Zot preload, authentication mode, worker join/remove, validation, and known limits.

- [ ] **Step 3: Link the SOP from deployment README**

Add the showroom guide to the deployment documentation index.

### Task 4: Validate the changes

**Files:**
- Validate all YAML files created above.
- Validate Markdown renders as plain text with no broken local paths.

- [ ] **Step 1: Run YAML validation**

Run a parser or Helm render command against all new YAML files.

- [ ] **Step 2: Review git diff**

Run: `GIT_MASTER=1 git diff --stat`

Expected: only the planned docs/config files are changed.

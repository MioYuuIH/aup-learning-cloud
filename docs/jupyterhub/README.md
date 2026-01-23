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



# How to setup [runtime/values.yaml](../../runtime/values.yaml)

## PrePuller settings

Example:
```yml
prePuller:
  extraImages:
    aup-cpu-notebook:
      name: ghcr.io/amdresearch/aup-cpu-notebook
      tag: v1.0
    ...

    #for frontpage
    aup-jupyterhub-hub:
      name: ghcr.io/amdresearch/aup-jupyterhub-hub
      tag: v1.3.5-multilogin
```

It is recommended to include as many images as you plan to deploy. This section ensures that all images are pre-downloaded on each node, preventing delays during container startup due to image downloads.

## Network settings

Two access methods are supported:

1. NodePort access via `<ip>:<port>` (port > 30000)
2. Domain access (Default) `<Your.domain>`

Example NodePort setup. With this configuration, ingress should be disabled.

```yml
proxy:
  service:
    type: NodePort
    nodePorts:
      http: 30890
  chp:
    networkPolicy:
      enabled: false
ingress:
  enabled: false
  # Explicitly set the ingress class to traefik
  ingressClassName: traefik
  hosts:
  tls:
    - hosts:
      # Let K3s/Traefik auto-generate certificates with Let's Encrypt
      secretName: 
```

Example Domain setup. Note that you should obtain the domain from your IT department.
```yml
proxy:
  service:
    type: ClusterIP
# Add Ingress configuration specifically for K3s
ingress:
  enabled: true
  # Explicitly set the ingress class to traefik
  ingressClassName: traefik
  hosts:
    - <Your.domain>
  tls:
    - hosts:
        - <Your.domain>
      # Let K3s/Traefik auto-generate certificates with Let's Encrypt
      secretName: jupyter-tls-cert
```

## Hub image setup

Update this section with your built Docker image.
```yml
  image:
    name: ghcr.io/amdresearch/aup-jupyterhub-hub
    tag: v1.3.5-multilogin
    pullPolicy: IfNotPresent
    pullSecrets:
      - github-registry-secret
```

## Update Announcement on login page

Edit the stringData section with HTML content to display announcements on the login page.
```yml
  extraFiles:
    announcement.txt:
      mountPath: /usr/local/share/jupyterhub/static/announcement.txt
      stringData: |
          <div class="announcement-box" style="padding: 1em; border: 1px solid #ccc; border-radius: 6px; background-color: #f8f8f8;">
          <h3>Welcome to AUP Remote Lab!</h3>
          <p>This is a <strong>dynamic announcement</strong>.</p>
          <p>My location is on <code>runtime/values.yaml</code></p>
          <p>You can edit this via <strong>ConfigMap</strong> without rebuilding the image.</p>
          </div>
```

## Provide Github OAuth Credentials

Refer to this [article](https://discourse.jupyter.org/t/github-authentication-for-organization-teams/1209/4) for information on setting up GitHub OAuth with GitHub Organizations. 

Fill in this section with credentials from your organization's OAuth app. Please note that the `oauth_callback_url` should match your actual deployment. For a simple GitHub OAuth-only solution, use `https://<Your.domain>/hub/oauth_callback`. Since we are using `MultiAuth`, we need `github` to identify that we are using `GitHubOAuth`.
```yml
    GitHubOAuthenticator:
      oauth_callback_url: "https://<Your.domain>/hub/github/oauth_callback"
      client_id: "AAAA"
      client_secret: "BBB"
      allowed_organizations:
        - <YOUR-ORG-NAME>
      scope:
        - read:user
        - read:org
```

## NFS Storage setting

Refer to [Cluster-NFS-Setting](../../deploy/k8s/nfs-provisioner).
```yml
  storage:
    dynamic:
      storageClass: nfs-client

```

## After

You should run [`helm upgrade`](../../scripts/helm_upgrade.bash) to apply the changes.

# How to setup `jupyterhub_config.yaml`

## Change Image Settings

Find `RESOURCE_IMAGES` in `jupyterhub_config.py` and change the image settings.
```python
RESOURCE_IMAGES = {
        "cpu": "ghcr.io/amdresearch/aup-cpu-notebook:v1.0",
#    "mlir-aie": "ghcr.io/amdresearch/aup-mliraie-notebook:v1.0",
    "Course-CV": "ghcr.io/amdresearch/aup-course-cv:v1.3.6",
}
```
## Change Image Resource Limitations
Find `RESOURCE_REQUIREMENTS` in `jupyterhub_config.py` and change the resource limitations.
```python
RESOURCE_REQUIREMENTS = {"Course-CV":  {"cpu": "4", "memory": "16Gi", "memory_limit": "24Gi", "amd.com/gpu": "1"},
    "Course-DL":  {"cpu": "4", "memory": "16Gi", "memory_limit": "24Gi", "amd.com/gpu": "1"},}
```

For images using NPU, you need to add `"amd.com/npu": "1"` to the resource requirements. And explicitly set Special configuration for NPU resources.

```python
        if resource_type in ["Tutorial-NPU-Resnet", "mlir-aie", "ROSCON2025-GPU",  "ROSCON2025-NPU"]:
            # Apply NPU security configuration
            for key, value in NPU_SECURITY_CONFIG.items():
                if hasattr(self, key):
                    setattr(self, key, value)
```

## Change Node Preference 
Find `NODE_SELECTOR_MAPPING` in `jupyterhub_config.py` and change the node preference.
```python

NODE_SELECTOR_MAPPING = {
    # GPU nodes
    "phx": {"node-type": "phx"},
    "strix": {"node-type": "strix"},
    "strix-halo": {"node-type": "strix-halo"},
    "dgpu": {"node-type": "dgpu"},
    # NPU nodes (Note: NPU's strix uses different labels)
    "strix-npu": {"type": "strix"}
}
```

## Change Team Resource Limitations
Find `TEAM_RESOURCE_MAPPING` in `jupyterhub_config.py` and change the team resource limitations.

```python
TEAM_RESOURCE_MAPPING = {
    "cpu": ["cpu"],
    "gpu": ["Course-CV","Course-DL","Course-LLM", "Tutorial-HIP-Intro","Tutorial-LLM-Lemonade","Tutorial-LLM-Ollama", 
            "ROSCON2025-GPU", "ROSCON2025-NPU", "ROSCON2025-DIGIT"],
    "npu": ["Tutorial-NPU-Resnet", 
            # "mlir-aie"
            ],}
```
## Change Local Account Credentials

Find this sections in `jupyterhub_config.py` and change the local account credentials.
```python
AUP_USERS = [f"AUP{i:02d}" for i in range(1, 51)]
TEST_USERS = [f"TEST{i:02d}" for i in range(1, 51)]
ROSCON_USERS = [f"ROSCON{i:02d}" for i in range(1, 51)]


AUP_PASSWORD = "AUP"        
TEST_PASSWORD = "TEST"       
ROSCON_PASSWORD = "ROSCON"     
ADMIN_PASSWORD = "AUP"
```

## Change Local Account Resource Settings

Find `get_user_teams` in `RemoteLabKubeSpawner`, change them respectively.

```python

if LOCAL_ACCOUNT_PREFIX_UPPER in username:
            print(f"[DEBUG] Enter local username checking: {username}")
            if "AUP" in username:
                print("[DEBUG] Matched AUP user group")
                return TEAM_RESOURCE_MAPPING["AUP"]
            elif "TEST" in username:
                print("[DEBUG] Matched TEST user group")
                return TEAM_RESOURCE_MAPPING["official"]
            elif "ROSCON" in username:
                print("[DEBUG] Matched ROSCON user group")
                return TEAM_RESOURCE_MAPPING["ROSCON"]
            return ["none"]
```

## Change Authentication Methods
Find `authenticator_class` in `jupyterhub_config.py` and change the authentication methods.

```python
# default, support multiple authentication methods: local & github
c.JupyterHub.spawner_class = RemoteLabKubeSpawner
# any password will work, suggested to use during testing, do check resource mapping.
c.JupyterHub.spawner_class = "dummy"
# only allow GitHub OAuth, do check team membership and callback link.
c.JupyterHub.authenticator_class = CustomGitHubOAuthenticator

```

About how to setup other authenticator methods, do check `CustomMultiAuthenticator` and set up `url_prefix`.

```python
c.MultiAuthenticator.authenticators = [
    {
        "authenticator_class": CustomGitHubOAuthenticator,
        "url_prefix": "/github",
    },
    {
        "authenticator_class": SimpleGroupAuthenticator,
        "url_prefix": "/local",
    },
]
```

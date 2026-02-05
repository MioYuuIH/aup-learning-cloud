#!/usr/bin/env bash

# Modifications Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Portions of this file consist of AI-generated content.
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

set -euo pipefail

# k3s image dir
K3S_IMAGES_DIR="/var/lib/rancher/k3s/agent/images"
K3S_REGISTRIES_FILE="/etc/rancher/k3s/registries.yaml"

# Registry mirror prefix (set via environment variable)
# Example: MIRROR_PREFIX="m.daocloud.io" will transform:
#   quay.io/jupyterhub/k8s-hub:4.1.0 -> m.daocloud.io/quay.io/jupyterhub/k8s-hub:4.1.0
MIRROR_PREFIX="${MIRROR_PREFIX:-}"

# Package manager mirrors (set via environment variables)
MIRROR_PIP="${MIRROR_PIP:-}"
MIRROR_NPM="${MIRROR_NPM:-}"

# Custom images (built locally)
CUSTOM_IMAGES=(
    "ghcr.io/amdresearch/auplc-hub:latest"
    "ghcr.io/amdresearch/auplc-default:latest"
    "ghcr.io/amdresearch/auplc-cv:latest"
    "ghcr.io/amdresearch/auplc-dl:latest"
    "ghcr.io/amdresearch/auplc-llm:latest"
)

# External images required by JupyterHub (for offline deployment)
EXTERNAL_IMAGES=(
    # JupyterHub core components
    "quay.io/jupyterhub/k8s-hub:4.1.0"
    "quay.io/jupyterhub/configurable-http-proxy:4.6.3"
    "quay.io/jupyterhub/k8s-secret-sync:4.1.0"
    "quay.io/jupyterhub/k8s-network-tools:4.1.0"
    "quay.io/jupyterhub/k8s-image-awaiter:4.1.0"
    "quay.io/jupyterhub/k8s-singleuser-sample:4.1.0"
    # Kubernetes components
    "registry.k8s.io/kube-scheduler:v1.30.8"
    "registry.k8s.io/pause:3.10"
    # Traefik proxy
    "traefik:v3.3.1"
    # Utility images
    "curlimages/curl:8.5.0"
    # Base images for Docker build
    "node:20-alpine"
    "ubuntu:24.04"
    "quay.io/jupyter/base-notebook"
)

# Combined list for backward compatibility
IMAGES=("${CUSTOM_IMAGES[@]}")

function check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "Error: This script must be run as root." >&2
        exit 1
    fi
}

function install_tools() {
    echo "Checking/Installing tools (may require sudo)..."

    if ! command -v helm &> /dev/null; then
        echo "Installing Helm..."
        wget https://get.helm.sh/helm-v3.17.2-linux-amd64.tar.gz -O /tmp/helm-linux-amd64.tar.gz
        tar -zxvf /tmp/helm-linux-amd64.tar.gz -C /tmp
        sudo mv /tmp/linux-amd64/helm /usr/local/bin/helm
        rm /tmp/helm-linux-amd64.tar.gz
        rm -rf /tmp/linux-amd64
    fi

    if ! command -v k9s &> /dev/null; then
        echo "Installing K9s..."
        wget https://github.com/derailed/k9s/releases/latest/download/k9s_linux_amd64.deb -O /tmp/k9s_linux_amd64.deb
        sudo apt install /tmp/k9s_linux_amd64.deb -y
        rm /tmp/k9s_linux_amd64.deb
    fi
}

function configure_registry_mirrors() {
    # Configure K3s registry mirrors using MIRROR_PREFIX
    # This must be done BEFORE k3s starts

    if [[ -z "${MIRROR_PREFIX}" ]]; then
        echo "No registry mirror configured. Using default registries."
        return 0
    fi

    echo "Configuring registry mirrors with prefix: ${MIRROR_PREFIX}"
    sudo mkdir -p "$(dirname "${K3S_REGISTRIES_FILE}")"

    # Configure mirrors for all registries using the prefix pattern
    local config="mirrors:
  docker.io:
    endpoint:
      - \"https://${MIRROR_PREFIX}/docker.io\"
  quay.io:
    endpoint:
      - \"https://${MIRROR_PREFIX}/quay.io\"
  registry.k8s.io:
    endpoint:
      - \"https://${MIRROR_PREFIX}/registry.k8s.io\"
  ghcr.io:
    endpoint:
      - \"https://${MIRROR_PREFIX}/ghcr.io\""

    echo "${config}" | sudo tee "${K3S_REGISTRIES_FILE}" > /dev/null
    echo "Registry mirrors configured at ${K3S_REGISTRIES_FILE}"
}

function install_k3s_single_node() {
    echo "Starting K3s installation..."

    # Configure registry mirrors before starting k3s
    configure_registry_mirrors

    curl -sfL https://get.k3s.io | sudo K3S_KUBECONFIG_MODE="644" sh -

    echo "Configuring kubeconfig for user: $(whoami)"
    mkdir -p "$HOME/.kube"
    sudo cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
    sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"
}

function remove_k3s() {
    local uninstall_script="/usr/local/bin/k3s-uninstall.sh"

    if [[ -f "$uninstall_script" ]]; then
        echo "Removing K3s (requires sudo)..."
        sudo "$uninstall_script"
        echo "K3s removed successfully."
    else
        echo "K3s uninstall script not found at $uninstall_script. Is K3s installed?"
    fi

    if [[ -d "$HOME/.kube" ]]; then
        echo "Removing kubeconfig files from $HOME/.kube..."
        rm -rf "$HOME/.kube"
    fi

    if [ -n "${SUDO_USER:-}" ]; then
        local user_home
        user_home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        if [[ -d "$user_home/.kube" ]]; then
             echo "Removing kubeconfig for user: $SUDO_USER"
             sudo rm -rf "$user_home/.kube"
        fi
    fi

    echo "Removing K3S local data"
    sudo rm -rf /var/lib/rancher/k3s
}

function deploy_rocm_gpu_device_plugin() {
    echo "Deploying ROCm GPU device plugin..."

    if kubectl get ds/amdgpu-device-plugin-daemonset --namespace=kube-system &> /dev/null; then
        echo "ROCm GPU device plugin already exists."
        return 0
    fi

    kubectl create -f https://raw.githubusercontent.com/ROCm/k8s-device-plugin/master/k8s-ds-amdgpu-dp.yaml

    if ! kubectl wait --for=jsonpath='{.status.numberReady}'=1 --namespace=kube-system ds/amdgpu-device-plugin-daemonset --timeout=300s | grep "condition met"; then
        exit 1
    else
        echo "Successfully deployed ROCm GPU device plugin."
    fi
}

function deply_aup_learning_cloud_runtime() {
    echo "Deploying AUP Learning Cloud Runtime..."

    helm install jupyterhub ../runtime/jupyterhub  --namespace jupyterhub   --create-namespace   -f ../runtime/values.yaml

    echo "Waiting for JupyterHub deployments to be ready..."
    kubectl wait --namespace jupyterhub \
        --for=condition=available --timeout=600s \
        deployment/hub deployment/proxy deployment/user-scheduler

    # Label node (first version only detect strix-halo)
    kubectl label "$(kubectl get nodes -o name)" node-type=strix-halo --overwrite
}

function upgrade_aup_learning_cloud_runtime() {
    helm upgrade jupyterhub ../runtime/jupyterhub  --namespace jupyterhub   --create-namespace   -f ../runtime/values.yaml
}

function remove_aup_learning_cloud_runtime() {
    helm uninstall jupyterhub --namespace jupyterhub
}

function local_image_build() {
    if ! command -v docker &> /dev/null; then
        echo "Please install docker"
        exit 1
    fi

    echo "Building local images..."

    if [ ! -d "${K3S_IMAGES_DIR}" ]; then
        sudo mkdir -p "${K3S_IMAGES_DIR}"
    fi

    echo "Build & Copy Images to K3S image pool"

    # Pass IMAGES array and mirror settings to Makefile
    cd ../dockerfiles/ && make \
        K3S_IMAGES_DIR="${K3S_IMAGES_DIR}" \
        IMAGES="${IMAGES[*]}" \
        MIRROR_PREFIX="${MIRROR_PREFIX}" \
        MIRROR_PIP="${MIRROR_PIP}" \
        MIRROR_NPM="${MIRROR_NPM}"

    echo "-------------------------------------------"
}

function pull_external_images() {
    # Pull and save external images required for offline deployment
    # This ensures JupyterHub can run without internet access

    if ! command -v docker &> /dev/null; then
        echo "Please install docker"
        exit 1
    fi

    echo "==========================================="
    echo "Pulling external images for offline deployment..."
    if [[ -n "${MIRROR_PREFIX}" ]]; then
        echo "Using mirror prefix: ${MIRROR_PREFIX}"
    fi
    echo "==========================================="

    if [ ! -d "${K3S_IMAGES_DIR}" ]; then
        sudo mkdir -p "${K3S_IMAGES_DIR}"
    fi

    local failed_images=()

    for image in "${EXTERNAL_IMAGES[@]}"; do
        # Determine the full image path for pulling with mirror
        # Images without registry prefix are from docker.io
        local full_image="${image}"
        local first_segment="${image%%/*}"

        if [[ "${image}" == *"/"* ]]; then
            # Has slash - check if first segment looks like a registry (contains a dot)
            if [[ "${first_segment}" != *"."* ]]; then
                # No dot in first segment, it's docker.io (e.g., curlimages/curl)
                full_image="docker.io/${image}"
            fi
        else
            # No slash - it's an official docker image (e.g., traefik:v3.3.1)
            full_image="docker.io/library/${image}"
        fi

        # Apply mirror prefix if set
        local pull_image="${full_image}"
        if [[ -n "${MIRROR_PREFIX}" ]]; then
            pull_image="${MIRROR_PREFIX}/${full_image}"
        fi

        echo "-------------------------------------------"
        echo "Pulling: ${pull_image}"

        if docker pull "${pull_image}"; then
            # Tag to original name so K3s can use it
            if [[ "${pull_image}" != "${image}" ]]; then
                docker tag "${pull_image}" "${image}"
            fi

            # Also tag to mirror-prefixed name so Docker build with MIRROR_PREFIX can use local cache
            if [[ -n "${MIRROR_PREFIX}" && "${pull_image}" != "${MIRROR_PREFIX}/${full_image}" ]]; then
                docker tag "${pull_image}" "${MIRROR_PREFIX}/${full_image}"
            fi

            # Generate filename from original image name (replace / and : with -)
            local filename
            filename=$(echo "${image}" | sed 's/[\/:]/-/g').tar
            local out_path="${K3S_IMAGES_DIR}/${filename}"

            echo "Saving to: ${out_path}"
            if sudo docker save "${image}" -o "${out_path}"; then
                echo "Saved: ${image}"
            else
                echo "Failed to save: ${image}"
                failed_images+=("${image}")
            fi
        else
            echo "Failed to pull: ${pull_image}"
            failed_images+=("${image}")
        fi
    done

    echo "==========================================="
    if [ ${#failed_images[@]} -eq 0 ]; then
        echo "All external images pulled and saved successfully!"
    else
        echo "Failed images:"
        for img in "${failed_images[@]}"; do
            echo "  - ${img}"
        done
        echo "Warning: Some images failed. Deployment may require internet access."
    fi
    echo "==========================================="
}

function deploy_all_components() {
    install_tools
    install_k3s_single_node
    deploy_rocm_gpu_device_plugin
    pull_external_images
    local_image_build
    deply_aup_learning_cloud_runtime
}

function remove_all_components() {
    remove_aup_learning_cloud_runtime || true
    remove_k3s
}

function show_help() {
    cat << 'EOF'
Usage: ./single-node.sh <command>

Commands:
  install          Full installation (k3s + images + runtime)
  uninstall        Remove everything
  install-tools    Install helm and k9s
  install-runtime  Deploy JupyterHub runtime only
  remove-runtime   Remove JupyterHub runtime
  upgrade-runtime  Upgrade JupyterHub runtime
  build-images     Build custom images locally
  pull-images      Pull external images for offline use

Mirror Configuration:
  Set environment variables to use alternative mirrors.

  Container Registries:
    MIRROR_PREFIX   Registry mirror prefix (without https://)
                    Transforms: quay.io/image -> <prefix>/quay.io/image

  Package Managers:
    MIRROR_PIP      PyPI mirror URL
    MIRROR_NPM      npm registry URL

  Example:
    MIRROR_PREFIX="mirror.example.com" \
    MIRROR_PIP="https://pypi.example.com/simple" \
    ./single-node.sh install

EOF
}

if [[ $# -eq 0 ]]; then
    show_help
    exit 1
fi

case "$1" in
    install) deploy_all_components ;;
    uninstall) remove_all_components ;;
    install-tools) install_tools ;;
    install-runtime) deply_aup_learning_cloud_runtime ;;
    remove-runtime) remove_aup_learning_cloud_runtime ;;
    upgrade-runtime) upgrade_aup_learning_cloud_runtime ;;
    build-images) local_image_build ;;
    pull-images) pull_external_images ;;
    help|--help|-h) show_help ;;
    *) show_help; exit 1 ;;
esac

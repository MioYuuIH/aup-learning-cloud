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
# Docker images version
IMAGES=(
    "ghcr.io/amdresearch/auplc-hub:latest"
    "ghcr.io/amdresearch/auplc-default:latest"
    "ghcr.io/amdresearch/auplc-cv:latest"
    "ghcr.io/amdresearch/auplc-dl:latest"
    "ghcr.io/amdresearch/auplc-llm:latest"
)

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

function install_k3s_single_node() {
    echo "Starting K3s installation..."

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

    # Pass IMAGES array as space-separated string to Makefile
    cd ../dockerfiles/ && make K3S_IMAGES_DIR="${K3S_IMAGES_DIR}" IMAGES="${IMAGES[*]}"

    echo "-------------------------------------------"
}

function deploy_all_components() {
    install_tools
    install_k3s_single_node
    deploy_rocm_gpu_device_plugin
    local_image_build
    deply_aup_learning_cloud_runtime
}

function remove_all_components() {
    remove_aup_learning_cloud_runtime || true
    remove_k3s
}

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 {install|uninstall|install-tools|install-runtime|remove-runtime|upgrade-runtime|build-images}"
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
    *) echo "Usage: $0 {install|uninstall|install-tools|install-runtime|remove-runtime|upgrade-runtime|build-images}"; exit 1 ;;
esac

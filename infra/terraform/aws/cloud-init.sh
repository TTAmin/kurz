#!/bin/bash
# Installs k3s (with its bundled Traefik ingress on port 80) and Helm.
set -euo pipefail

curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--write-kubeconfig-mode 644" sh -
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

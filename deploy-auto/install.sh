#!/usr/bin/env bash
#
# Déploie l'agent de remédiation et son automatisation dans le cluster, dans
# l'ordre. À lancer depuis le dossier deploy-auto/ :
#
#   cd deploy-auto && ./install.sh
#
# Prérequis :
#   - kubectl configuré sur le bon cluster (export KUBECONFIG=...)
#   - l'image de l'agent construite et poussée (voir Dockerfile), et le champ
#     image: de agent/cronjob.yaml mis à jour en conséquence.
#   - Trivy Operator déjà déployé (via argocd/apps/02-trivy-operator.yaml).
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="security"

echo "[1/5] Namespace '${NAMESPACE}'..."
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

echo "[2/5] Argo CD (installé s'il est absent, dans le namespace argocd)..."
if ! kubectl get namespace argocd >/dev/null 2>&1; then
  kubectl create namespace argocd
  kubectl apply -n argocd \
    -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.3.12/manifests/install.yaml
  echo "      Attente du rollout d'argocd-server..."
  kubectl -n argocd rollout status deploy/argocd-server --timeout=300s
else
  echo "      argocd déjà présent, on ne réinstalle pas."
fi

echo "[3/5] RBAC de l'agent (ServiceAccount + lecture des rapports Trivy)..."
kubectl apply -f "${HERE}/rbac/rbac.yaml"

echo "[4/5] Secret des tokens (créé HORS Git)..."
# Le Secret n'est volontairement PAS dans cronjob.yaml : on ne committe jamais
# de token. On vérifie qu'il a bien été créé à la main avant de poser le CronJob.
if ! kubectl -n "${NAMESPACE}" get secret remediation-agent-secrets >/dev/null 2>&1; then
  echo "      ✗ Secret 'remediation-agent-secrets' absent du namespace ${NAMESPACE}."
  echo "        Crée-le d'abord (les tokens ne doivent jamais aller dans Git) :"
  echo
  echo "          kubectl create secret generic remediation-agent-secrets -n ${NAMESPACE} \\"
  echo "            --from-literal=OVH_AI_ENDPOINTS_ACCESS_TOKEN=\"<token_ovh>\" \\"
  echo "            --from-literal=GITHUB_TOKEN=\"<pat_github>\""
  echo
  echo "        (ou peuple-le via ESO), puis relance ./install.sh."
  exit 1
fi
echo "      ✓ Secret présent."

echo "[5/5] Agent : ConfigMap + CronJob..."
kubectl apply -f "${HERE}/agent/cronjob.yaml"

# Application Argo CD qui surveille le dépôt de manifestes. Optionnelle si tu
# gères déjà cette Application via l'app-of-apps (argocd/apps/).
# echo "[+] Application Argo CD (surveillance du dépôt de manifestes)..."
# kubectl apply -f "${HERE}/argocd/application.yaml"

echo
echo "✅ Terminé."
echo
echo "Déclencher l'agent sans attendre le cron :"
echo "  kubectl -n ${NAMESPACE} create job --from=cronjob/ai-remediation-agent test-run"
echo "  kubectl -n ${NAMESPACE} logs -f job/test-run"
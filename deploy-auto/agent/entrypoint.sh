#!/usr/bin/env bash
#
# Point d'entrée exécuté à chaque réveil du CronJob.
#
# L'agent (remediator.py) attend un dépôt Git LOCAL dans MANIFESTS_DIR : il y
# lit les manifestes, y crée une branche, commit et push. Un pod étant
# éphémère, ce dépôt n'existe pas encore au démarrage : on le clone d'abord.
#
# Toutes les valeurs sensibles arrivent par variables d'environnement, injectées
# depuis un Secret Kubernetes (idéalement géré par ESO, comme prévu dans la stack).

set -euo pipefail

# --- Paramètres attendus depuis l'environnement ---
: "${GITHUB_TOKEN:?GITHUB_TOKEN manquant}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY manquant (format owner/repo)}"
GIT_BASE_BRANCH="${GIT_BASE_BRANCH:-main}"

# Répertoire de travail clonable (writable, car le rootfs peut être read-only)
WORKDIR="${WORKDIR:-/tmp/manifests-repo}"

echo "[entrypoint] Clonage du dépôt de manifestes ${GITHUB_REPOSITORY}..."
rm -rf "${WORKDIR}"
git clone --branch "${GIT_BASE_BRANCH}" --single-branch \
  "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" \
  "${WORKDIR}"

# Identité Git pour les commits créés par l'agent
git -C "${WORKDIR}" config user.name  "ai-remediation-bot"
git -C "${WORKDIR}" config user.email "ai-remediation-bot@users.noreply.github.com"

# L'agent lit MANIFESTS_DIR pour trouver et modifier les fichiers : on le pointe
# vers le dépôt fraîchement cloné.
export MANIFESTS_DIR="${WORKDIR}"

echo "[entrypoint] Lancement de l'agent de remédiation en mode cluster..."
cd /app/ai-agent
exec python remediator.py --cluster

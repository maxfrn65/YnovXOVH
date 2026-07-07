# Image de l'agent de remédiation IA.
#
# Empaquette ai-agent/ (remediator.py + dépendances) et l'entrypoint du
# CronJob. À construire depuis la RACINE du dépôt (contexte = ., pour avoir
# accès à ai-agent/ et à deploy-auto/) :
#
#   docker build -f deploy-auto/Dockerfile -t <registry>/ai-remediation-agent:latest .
#   docker push <registry>/ai-remediation-agent:latest
#
FROM python:3.12-slim

# git est requis : l'entrypoint clone le dépôt de manifestes, l'agent commit/push.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Dépendances Python (cache Docker : on copie requirements en premier)
COPY ai-agent/requirements.txt /app/ai-agent/requirements.txt
RUN pip install --no-cache-dir -r /app/ai-agent/requirements.txt

# 2) Code de l'agent (entrypoint.sh fait `cd /app/ai-agent`)
COPY ai-agent/ /app/ai-agent/

# 3) Entrypoint du CronJob
COPY deploy-auto/agent/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Utilisateur non-root (cohérent avec securityContext runAsNonRoot du CronJob).
# UID/GID arbitraire haut ; /tmp reste writable via emptyDir monté par le pod.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin agent
USER 10001

ENTRYPOINT ["/app/entrypoint.sh"]
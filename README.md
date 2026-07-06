# YnovXOVH

Hackathon Lille Ynov Campus x OVHcloud (6-7 juillet 2026) - Équipe 9.
Chaîne d'audit et de remédiation GitOps sécurisée sur Kubernetes, pilotée par
Argo CD et enrichie par l'IA générative (AI Endpoints OVHcloud).

## Boucle cible

Détection d'une faille (Trivy-operator) -> analyse et correctif proposé par
l'IA -> Pull Request automatique sur ce dépôt -> revue humaine -> merge ->
resynchronisation Argo CD -> cluster corrigé.

## Structure du dépôt

```
argocd/
  projects/hackathon-project.yaml   AppProject Argo CD (repos/destinations autorises)
  bootstrap/root-app.yaml           Application "app of apps" -> surveille argocd/apps/
  apps/                             une Application Argo CD par brique
    00-kyverno.yaml                 policy-as-code (Alexis)
    01-falco.yaml                   detection runtime (Alexis)
    02-trivy-operator.yaml          audit/scan de vulnérabilités (Alexis)
    03-kube-prometheus-stack.yaml   observabilité (Alexandre)
    04-vulnerable-workloads.yaml    workloads de démo (Ulysse)
    05-ai-remediation.yaml          service IA (Maxime/Aurélien)
    06-monitoring-config.yaml       dashboards/alertes de la chaîne (Alexandre)
manifests/
  workloads/vulnerable-app/         manifests K8s du workload volontairement vulnérable
  ai-remediation/                   placeholder du service IA (à compléter par Maxime/Aurélien)
  monitoring/                       dashboard Grafana, alertes, contrat de métriques IA (Alexandre)
```

## Bootstrap (une seule fois, en manuel)

```bash
export KUBECONFIG=/path/to/kubeconfig-equipe-9.yaml

kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

kubectl apply -f argocd/projects/hackathon-project.yaml
kubectl apply -f argocd/bootstrap/root-app.yaml
```

À partir de là, tout passe par Git : Argo CD lit `argocd/apps/` (récursif) et
crée/maintient lui-même toutes les Applications listées ci-dessus.

## Politique de synchronisation

Chaque Application utilise :

```yaml
syncPolicy:
  automated:
    prune: true      # supprime ce qui a été retiré du repo
    selfHeal: true    # corrige tout drift manuel sur le cluster
  syncOptions:
    - CreateNamespace=true
```

## Sync quasi-instantanée post-merge (webhook)

Par défaut Argo CD poll le dépôt toutes les 3 min. Pour une resync immédiate
après un merge de PR (important pour la démo live) :

1. Argo CD > Settings > Repositories, ou directement sur GitHub :
   Settings > Webhooks > Add webhook
   - Payload URL : `https://<argocd-server>/api/webhook`
   - Content type : `application/json`
   - Secret : même valeur que celle configurée dans le secret `argocd-secret`
     (clé `webhook.github.secret`), à définir via `kubectl edit secret
     argocd-secret -n argocd` (ne jamais committer cette valeur dans Git).
2. Événement à envoyer : `Just the push event`.

## Secrets

Ne jamais committer `ai-endpoints-key.txt`, le kubeconfig ou un token GitHub
dans ce dépôt. Les créer directement sur le cluster :

```bash
kubectl create secret generic ai-remediation-secrets -n ai-remediation \
  --from-literal=ai-endpoints-token="$(cat ai-endpoints-key.txt)" \
  --from-literal=github-token="<PAT_github>"
```

# YnovXOVH

Hackathon Lille Ynov Campus x OVHcloud (6-7 juillet 2026) - Equipe 9.
Chaine d'audit et de remediation GitOps securisee sur Kubernetes, pilotee par
Argo CD et enrichie par l'IA generative (AI Endpoints OVHcloud).

## Boucle cible

Detection d'une faille (Trivy-operator) -> analyse et correctif propose par
l'IA -> Pull Request automatique sur ce depot -> revue humaine -> merge ->
resynchronisation Argo CD -> cluster corrige.

## Structure du depot

```
argocd/
  projects/hackathon-project.yaml   AppProject Argo CD (repos/destinations autorises)
  bootstrap/root-app.yaml           Application "app of apps" -> surveille argocd/apps/
  apps/                             une Application Argo CD par brique
    00-kyverno.yaml                 policy-as-code (Alexis)
    01-falco.yaml                   detection runtime (Alexis)
    02-trivy-operator.yaml          audit/scan de vulnerabilites (Alexis)
    03-kube-prometheus-stack.yaml   observabilite (Alexandre)
    04-vulnerable-workloads.yaml    workloads de demo (Ulysse)
    05-ai-remediation.yaml          service IA (Maxime/Aurelien)
manifests/
  workloads/vulnerable-app/         manifests K8s du workload volontairement vulnerable
  ai-remediation/                   placeholder du service IA (a completer par Maxime/Aurelien)
```

## Bootstrap (une seule fois, en manuel)

```bash
export KUBECONFIG=/path/to/kubeconfig-equipe-9.yaml

kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

kubectl apply -f argocd/projects/hackathon-project.yaml
kubectl apply -f argocd/bootstrap/root-app.yaml
```

A partir de la, tout passe par Git : Argo CD lit `argocd/apps/` (recursif) et
cree/maintient lui-meme toutes les Applications listees ci-dessus.

## Politique de synchronisation

Chaque Application utilise :

```yaml
syncPolicy:
  automated:
    prune: true      # supprime ce qui a ete retire du repo
    selfHeal: true    # corrige tout drift manuel sur le cluster
  syncOptions:
    - CreateNamespace=true
```

## Sync quasi-instantanee post-merge (webhook)

Par defaut Argo CD poll le depot toutes les 3 min. Pour une resync immediate
apres un merge de PR (important pour la demo live) :

1. Argo CD > Settings > Repositories, ou directement sur GitHub :
   Settings > Webhooks > Add webhook
   - Payload URL : `https://<argocd-server>/api/webhook`
   - Content type : `application/json`
   - Secret : meme valeur que celle configuree dans le secret `argocd-secret`
     (cle `webhook.github.secret`), a definir via `kubectl edit secret
     argocd-secret -n argocd` (ne jamais committer cette valeur dans Git).
2. Evenement a envoyer : `Just the push event`.

## Secrets

Ne jamais committer `ai-endpoints-key.txt`, le kubeconfig ou un token GitHub
dans ce depot. Les creer directement sur le cluster :

```bash
kubectl create secret generic ai-remediation-secrets -n ai-remediation \
  --from-literal=ai-endpoints-token="$(cat ai-endpoints-key.txt)" \
  --from-literal=github-token="<PAT_github>"
```

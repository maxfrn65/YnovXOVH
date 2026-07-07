# Automatisation de la chaîne de remédiation (CronJob + Argo CD)

Ce dossier contient tout le nécessaire pour **déployer et automatiser** l'agent
de remédiation IA (`ai-agent/`) dans un cluster Kubernetes, avec Argo CD comme
moteur GitOps.

## Les deux boucles, et pourquoi elles sont séparées

Il y a **deux automatismes distincts**, reliés uniquement par Git :

```
  [ CronJob : l'agent ]                         [ Argo CD ]
  détection → IA → PR         ── Git ──►         Git → cluster
  (s'arrête à la PR)          (le merge          (applique après merge)
                               humain fait
                               le lien)
```

- Le **CronJob** réveille l'agent toutes les 6 h. L'agent lit les rapports
  Trivy du cluster, fait corriger les manifestes par l'IA OVHcloud, et ouvre
  une **Pull Request**. Il s'arrête là.
- **Argo CD** surveille le dépôt Git. Quand un humain **merge** la PR, Argo CD
  détecte l'écart et resynchronise le cluster.

L'agent n'appelle jamais Argo CD. Le **garde-fou humain** (la revue de PR) est
donc structurel : sans merge, Argo CD ne voit rien.

## La contrainte kubeconfig

Le fichier kubeconfig (`clusters:` / `contexts:`) **n'est pas utilisé** ici.
Quand l'agent tourne dans le cluster, `remediator.py` bascule sur
`load_incluster_config()` : il s'authentifie via le **ServiceAccount** du pod,
défini dans `rbac/rbac.yaml`. On ne modifie donc jamais le kubeconfig existant.
Les droits accordés sont en **lecture seule** sur les rapports Trivy — l'agent
n'écrit rien dans le cluster, seulement dans Git.

## Contenu

| Fichier | Rôle |
|---|---|
| `Dockerfile` | Empaquette `ai-agent/` en image conteneur (avec `git`). |
| `agent/entrypoint.sh` | Clone le dépôt de manifestes puis lance `remediator.py --cluster`. |
| `agent/cronjob.yaml` | CronJob + ConfigMap + Secret de l'agent. |
| `rbac/rbac.yaml` | ServiceAccount + droits lecture des rapports Trivy. |
| `argocd/application.yaml` | Application Argo CD surveillant le dépôt. |
| `install.sh` | Déploie tout dans l'ordre. |

## Où installer Argo CD

Argo CD s'installe **dans le cluster lui-même**, dans son propre namespace
`argocd`. Version stable utilisée : `v3.3.12`. L'installation se fait par
`kubectl apply` du manifeste officiel (voir `install.sh`, étape 2).

## Déploiement

### 1. Construire et pousser l'image de l'agent
Depuis la racine du dépôt (là où se trouve `ai-agent/`) :

```bash
docker build -f deploy-automation/Dockerfile -t registry.example/ai-remediation-agent:latest .
docker push registry.example/ai-remediation-agent:latest
```

Adapter `registry.example/...` à ton registre, et l'`image:` dans
`agent/cronjob.yaml` en conséquence.

### 2. Adapter les valeurs
- `agent/cronjob.yaml` : `GITHUB_REPOSITORY`, `GIT_BASE_BRANCH`, le modèle IA.
- `argocd/application.yaml` : `repoURL`, `targetRevision`, `path`.
- Les secrets : idéalement via **ESO**, sinon `kubectl -n security edit secret
  remediation-agent-secrets`.

### 3. Tout installer
```bash
cd deploy-automation
./install.sh
```

### 4. Vérifier
```bash
# Déclencher l'agent manuellement sans attendre le cron
kubectl -n security create job --from=cronjob/ai-remediation-agent test-run
kubectl -n security logs -f job/test-run

# UI Argo CD
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d ; echo
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

## Le cycle complet, une fois en place

1. Le CronJob réveille l'agent (toutes les 6 h, ou déclenché à la main).
2. L'agent lit les rapports Trivy, fait corriger par l'IA, ouvre une PR.
3. Un humain **relit et merge** la PR.
4. Argo CD détecte le merge et resynchronise → **cluster corrigé**.

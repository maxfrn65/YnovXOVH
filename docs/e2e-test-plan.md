# Scénario de test bout-en-bout — démo live

Objectif : vérifier la boucle complète sur les workloads volontairement
vulnérables de `manifests/workloads/vulnerable-app/`, une fois le cluster et
toutes les briques déployés.

## Prérequis avant de lancer le test

- [ ] Cluster OVHcloud Managed Kubernetes up, `KUBECONFIG` exporté
- [ ] Argo CD bootstrappé (`root-app` synchronisé, toutes les Applications `Healthy`/`Synced`)
- [ ] trivy-operator, Kyverno, Falco déployés et actifs
- [ ] Service IA déployé (image réelle, pas le placeholder) avec les secrets configurés

## Étapes et points de vérification

1. **Détection statique (Trivy)**
   - `kubectl get vulnerabilityreports -n vulnerable-demo`
   - Attendu : un rapport pour `legacy-webapp` listant des CVE sur `nginx:1.16.0`

2. **Détection de configuration (Kyverno)**
   - `kubectl get policyreports -n vulnerable-demo`
   - Attendu : violations sur `privileged`, `runAsUser: 0`, capability `SYS_ADMIN`, `hostPath`, absence de limites de ressources

3. **Détection runtime (Falco)**
   - Générer une activité suspecte dans le pod (ex. `kubectl exec` puis lecture sous `/host`)
   - Attendu : alerte Falco visible dans les logs (`kubectl logs -n falco -l app.kubernetes.io/name=falco`)

4. **Correctif proposé par l'IA**
   - Attendre le prochain cycle du service IA (ou déclencher manuellement)
   - Attendu : une Pull Request ouverte sur le dépôt, labellisée `ai-remediation`, ciblant `manifests/workloads/vulnerable-app/deployment.yaml`

5. **Revue humaine**
   - Relire la PR : diff cohérent (image montée de version, `privileged`/`runAsUser`/`hostPath` retirés, limites de ressources ajoutées), rien d'autre modifié

6. **Merge**
   - Merger la PR sur `main`

7. **Resynchronisation Argo CD**
   - `kubectl get application vulnerable-workloads -n argocd -w`
   - Attendu : passage en `OutOfSync` puis retour à `Synced`/`Healthy` sans intervention manuelle

8. **Cluster corrigé**
   - `kubectl get pod -n vulnerable-demo -o yaml` : plus de `privileged`, `runAsUser: 0` ni `hostPath`, image à jour, limites de ressources présentes
   - Nouveau scan Trivy/Kyverno : rapport propre (ou fortement réduit) sur cette ressource

## Idée de mesure du temps de bout en bout

Chronométrer entre l'étape 1 (première détection) et l'étape 8 (cluster
corrigé) pour illustrer, en soutenance, la latence réelle de la boucle
détection -> correctif -> merge -> resync.

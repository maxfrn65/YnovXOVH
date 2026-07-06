# Observabilité de la chaîne (Alexandre)

Contenu déployé par l'Application Argo CD `monitoring-config`
(`argocd/apps/06-monitoring-config.yaml`) :

- `grafana-dashboard-chaine-securite.yaml` : dashboard Grafana versionné
  (failles détectées par sévérité, violations Kyverno, PRs de remédiation,
  temps de remédiation). Chargé automatiquement par le sidecar Grafana.
- `ai-remediation-metrics.yaml` : Service + ServiceMonitor pour scraper le
  service IA.
- `prometheusrules-chaine-securite.yaml` : alertes (CVE Critical présente,
  boucle de remédiation bloquée).

## Accès Grafana (démo)

```bash
kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80
# login: admin / mot de passe:
kubectl get secret monitoring-grafana -n monitoring \
  -o jsonpath="{.data.admin-password}" | base64 -d
```

Dashboard : "Chaîne de sécurité - détection & remédiation IA" (uid
`chaine-securite`).

## Contrat de métriques du service IA (pour Maxime/Aurélien)

Le dashboard et les alertes supposent que `ai-remediation-service` expose
sur `:8080/metrics` (format Prometheus, le Service/ServiceMonitor sont déjà
en place — il suffit de labelliser les pods `app: ai-remediation-service`) :

| Métrique | Type | Rôle |
|---|---|---|
| `ai_remediation_findings_total` | counter | findings analysés (labels libres : `source=trivy\|kyverno\|falco`, `severity`) |
| `ai_remediation_prs_opened_total` | counter | PRs de correctif ouvertes sur GitHub |
| `ai_remediation_prs_merged_total` | counter | PRs mergées (faille considérée corrigée) |
| `ai_remediation_duration_seconds` | histogram | temps entre la détection du finding et l'ouverture de la PR |

Exemple avec `prometheus_client` (Python) :

```python
from prometheus_client import Counter, Histogram, start_http_server

FINDINGS = Counter("ai_remediation_findings_total", "Findings analysés", ["source", "severity"])
PRS_OPENED = Counter("ai_remediation_prs_opened_total", "PRs ouvertes")
PRS_MERGED = Counter("ai_remediation_prs_merged_total", "PRs mergées")
DURATION = Histogram("ai_remediation_duration_seconds", "Détection -> PR ouverte",
                     buckets=[30, 60, 120, 300, 600, 1200, 3600])

start_http_server(8080)
```

## Ordre de synchronisation

`monitoring-config` et les ServiceMonitors de trivy-operator/kyverno
dépendent des CRD installées par `kube-prometheus-stack` : à la première
synchronisation du cluster, laisser la stack Prometheus se poser puis
relancer un sync (une politique de retry est configurée sur l'app).

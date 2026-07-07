# 🤖 Agent de Remédiation de Sécurité IA (OVHcloud AI Endpoints)

Ce dossier contient l'agent intelligent d'audit et de remédiation automatisé conçu dans le cadre du Hackathon **Lille Ynov Campus × OVHcloud**. 

Cet agent permet d'automatiser le cycle suivant :
`Détection d'une faille dans le cluster` ➡️ `Analyse & génération de correctif par l'IA (OVHcloud AI Endpoints)` ➡️ `Création d'une Pull Request sur GitHub` ➡️ `Merge` ➡️ `Mise à jour par Argo CD`.

---

## 📋 Prérequis

- **Python 3.8+**
- Un token d'accès **OVHcloud AI Endpoints** (disponible dans votre console OVHcloud, onglet Public Cloud > AI Endpoints > API Keys).
- Un cluster Kubernetes actif avec **Trivy Operator** déployé (pour le mode `--cluster`).
- Un token d'accès personnel GitHub (PAT) avec des droits d'écriture sur votre dépôt de configuration.

---

## 🚀 Installation

1. Accédez au dossier `ai-agent` :
   ```bash
   cd ai-agent
   ```

2. Installez les dépendances requises :
   ```bash
   pip install -r requirements.txt
   ```

3. Configurez votre environnement :
   ```bash
   cp .env.example .env
   ```
   Éditez le fichier `.env` nouvellement créé et renseignez vos tokens et configurations.

---

## 🛠️ Utilisation

### 1. Lancer la Simulation Locale (Idéal pour les démos & tests de prompts)
Vous pouvez tester le bon fonctionnement de l'intégration IA et la génération de correctifs sans avoir besoin de cluster actif, grâce à un exemple de déploiement vulnérable fourni dans `samples/`.

Pour lancer la simulation :
```bash
python simulate.py
```
Le script va :
1. Charger le fichier YAML vulnérable (`samples/vulnerable-deployment.yaml`).
2. Charger un rapport d'erreurs Trivy simulé (`samples/trivy-failures.json`).
3. Envoyer ces informations aux **AI Endpoints de OVHcloud** avec le prompt de remédiation.
4. Enregistrer le manifeste corrigé dans `samples/corrected-deployment.yaml`.
5. Afficher un **diff de sécurité colorisé** comparant l'original et le corrigé.

### 2. Lancer la Remédiation Active sur le Cluster Kube
Lorsque votre cluster Kubernetes est connecté (avec `kubectl`), vous pouvez exécuter le script principal pour interroger le cluster en temps réel :
```bash
python remediator.py --cluster
```
Ce script va :
1. Récupérer les Custom Resources `ConfigAuditReports` générées par Trivy.
2. Pour chaque anomalie de sécurité détectée :
   - Trouver le manifeste YAML source correspondant dans votre dépôt local.
   - Envoyer le code source + les détails de la faille à l'IA OVHcloud.
   - Remplacer le contenu du fichier par le correctif de l'IA.
   - Créer une branche Git dédiée (ex: `remediation/fix-nginx`).
   - Pusher la branche et **ouvrir automatiquement une Pull Request** sur votre dépôt GitHub.

---

## 📝 Stratégie de Prompt Engineering

L'agent utilise un prompt système directif (`remediator.py`) pour formater les réponses de l'IA :
- **Directivité** : Le modèle doit renvoyer uniquement du YAML entouré de balises markdown pour faciliter le parsing.
- **Préservation** : Obligation de préserver les informations non liées à la sécurité (labels, services, configurations réseau).
- **Précision** : Seules les failles d'audit spécifiées doivent être remédiées.

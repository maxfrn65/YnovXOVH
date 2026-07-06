#!/usr/bin/env python3
import os
import sys
import json
import re
import subprocess
import yaml
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import requests

# Charger les variables d'environnement
load_dotenv()

# --- Configuration ---
OVH_AI_ACCESS_TOKEN = os.getenv("OVH_AI_ENDPOINTS_ACCESS_TOKEN")
OVH_AI_BASE_URL = os.getenv("OVH_AI_ENDPOINTS_BASE_URL", "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1")
OVH_AI_MODEL = os.getenv("OVH_AI_ENDPOINTS_MODEL", "Mistral-7B-Instruct-v0.3")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")  # Format: "owner/repo"
GIT_BASE_BRANCH = os.getenv("GIT_BASE_BRANCH", "main")
MANIFESTS_DIR = os.getenv("MANIFESTS_DIR", "../")

# Validation de base
if not OVH_AI_ACCESS_TOKEN:
    print("[WARNING] OVH_AI_ENDPOINTS_ACCESS_TOKEN non défini. L'appel à l'IA échouera sans token valide.")

# --- Client OpenAI compatible OVHcloud ---
client = None
if OVH_AI_ACCESS_TOKEN:
    client = OpenAI(
        api_key=OVH_AI_ACCESS_TOKEN,
        base_url=OVH_AI_BASE_URL
    )

# --- Fonction d'intégration IA ---
def get_ai_remediation(manifest_yaml, audit_details):
    """
    Envoie le manifeste Kubernetes et le rapport de failles aux AI Endpoints d'OVHcloud.
    Renvoie le manifeste corrigé généré par le LLM.
    """
    if not client:
        print("[ERROR] Le client OpenAI/OVHcloud n'est pas initialisé (Token manquant).")
        return None

    system_prompt = (
        "Tu es un ingénieur DevSecOps expert en sécurité Kubernetes.\n"
        "Ton rôle est de corriger des fichiers de déploiement Kubernetes (YAML) en fonction d'un rapport de sécurité Trivy.\n\n"
        "Tu dois impérativement respecter les règles suivantes :\n"
        "1. Analyse le manifeste YAML d'origine fourni et le rapport d'erreurs/failles associé.\n"
        "2. Corrige TOUTES les failles de sécurité mentionnées dans le rapport en modifiant le manifeste YAML d'origine "
        "(ex: ajouter 'securityContext', 'runAsNonRoot: true', 'readOnlyRootFilesystem: true', supprimer les privilèges élevés, "
        "passer à une version d'image sécurisée si demandé, etc.).\n"
        "3. Ne modifie pas la structure générale du manifeste (conserve les labels, les selectors, les ports, l'appartenance de namespace, etc.) qui n'a aucun rapport avec la sécurité.\n"
        "4. Rends la réponse la plus propre possible.\n"
        "5. Renvoie UNIQUEMENT le code YAML complet et valide. Ne mets aucun texte d'introduction ou d'explication. "
        "Entoure le code YAML de balises markdown ```yaml et ```.\n"
    )

    user_prompt = (
        f"Voici le manifeste YAML d'origine :\n"
        f"---\n"
        f"{manifest_yaml}\n\n"
        f"Voici les failles de sécurité détectées par Trivy :\n"
        f"{json.dumps(audit_details, indent=2, ensure_ascii=False)}\n\n"
        f"Génère le manifeste YAML corrigé conformément aux consignes."
    )

    print(f"[IA] Envoi de la demande de remédiation au modèle '{OVH_AI_MODEL}' sur OVHcloud...")
    try:
        response = client.chat.completions.create(
            model=OVH_AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1  # Faible température pour plus de déterminisme sur le YAML
        )
        content = response.choices[0].message.content.strip()

        # Extraire le bloc de code YAML
        yaml_match = re.search(r"```(?:yaml)?\n(.*?)```", content, re.DOTALL)
        if yaml_match:
            return yaml_match.group(1).strip()
        
        # Si le modèle a renvoyé du YAML brut sans balises markdown
        if content.startswith("apiVersion:") or "kind:" in content:
            return content

        print("[ERROR] Le format de la réponse de l'IA ne contient pas de bloc de code YAML valide.")
        print(f"Réponse brute de l'IA :\n{content}")
        return None
    except Exception as e:
        print(f"[ERROR] Échec de la requête vers OVHcloud AI Endpoints : {e}")
        return None

# --- Fonctions Git & GitHub ---
def run_command(cmd, cwd=None):
    """Exécute une commande shell et renvoie la sortie."""
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, cwd=cwd)
    if result.returncode != 0:
        raise Exception(f"Commande échouée : {cmd}\nErreur : {result.stderr.strip()}")
    return result.stdout.strip()

def create_github_pr(branch_name, pr_title, pr_body):
    """Crée une Pull Request sur GitHub via l'API REST."""
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        print("[WARNING] GITHUB_TOKEN ou GITHUB_REPOSITORY non configuré. Création de la PR ignorée.")
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    data = {
        "title": pr_title,
        "head": branch_name,
        "base": GIT_BASE_BRANCH,
        "body": pr_body
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            pr_info = response.json()
            print(f"[Git] Pull Request créée avec succès : {pr_info['html_url']}")
            return pr_info['html_url']
        else:
            print(f"[ERROR] Échec de la création de la PR : {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception lors de la création de la PR GitHub : {e}")
        return None

def apply_fix_and_push(file_path, corrected_yaml, resource_name, issue_summary):
    """
    Applique le patch YAML localement, crée une branche Git,
    commit, push et ouvre une PR.
    """
    repo_dir = Path(MANIFESTS_DIR).resolve()
    print(f"[Git] Utilisation du dépôt Git à : {repo_dir}")

    # S'assurer qu'on est sur la branche de base et propre
    try:
        run_command("git checkout " + GIT_BASE_BRANCH, cwd=repo_dir)
        run_command("git pull origin " + GIT_BASE_BRANCH, cwd=repo_dir)
    except Exception as e:
        print(f"[WARNING] Impossible de pull la branche de base : {e}. On continue localement.")

    # Créer une branche unique pour ce correctif
    sanitized_name = re.sub(r'[^a-zA-Z0-9-]', '-', resource_name.lower())
    branch_name = f"remediation/fix-{sanitized_name}"
    print(f"[Git] Création de la branche : {branch_name}")
    try:
        run_command(f"git checkout -b {branch_name}", cwd=repo_dir)
    except Exception:
        # Si la branche existe déjà, on bascule dessus
        run_command(f"git checkout {branch_name}", cwd=repo_dir)

    # Écrire le nouveau contenu YAML
    abs_file_path = repo_dir / file_path
    with open(abs_file_path, "w") as f:
        f.write(corrected_yaml + "\n")
    print(f"[Git] Fichier mis à jour localement : {abs_file_path}")

    # Commit & Push
    try:
        run_command("git add .", cwd=repo_dir)
        commit_msg = f"security: remédiation automatique IA pour {resource_name}"
        run_command(f'git commit -m "{commit_msg}"', cwd=repo_dir)
        print("[Git] Commit effectué.")
        
        if GITHUB_TOKEN and GITHUB_REPOSITORY != "username/YnovXOVH":
            print(f"[Git] Poussée de la branche vers origin...")
            run_command(f"git push origin {branch_name} --force", cwd=repo_dir)
            
            # Créer la Pull Request
            pr_title = f"🔒 Security Fix: Remédiation IA pour {resource_name}"
            pr_body = (
                f"### Remédiation automatique de sécurité par IA (OVHcloud AI Endpoints)\n\n"
                f"L'agent IA a détecté des failles de sécurité dans le manifeste du composant `{resource_name}`.\n\n"
                f"**Détails des failles corrigées :**\n"
                f"```json\n"
                f"{json.dumps(issue_summary, indent=2)}\n"
                f"```\n\n"
                f"**Modifications apportées :**\n"
                f"- Ajout/correction des paramètres de sécurité recommandés.\n"
                f"- Validation de la structure YAML.\n\n"
                f"_Veuillez valider cette PR pour appliquer le correctif dans Argo CD._"
            )
            create_github_pr(branch_name, pr_title, pr_body)
        else:
            print("[INFO] Mode local uniquement (pas de token GitHub valide ou dépôt par défaut). Le fichier a été modifié localement.")
            print(f"Vous pouvez créer votre branche, commit et inspecter le fichier : {file_path}")
        
        # Revenir sur la branche de base
        run_command("git checkout " + GIT_BASE_BRANCH, cwd=repo_dir)
    except Exception as e:
        print(f"[ERROR] Échec des opérations Git : {e}")

# --- Recherche du manifeste dans le dépôt local ---
def find_manifest_file(kind, name):
    """
    Scanne les fichiers YAML dans MANIFESTS_DIR et trouve celui qui définit
    la ressource spécifiée par son 'kind' et son 'name'.
    Gère aussi les cas où la ressource auditée est un ReplicaSet ou un Pod
    généré par un Deployment en cherchant le Deployment associé.
    """
    search_dir = Path(MANIFESTS_DIR).resolve()
    
    # Normalisation du kind
    target_kinds = [kind.lower()]
    if kind.lower() in ["replicaset", "pod"]:
        target_kinds.append("deployment")
        target_kinds.append("statefulset")
        target_kinds.append("daemonset")
    
    # Nettoyage du nom pour enlever les suffixes générés (ex: nginx-6d4cf56db6 -> nginx)
    base_name = name
    if kind.lower() == "replicaset":
        # Retire le hash de fin (ex: -6d4cf56db6)
        base_name = re.sub(r'-[0-9a-f]{8,10}$', '', name)
    elif kind.lower() == "pod":
        # Retire les deux derniers hashs (ex: -6d4cf56db6-xxxxx ou -xxxxx)
        base_name = re.sub(r'-[0-9a-f]{8,10}-[a-z0-9]{5}$', '', name)
        base_name = re.sub(r'-[a-z0-9]{5}$', '', base_name)

    print(f"[Recherche] Recherche d'un manifeste pour Kind: {kind} ({target_kinds}) et Nom: {name} (base_name: {base_name}) dans {search_dir}")

    # Parcourir tous les fichiers yaml du dossier
    for path in search_dir.glob("**/*.yaml"):
        # Ignorer le dossier ai-agent
        if "ai-agent" in path.parts:
            continue
        try:
            with open(path, "r") as f:
                content = f.read()
                # Les fichiers K8s peuvent contenir plusieurs manifestes séparés par '---'
                documents = list(yaml.safe_load_all(content))
                for doc in documents:
                    if not doc or not isinstance(doc, dict):
                        continue
                    
                    doc_kind = doc.get("kind", "").lower()
                    doc_name = doc.get("metadata", {}).get("name", "").lower()
                    
                    # Correspondance exacte ou partielle si c'est un parent
                    if doc_kind in target_kinds:
                        if doc_name == base_name.lower() or base_name.lower().startswith(doc_name):
                            # On renvoie le chemin relatif pour Git
                            rel_path = path.relative_to(search_dir)
                            return str(rel_path), doc
        except Exception as e:
            # Ignorer les erreurs de lecture de fichiers non valides
            pass

    for path in search_dir.glob("**/*.yml"):
        if "ai-agent" in path.parts:
            continue
        try:
            with open(path, "r") as f:
                content = f.read()
                documents = list(yaml.safe_load_all(content))
                for doc in documents:
                    if not doc or not isinstance(doc, dict):
                        continue
                    doc_kind = doc.get("kind", "").lower()
                    doc_name = doc.get("metadata", {}).get("name", "").lower()
                    if doc_kind in target_kinds:
                        if doc_name == base_name.lower() or base_name.lower().startswith(doc_name):
                            rel_path = path.relative_to(search_dir)
                            return str(rel_path), doc
        except Exception:
            pass

    return None, None

# --- Récupération des rapports Kubernetes ---
def scan_and_remediate_cluster():
    """
    Interroge le cluster Kubernetes pour trouver les ConfigAuditReports / VulnerabilityReports
    présentant des failles, et déclenche la remédiation IA.
    """
    try:
        from kubernetes import client as k8s_client
        from kubernetes import config as k8s_config
        try:
            k8s_config.load_kube_config()
        except Exception:
            k8s_config.load_incluster_config()
        
        custom_api = k8s_client.CustomObjectsApi()
    except Exception as e:
        print(f"[Kubernetes] Impossible d'initialiser le client K8s : {e}")
        print("[Kubernetes] Assurez-vous d'avoir configuré kubectl ou d'avoir accès à un cluster.")
        return

    print("[Kubernetes] Récupération des rapports ConfigAuditReports...")
    try:
        # Lister tous les ConfigAuditReports du cluster
        reports = custom_api.list_cluster_custom_object(
            group="aquasecurity.github.io",
            version="v1alpha1",
            plural="configauditreports"
        )
    except Exception as e:
        print(f"[Kubernetes] Erreur lors de la récupération des rapports : {e}")
        return

    items = reports.get("items", [])
    print(f"[Kubernetes] Trouvé {len(items)} ConfigAuditReports au total.")

    for report in items:
        metadata = report.get("metadata", {})
        report_name = metadata.get("name")
        labels = metadata.get("labels", {})
        
        # Récupérer les infos de la ressource auditée
        resource_kind = labels.get("trivy-operator.resource.kind")
        resource_name = labels.get("trivy-operator.resource.name")
        
        if not resource_kind or not resource_name:
            continue

        report_data = report.get("report", {})
        summary = report_data.get("summary", {})
        
        # Si aucune faille, on passe au suivant
        fail_count = summary.get("criticalCount", 0) + summary.get("highCount", 0) + summary.get("mediumCount", 0) + summary.get("lowCount", 0)
        if fail_count == 0:
            continue

        print(f"\n[Alerte] Faille trouvée sur {resource_kind}/{resource_name} ({fail_count} échecs).")

        # Extraire les checks en échec
        failed_checks = []
        for check in report_data.get("checks", []):
            if not check.get("success", True):
                failed_checks.append({
                    "checkID": check.get("checkID"),
                    "severity": check.get("severity"),
                    "messages": check.get("messages", [])
                })

        # Chercher le fichier manifeste local correspondant
        file_path, manifest_doc = find_manifest_file(resource_kind, resource_name)
        if not file_path:
            print(f"[Recherche] Manifeste YAML introuvable pour {resource_kind}/{resource_name} dans le dépôt local.")
            continue

        print(f"[Trouvé] Correspondance avec le fichier : {file_path}")

        # Lire le manifeste d'origine complet
        repo_dir = Path(MANIFESTS_DIR).resolve()
        with open(repo_dir / file_path, "r") as f:
            manifest_yaml_content = f.read()

        # Préparer le rapport de failles synthétique pour l'IA
        audit_details = {
            "resource": f"{resource_kind}/{resource_name}",
            "failed_checks": failed_checks
        }

        # Appeler l'IA pour générer le correctif
        corrected_yaml = get_ai_remediation(manifest_yaml_content, audit_details)
        
        if corrected_yaml:
            # Appliquer le correctif Git, commit et PR
            apply_fix_and_push(file_path, corrected_yaml, resource_name, failed_checks)
        else:
            print("[IA] Aucun correctif généré ou erreur survenue.")

if __name__ == "__main__":
    print("=== Agent de Remédiation IA GitOps (OVHcloud AI Endpoints) ===")
    if len(sys.argv) > 1 and sys.argv[1] == "--cluster":
        scan_and_remediate_cluster()
    else:
        print("[INFO] Pour scanner le cluster Kubernetes actif, lancez avec l'option --cluster.")
        print("[INFO] Vous pouvez exécuter simulate.py pour tester la remédiation en local sans cluster actif.")

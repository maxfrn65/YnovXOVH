#!/usr/bin/env python3
import os
import sys
import json
import difflib
from pathlib import Path
from dotenv import load_dotenv

# Ajouter le dossier parent au PATH pour pouvoir importer remediator.py
sys.path.append(str(Path(__file__).resolve().parent))
from remediator import get_ai_remediation

# Charger l'environnement
load_dotenv()

def print_color_diff(text1, text2, fromfile='Original', tofile='Corrigé'):
    """Affiche un diff unifié colorisé dans la console."""
    lines1 = text1.splitlines(keepends=True)
    lines2 = text2.splitlines(keepends=True)
    
    diff = difflib.unified_diff(lines1, lines2, fromfile=fromfile, tofile=tofile)
    
    has_diff = False
    for line in diff:
        has_diff = True
        if line.startswith('+') and not line.startswith('+++'):
            # Vert pour les ajouts
            print(f"\033[92m{line.rstrip()}\033[0m")
        elif line.startswith('-') and not line.startswith('---'):
            # Rouge pour les suppressions
            print(f"\033[91m{line.rstrip()}\033[0m")
        elif line.startswith('@@'):
            # Bleu pour les infos de ligne
            print(f"\033[94m{line.rstrip()}\033[0m")
        else:
            print(line.rstrip())
            
    if not has_diff:
        print("Aucune différence détectée entre le fichier original et la réponse.")

def main():
    print("=== Simulation de Remédiation IA (OVHcloud AI Endpoints) ===")
    
    # Chemins des fichiers d'exemple
    current_dir = Path(__file__).resolve().parent
    vulnerable_file = current_dir / "samples" / "vulnerable-deployment.yaml"
    failures_file = current_dir / "samples" / "trivy-failures.json"
    output_file = current_dir / "samples" / "corrected-deployment.yaml"
    
    # Vérifier l'existence des fichiers
    if not vulnerable_file.exists() or not failures_file.exists():
        print("[ERROR] Fichiers d'exemple manquants dans samples/")
        sys.exit(1)
        
    # Lire le déploiement vulnérable
    print(f"[1/4] Lecture du manifeste vulnérable : {vulnerable_file.name}")
    with open(vulnerable_file, "r") as f:
        vulnerable_yaml = f.read()
        
    # Lire le rapport d'erreurs Trivy
    print(f"[2/4] Lecture du rapport d'erreurs Trivy : {failures_file.name}")
    with open(failures_file, "r") as f:
        failures_data = json.load(f)
        
    print(f"[3/4] Appel de l'IA (OVHcloud AI Endpoints) pour corriger le manifeste...")
    corrected_yaml = get_ai_remediation(vulnerable_yaml, failures_data)
    
    if not corrected_yaml:
        print("[ERROR] Impossible de générer la remédiation via l'IA.")
        print("[CONSEIL] Vérifiez que vous avez configuré OVH_AI_ENDPOINTS_ACCESS_TOKEN dans un fichier .env.")
        sys.exit(1)
        
    print(f"\n[4/4] Remédiation réussie ! Sauvegarde dans : {output_file.name}")
    
    # Enregistrer le fichier corrigé
    with open(output_file, "w") as f:
        f.write(corrected_yaml + "\n")
        
    print("\n" + "="*40 + " COMPARATIF DES MODIFICATIONS " + "="*40)
    print_color_diff(vulnerable_yaml, corrected_yaml)
    print("="*110)

if __name__ == "__main__":
    main()

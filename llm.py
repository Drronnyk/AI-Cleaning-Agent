import json
import os
import pandas as pd
from groq import Groq


ACTIONS_AUTORISEES = ["corriger", "supprimer", "verifier_manuellement"]
CHAMPS_ATTENDUS = ["id_signalement", "action", "correction_proposee", "justification"]

REGLES_DE_PRUDENCE = {
    "R-06": {"action": "supprimer", "raison": "La copie est identique sans risque"},
    "R-05": {"action": "verifier_manuellement", "raison": "Deux commandes différentes, réponse humaine requise"},
    "R-08": {"action": "verifier_manuellement", "raison": "Le modèle ne connaît pas la valeur vraie (interdiction d'inventer)"},
    "R-07": {"action": "corriger", "raison": "Quantité x prix est connu, sauf si l'un est suspect"},
    "R-10": {"action": "corriger", "raison": "La forme correcte du format/texte est connue"},
    "R-11": {"action": "corriger", "raison": "La forme correcte du format/texte est connue"},
}

# Contrôle de démarrage : une faute de frappe dans une action est détectée tout de suite
for regle, infos in REGLES_DE_PRUDENCE.items():
    assert infos["action"] in ACTIONS_AUTORISEES, (
        f"Action invalide pour {regle} : {infos['action']}"
    )


def valider_reponse(element) -> bool:
    if not isinstance(element, dict):
        return False

    for champ in CHAMPS_ATTENDUS:
        if champ not in element:
            return False

    if element["action"] not in ACTIONS_AUTORISEES:
        return False

    if element["action"] == "corriger":
        correction = element["correction_proposee"]
        if correction is None or str(correction).strip() == "":
            return False

    return True


def nettoyer_ligne(ligne: dict) -> dict:
    """Prépare une ligne Pandas pour json.dumps : NaN -> None, types NumPy -> types Python."""
    propre = {}
    for cle, valeur in ligne.items():
        if pd.isna(valeur):
            propre[cle] = None
        elif hasattr(valeur, "item"):
            propre[cle] = valeur.item()
        else:
            propre[cle] = valeur
    return propre


def reponse_de_repli(id_signalement: str, motif: str) -> dict:
    """Réponse de sécurité : le signalement est renvoyé à l'humain."""
    return {
        "id_signalement": id_signalement,
        "action": "verifier_manuellement",
        "correction_proposee": "",
        "justification": motif,
    }


def construire_messages(ligne: dict, signalements: list) -> list:

    prompt_system = f"""Tu es un assistant expert en qualité des données pour une entreprise de distribution au Cameroun. 
Tous les montants financiers manipulés sont en Francs CFA (XAF).

Ton rôle est d'analyser des anomalies de données (signalements) sur une ligne de transaction et de proposer une action pour chaque signalement selon un contrat strict.

### RÈGLES CRITIQUES :
- INTERDICTION D'INVENTER : Ne devine jamais une valeur manquante ou absente si tu ne possèdes pas la certitude absolue de sa valeur réelle. Dans ce cas, demande une vérification manuelle.
- Tu dois impérativement répondre en Français.

### CONTRAT D'ACTIONS :
Tu dois obligatoirement choisir l'une des 3 actions suivantes :
1. 'corriger' : Si la correction est logique, mathématique ou évidente.
2. 'supprimer' : Uniquement en cas de doublon exact et confirmé.
3. 'verifier_manuellement' : Si la valeur est manquante ou nécessite un arbitrage humain.

### FORMAT DE RÉPONSE REQUIS :
Tu dois répondre STRICTEMENT sous la forme d'un objet JSON contenant une liste nommée 'resultats'. Chaque élément de cette liste doit correspondre à un signalement et contenir exactement ces 4 clés :
- 'id_signalement' : l'identifiant fourni.
- 'action' : une des 3 actions autorisées.
- 'correction_proposee' : la valeur corrigée sous forme de chaîne (ou une chaîne vide "" si l'action est 'supprimer' ou 'verifier_manuellement').
- 'justification' : une courte phrase expliquant ton choix en français (contexte Cameroun/XAF).

Exemple de format JSON attendu :
{{
    "resultats": [
        {{
            "id_signalement": "SIG-XYZ",
            "action": "verifier_manuellement",
            "correction_proposee": "",
            "justification": "Valeur manquante non stockée, arbitrage humain requis."
        }}
    ]
}}
"""

    contexte_ligne = json.dumps(nettoyer_ligne(ligne), ensure_ascii=False, indent=2, default=str)

    details_signalements = ""
    for sig in signalements:
        code_regle = sig.get("regle", "")
        prudence = REGLES_DE_PRUDENCE.get(code_regle, {})
        consigne_prudence = f" (Consigne par défaut pour cette règle : {prudence['action']} car {prudence['raison']})" if prudence else ""

        details_signalements += f"""
- ID Signalement : {sig.get('id_signalement')}
  Règle enfreinte : {code_regle}{consigne_prudence}
  Colonne ciblée : {sig.get('colonne')}
  Valeur observée : '{sig.get('valeur_observee')}'
  Explication de l'anomalie : {sig.get('explication')}
--------------------------------------------------"""

    prompt_user = f"""Voici les données de la transaction à analyser :

### CONTEXTE COMPLET DE LA LIGNE CSV :
{contexte_ligne}

### LISTE DES SIGNALEMENTS À TRAITER SUR CETTE LIGNE :
{details_signalements}

Génère maintenant l'objet JSON contenant tes décisions pour chacun de ces signalements en respectant scrupuleusement le contrat d'action et les consignes de prudence."""

    return [
        {"role": "system", "content": prompt_system},
        {"role": "user", "content": prompt_user}
    ]


def analyser_signalements_ligne(client: Groq, ligne: dict, signalements: list,
                                model: str = None) -> list:
    """
    Envoie une ligne et ses signalements à Groq, valide les réponses et renvoie
    EXACTEMENT une réponse par signalement envoyé (réponse de repli si besoin).
    """
    model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    ids_envoyes = [str(sig.get("id_signalement")) for sig in signalements]
    messages = construire_messages(ligne, signalements)

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"}
    )

    contenu_brut = completion.choices[0].message.content

    # Réponse vide (par exemple limite de jetons atteinte pendant le raisonnement)
    if not contenu_brut:
        print(" Erreur : réponse vide du modèle.")
        return [reponse_de_repli(i, "Pas de réponse exploitable du modèle.") for i in ids_envoyes]

    try:
        donnees = json.loads(contenu_brut)
    except (json.JSONDecodeError, TypeError):
        print(" Erreur critique : le modèle n'a pas renvoyé un JSON valide.")
        return [reponse_de_repli(i, "Pas de réponse exploitable du modèle.") for i in ids_envoyes]

    resultats = donnees.get("resultats", []) if isinstance(donnees, dict) else []
    if not isinstance(resultats, list):
        resultats = []

    reponses_valides = {}
    for item in resultats:
        if not valider_reponse(item):
            print(f" [Contrat enfreint] Réponse écartée : {item}")
            continue
        id_recu = str(item["id_signalement"])
        if id_recu not in ids_envoyes:
            print(f" [Identifiant inconnu] Réponse écartée : {item}")
            continue
        reponses_valides[id_recu] = item

    # Une réponse par signalement envoyé : repli pour ceux qui manquent
    return [
        reponses_valides.get(i) or reponse_de_repli(i, "Pas de réponse exploitable du modèle.")
        for i in ids_envoyes
    ]

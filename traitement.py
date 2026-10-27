import json
import os
import re
import time
from itertools import islice

import pandas as pd
from dotenv import load_dotenv
from groq import Groq, APIError, RateLimitError

from llm import analyser_signalements_ligne

FICHIER_PROGRES = "decisions_llm.jsonl"

# ---------- Références pour contrôler les propositions du modèle ----------
VALEURS_AUTORISEES = {
    "ville": ["Douala", "Yaoundé", "Bafoussam", "Garoua", "Bamenda", "Bertoua"],
    "categorie": ["Alimentaire", "Boissons", "Hygiène", "Électronique", "Papeterie", "Quincaillerie"],
    "mode_paiement": ["espèces", "Mobile Money", "virement", "carte bancaire"],
    "statut_paiement": ["payé", "partiellement payé", "impayé", "remboursé"],
    "statut_commande": ["en préparation", "expédiée", "livrée", "annulée", "retournée"],
}
FORMATS = {
    "email_client": r"[^\s@]+@[^\s@]+\.[^\s@]+",
    "telephone_client": r"\+237 6\d{2} \d{2} \d{2} \d{2}",
    "date_commande": r"\d{4}-\d{2}-\d{2}",
    "date_livraison": r"\d{4}-\d{2}-\d{2}",
}
COLONNES_NUMERIQUES = ["quantite", "prix_unitaire", "montant_total", "montant_paye"]


# ---------- Sauvegarde reprenable ----------
def charger_progres() -> dict:
    decisions = {}
    if os.path.exists(FICHIER_PROGRES):
        with open(FICHIER_PROGRES, encoding="utf-8") as f:
            for ligne in f:
                if ligne.strip():
                    d = json.loads(ligne)
                    decisions[d["id_signalement"]] = d   # la dernière version gagne
    return decisions


def sauvegarder_decision(decision: dict) -> None:
    with open(FICHIER_PROGRES, "a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False) + "\n")


def reecrire_progres(decisions: dict) -> None:

    with open(FICHIER_PROGRES, "w", encoding="utf-8") as f:
        for d in decisions.values():
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def decisions_doublons(rapport: pd.DataFrame, ventes: pd.DataFrame) -> list:
    copies = ventes.duplicated(keep="first")
    decisions = []
    for _, sig in rapport[rapport["regle"] == "R-06"].iterrows():
        est_copie = bool(copies.loc[int(sig["ligne_csv"])])
        decisions.append({
            "id_signalement": sig["id_signalement"],
            "action": "supprimer" if est_copie else "conserver",
            "correction_proposee": "",
            "justification": (
                "Copie exacte d'une ligne précédente : suppression sans risque."
                if est_copie else
                "Ligne originale à conserver : seule sa copie est à supprimer."
            ),
        })
    return decisions


def normaliser_telephone(valeur):
    v = str(valeur).strip().strip('"')
    if re.search(r"[^\d\s+\-()./]", v):          # une lettre dans le numéro : trop ambigu
        return None
    chiffres = re.sub(r"\D", "", v)
    for prefixe in ("00237", "237"):
        if chiffres.startswith(prefixe):
            chiffres = chiffres[len(prefixe):]
            break
    if len(chiffres) == 9 and chiffres[0] == "6":
        return f"+237 {chiffres[:3]} {chiffres[3:5]} {chiffres[5:7]} {chiffres[7:]}"
    return None


def decisions_telephones(rapport: pd.DataFrame) -> list:
    cible = rapport[(rapport["regle"] == "R-10") & (rapport["colonne"] == "telephone_client")]
    decisions = []
    for _, sig in cible.iterrows():
        nouveau = normaliser_telephone(sig["valeur_observee"])
        decisions.append({
            "id_signalement": sig["id_signalement"],
            "action": "corriger" if nouveau else "verifier_manuellement",
            "correction_proposee": nouveau or "",
            "justification": (
                "Numéro reformaté au format +237 6XX XX XX XX (chiffres conservés)."
                if nouveau else
                "Numéro incomplet ou ambigu : impossible de le reconstruire sans inventer."
            ),
        })
    return decisions


# ---------- Contrôle des propositions du modèle ----------
def _nombre(x):
    try:
        v = float(str(x).strip().strip('"').replace(" ", ""))
        return None if v != v else v
    except ValueError:
        return None


def verifier_proposition(sig: dict, correction, ligne: dict, colonnes_signalees: set):

    colonne = sig["colonne"]
    texte = str(correction).strip()
    observee = str(sig["valeur_observee"]).strip().strip('"')
    actuelle = "" if pd.isna(ligne.get(colonne)) else str(ligne.get(colonne))


    n_cor = _nombre(texte)
    for ancienne in (observee, actuelle):
        if texte == ancienne:
            return False, "correction identique à la valeur actuelle"
        if colonne in COLONNES_NUMERIQUES:   # 14 et "14.0" sont la même valeur
            n_anc = _nombre(ancienne)
            if n_cor is not None and n_anc is not None and n_cor == n_anc:
                return False, "correction identique à la valeur actuelle"

    if colonne in VALEURS_AUTORISEES and texte not in VALEURS_AUTORISEES[colonne]:
        return False, "valeur hors liste autorisée"
    if colonne in FORMATS and not re.fullmatch(FORMATS[colonne], texte):
        return False, "format attendu non respecté"
    if colonne in ("date_commande", "date_livraison"):
        if pd.isna(pd.to_datetime(texte, format="%Y-%m-%d", errors="coerce")):
            return False, "date impossible"


    if colonne in COLONNES_NUMERIQUES:
        if n_cor is None:
            return False, "valeur non numérique"
        q, p, t = (_nombre(ligne.get(c)) for c in ("quantite", "prix_unitaire", "montant_total"))
        q_ok = q is not None and q > 0
        p_ok = p is not None and p > 0
        t_ok = t is not None and t > 0
        base_suspecte = colonnes_signalees & {"quantite", "prix_unitaire"}

        if colonne == "quantite":
            if not (t_ok and p_ok and abs(n_cor - t / p) < 0.01):
                return False, "non confirmée par total ÷ prix unitaire"
        elif colonne == "prix_unitaire":
            if not (t_ok and q_ok and abs(n_cor - t / q) < 0.01):
                return False, "non confirmé par total ÷ quantité"
        elif colonne == "montant_total":
            if base_suspecte:
                return False, "la quantité ou le prix de cette ligne sont eux-mêmes signalés"
            if not (q_ok and p_ok and abs(n_cor - q * p) < 0.01):
                return False, "différent de quantité × prix unitaire"
        elif colonne == "montant_paye":
            if base_suspecte:
                return False, "la quantité ou le prix de cette ligne sont eux-mêmes signalés"
            if n_cor < 0:
                return False, "un paiement ne peut pas être négatif"
            if q_ok and p_ok and n_cor > q * p + 0.01:
                return False, "supérieur à quantité × prix unitaire"

    return True, ""


def controler_reponses(reponses: list, signalements: list, ligne: dict) -> list:

    par_id = {str(s["id_signalement"]): s for s in signalements}
    colonnes_signalees = {s["colonne"] for s in signalements}
    resultat = []
    for d in reponses:
        sig = par_id.get(str(d["id_signalement"]))
        if sig is not None and d["action"] == "corriger":
            ok, motif = verifier_proposition(sig, d["correction_proposee"], ligne, colonnes_signalees)
            if not ok:
                d = {
                    **d,
                    "action": "verifier_manuellement",
                    "correction_proposee": "",
                    "justification": f"Correction du modèle rejetée par le contrôle ({motif}). "
                                     f"Avis initial : {d['justification']}",
                }
        resultat.append(d)
    return resultat


def revalider_decisions(rapport, ventes, decisions) -> dict:

    for numero, groupe in rapport.groupby("ligne_csv"):
        signalements = groupe.to_dict("records")
        ligne = ventes.loc[int(numero)].to_dict()
        existantes = [decisions[s["id_signalement"]] for s in signalements
                      if s["id_signalement"] in decisions]
        for d in controler_reponses(existantes, signalements, ligne):
            decisions[d["id_signalement"]] = d
    return decisions


# ---------- Traitement du rapport ----------
def traiter_rapport(rapport, ventes, client, limite=None, pause=2.0) -> dict:
    decisions = charger_progres()


    for d in decisions_telephones(rapport):
        decisions[d["id_signalement"]] = d
    for d in decisions_doublons(rapport, ventes):
        decisions.setdefault(d["id_signalement"], d)


    decisions = revalider_decisions(rapport, ventes, decisions)
    reecrire_progres(decisions)

    reste = rapport[(rapport["regle"] != "R-06")
                    & ~rapport["id_signalement"].isin(decisions)]
    groupes = reste.groupby("ligne_csv")
    if limite:
        groupes = islice(groupes, limite)

    for numero, groupe in groupes:
        ligne = ventes.loc[int(numero)].to_dict()
        signalements = groupe.to_dict("records")

        reponses = None
        for essai in range(2):
            try:
                reponses = analyser_signalements_ligne(client, ligne, signalements)
                break
            except RateLimitError:
                print(f" Limite atteinte (ligne {numero}), pause de 30 s...")
                time.sleep(30)
            except APIError as e:
                print(f" Erreur API (ligne {numero}) : {e}")
                break

        if reponses is None:
            print(f" Ligne {numero} ignorée pour l'instant.")
            continue

        reponses = controler_reponses(reponses, signalements, ligne)
        for d in reponses:
            decisions[d["id_signalement"]] = d
            sauvegarder_decision(d)
        print(f" Ligne {numero} traitée ({len(reponses)} signalement(s)).")
        time.sleep(pause)

    return decisions


def fusionner(rapport: pd.DataFrame, decisions: dict) -> pd.DataFrame:
    if not decisions:
        return rapport
    table = pd.DataFrame(list(decisions.values()))
    rapport = rapport.drop(columns=["action", "correction_proposee", "justification"],
                           errors="ignore")
    rapport = rapport.merge(table, on="id_signalement", how="left")

    rapport["statut"] = "À vérifier"
    rapport.loc[rapport["action"].notna(), "statut"] = "Proposition prête"
    rapport.loc[rapport["action"] == "conserver", "statut"] = "Aucune action requise"
    return rapport


if __name__ == "__main__":
    load_dotenv()
    client = Groq()
    ventes = pd.read_csv("ventes_anomalies.csv", keep_default_na=False, na_values="")
    rapport = pd.read_csv("rapport_anomalies.csv")

    decisions = traiter_rapport(rapport, ventes, client, limite=None)
    rapport_enrichi = fusionner(rapport, decisions)
    rapport_enrichi.to_csv("rapport_enrichi.csv", index=False, encoding="utf-8-sig")
    print(rapport_enrichi["statut"].value_counts())
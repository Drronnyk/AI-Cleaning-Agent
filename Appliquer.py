
import math
import re

import pandas as pd

from traitement import FORMATS, VALEURS_AUTORISEES

COLONNES_ENTIERES = ["quantite", "prix_unitaire", "montant_total", "montant_paye"]
COLONNES_JOURNAL = [
    "id_signalement", "ligne_csv", "colonne", "ancienne_valeur",
    "nouvelle_valeur", "action", "resultat", "motif",
]

def _vide(valeur) -> bool:
    return valeur is None or pd.isna(valeur) or str(valeur).strip() == ""


def _texte(valeur) -> str:
    return "" if _vide(valeur) else str(valeur)


def convertir_valeur(colonne: str, valeur_brute):
    """Convertit une correction au type de sa colonne et la contrôle.
    Renvoie (valeur, None) si tout va bien, ou (None, motif_du_refus)."""
    texte = str(valeur_brute).strip()

    if colonne in COLONNES_ENTIERES:
        try:
            nombre = float(texte.replace(" ", ""))
        except ValueError:
            return None, "valeur non numérique"
        if not math.isfinite(nombre):
            return None, "valeur non numérique"
        if nombre != round(nombre):
            return None, "nombre non entier"
        nombre = int(nombre)
        if colonne in ("quantite", "prix_unitaire") and nombre <= 0:
            return None, "doit être strictement positif"
        if nombre < 0:
            return None, "ne peut pas être négatif"
        return nombre, None

    if colonne in VALEURS_AUTORISEES and texte not in VALEURS_AUTORISEES[colonne]:
        return None, "valeur hors liste autorisée"
    if colonne in FORMATS and not re.fullmatch(FORMATS[colonne], texte):
        return None, "format attendu non respecté"
    if colonne in ("date_commande", "date_livraison"):
        if pd.isna(pd.to_datetime(texte, format="%Y-%m-%d", errors="coerce")):
            return None, "date impossible"
    return texte, None


def appliquer_corrections(df_ventes: pd.DataFrame, df_rapport: pd.DataFrame):

    ventes = df_ventes.copy()
    for col in COLONNES_ENTIERES:
        if col in ventes.columns:
            ventes[col] = ventes[col].astype("Int64")   # entiers avec vides autorisés

    retenues = df_rapport[df_rapport["statut"].isin(["Accepté", "Modifié"])]
    journal = []

    def noter(sig, idx, colonne, ancienne, nouvelle, action, resultat, motif=""):
        journal.append({
            "id_signalement": sig, "ligne_csv": idx, "colonne": colonne,
            "ancienne_valeur": ancienne, "nouvelle_valeur": nouvelle,
            "action": action, "resultat": resultat, "motif": motif,
        })

    a_supprimer = set()
    for _, d in retenues.iterrows():
        if d["statut"] == "Accepté" and d.get("action") == "supprimer":
            idx = int(d["ligne_csv"])
            if idx in ventes.index:
                a_supprimer.add(idx)
                noter(d["id_signalement"], idx, "TOUTES", "Ligne existante",
                      "SUPPRIMÉE", "supprimer", "appliquee")
            else:
                noter(d["id_signalement"], idx, "TOUTES", "", "", "supprimer",
                      "refusee", "ligne inconnue")

    cellules_modifiees = set()
    for _, d in retenues.iterrows():
        sig, action, statut = d["id_signalement"], d.get("action"), d["statut"]
        if statut == "Accepté" and action == "supprimer":
            continue                                    # déjà traité en passe 1

        idx, colonne = int(d["ligne_csv"]), d.get("colonne")

        if statut == "Modifié":
            valeur_brute, action_log = d.get("correction_finale"), "corriger"
        elif action == "corriger":
            valeur_brute, action_log = d.get("correction_proposee"), "corriger"
        else:
            noter(sig, idx, _texte(colonne), "", "", _texte(action),
                  "ignoree", "aucune modification à appliquer")
            continue

        if idx not in ventes.index:
            noter(sig, idx, _texte(colonne), "", _texte(valeur_brute), action_log,
                  "refusee", "ligne inconnue")
            continue
        if colonne not in ventes.columns:
            noter(sig, idx, _texte(colonne), "", _texte(valeur_brute), action_log,
                  "refusee", "colonne inconnue")
            continue

        ancienne = _texte(ventes.loc[idx, colonne])

        if _vide(valeur_brute):
            noter(sig, idx, colonne, ancienne, "", action_log, "refusee", "correction vide")
            continue
        if idx in a_supprimer:
            noter(sig, idx, colonne, ancienne, _texte(valeur_brute), action_log,
                  "ignoree", "la ligne est supprimée")
            continue
        if (idx, colonne) in cellules_modifiees:
            noter(sig, idx, colonne, ancienne, _texte(valeur_brute), action_log,
                  "ignoree", "conflit : cellule déjà modifiée par une autre décision")
            continue

        valeur, motif = convertir_valeur(colonne, valeur_brute)
        if motif:
            noter(sig, idx, colonne, ancienne, _texte(valeur_brute), action_log,
                  "refusee", motif)
            continue

        ventes.loc[idx, colonne] = valeur
        cellules_modifiees.add((idx, colonne))
        noter(sig, idx, colonne, ancienne, str(valeur), action_log, "appliquee")

    ventes = ventes.drop(index=list(a_supprimer))

    return ventes, pd.DataFrame(journal, columns=COLONNES_JOURNAL)

if __name__ == "__main__":
    ventes_test = pd.DataFrame({
        "id_commande": ["CMD-01", "CMD-02", "CMD-03", "CMD-04"],
        "ville": ["Douala", "douala", "Yaoundé", "Garoua"],
        "quantite": [10, 5, 2, 7],
        "prix_unitaire": [1500, 2000, 5000, 100],
        "montant_total": [15000, 10000, 10000, 700],
    })

    def dec(sig, ligne, colonne, action, proposee="", finale="", statut="Accepté"):
        return {"id_signalement": sig, "ligne_csv": ligne, "colonne": colonne, "action": action,
                "correction_proposee": proposee, "correction_finale": finale, "statut": statut}

    rapport_test = pd.DataFrame([
        dec("SIG-01", 1, "ville", "corriger", "Douala"),                          # appliquée
        dec("SIG-02", 1, "ville", "corriger", "Yaoundé"),                          # conflit
        dec("SIG-03", 1, "quantite", "corriger", "99", statut="Proposition prête"),  # non retenue
        dec("SIG-04", 0, "quantite", "corriger", "12", "14", statut="Modifié"),    # valeur humaine
        dec("SIG-05", 0, "prix_unitaire", "corriger", "DEUX MILLE"),               # refusée : texte
        dec("SIG-06", 2, "", "supprimer"),                                         # suppression
        dec("SIG-07", 2, "montant_total", "corriger", "5000"),                     # ligne supprimée
        dec("SIG-08", 3, "quantite", "corriger", "-4"),                            # refusée : négatif
        dec("SIG-09", 3, "montant_total", "corriger", ""),                         # refusée : vide
        dec("SIG-10", 3, "ville", "verifier_manuellement"),                        # sans effet
        dec("SIG-11", 3, "ville", "verifier_manuellement", "", "Bamenda", statut="Modifié"),  # humain
        dec("SIG-12", 0, "ville", "corriger", "Douala City"),                      # refusée : hors liste
    ])

    ventes_ok, journal = appliquer_corrections(ventes_test, rapport_test)
    pd.set_option("display.width", 200)
    print(ventes_ok, "\n", ventes_ok.dtypes.to_dict(), "\n")
    print(journal[["id_signalement", "colonne", "nouvelle_valeur", "resultat", "motif"]])
    print("\nOriginal intact :", ventes_test["quantite"].tolist())
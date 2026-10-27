import pandas as pd

from Appliquer import appliquer_corrections
from regles import Détecteurs

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)

LECTURE = dict(keep_default_na=False, na_values="")


ventes = pd.read_csv("ventes_anomalies.csv", **LECTURE)
rapport = pd.read_csv("rapport_enrichi.csv")

rapport.loc[rapport["action"].isin(["corriger", "supprimer"]), "statut"] = "Accepté"

ventes_corrigees, journal = appliquer_corrections(ventes, rapport)
ventes_corrigees.to_csv("ventes_corrigees.csv", index=False, encoding="utf-8-sig")
journal.to_csv("journal_modifications.csv", index=False, encoding="utf-8-sig")

print(f"Lignes : {len(ventes)} -> {len(ventes_corrigees)}")
print(journal["resultat"].value_counts())

ventes_relues = pd.read_csv("ventes_corrigees.csv", **LECTURE)


comptes = {}
for detecteur in Détecteurs:
    comptes[detecteur.__name__] = {
        "avant": len(detecteur(ventes)),
        "apres": len(detecteur(ventes_relues)),
    }

tableau = pd.DataFrame(comptes).T
tableau.loc["TOTAL"] = tableau.sum()
print(tableau)
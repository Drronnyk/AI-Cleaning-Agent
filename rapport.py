import pandas as pd
from regles import Détecteurs,natures
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

df = pd.read_csv("ventes_anomalies.csv", keep_default_na=False, na_values="")

# ----- Partie destiné à la generation du rapport global ------

colonnes_rapport = [
    "ligne_csv",
    "commande_id",
    "regle",
    "colonne",
    "valeur_observee",
    "explication",
]
resultats_anomalies = []
for detecteur in Détecteurs :
    anomalie_trouvée = detecteur(df)
    if not anomalie_trouvée.empty:
        resultats_anomalies.append(anomalie_trouvée[colonnes_rapport])


rapport_global = pd.concat(resultats_anomalies,ignore_index=True)
rapport_global["nature_signal"] = (
    rapport_global["regle"].map(natures)
)

rapport_global["statut"] = "À vérifier"
rapport_global = rapport_global.reset_index(drop=True)

rapport_global["id_signalement"] = rapport_global.index.map(lambda x: f"SIG-{x:03d}")

rapport_global["correction_proposee"] = ""
rapport_global["justification"] = ""
rapport_global["action"] = ""

ordre_colonnes = [
    "id_signalement",
    "ligne_csv",
    "commande_id",
    "regle",
    "nature_signal",
    "colonne",
    "valeur_observee",
    "explication",
    "statut",
    "correction_proposee",
    "justification",
    "action"
]
rapport_global = rapport_global[ordre_colonnes]


print(
    rapport_global.head(20)
)
print(rapport_global.groupby("nature_signal").size())

print("Nombre de signalements :", len(rapport_global))

rapport_global.to_csv("rapport_anomalies.csv", index=False, encoding="utf-8-sig")

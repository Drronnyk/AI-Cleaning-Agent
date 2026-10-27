import pandas as pd
df = pd.read_csv("ventes_anomalies.csv")


def analyser_qualite(df):
    rapport = {}

    # Structure générale
    rapport["nombre_lignes"] = len(df)
    rapport["nombre_colonnes"] = len(df.columns)

    # Valeurs manquantes
    rapport["valeurs_manquantes"] = int(
        df.isna().sum().sum()
    )

    # Doublons exacts
    rapport["doublons_exacts"] = int(
        df.duplicated().sum()
    )

    # Quantités invalides
    rapport["quantites_invalides"] = int(
        (df["quantite"] <= 0).sum()
    )

    # Prix unitaires invalides
    rapport["prix_invalides"] = int(
        (df["prix_unitaire"] <= 0).sum()
    )

    # Paiements négatifs
    rapport["paiements_negatifs"] = int(
        (df["montant_paye"] < 0).sum()
    )

    # Comparaison des paiements : uniquement si les
    # deux montants sont disponibles
    paiements_verifiables = df[
        ["montant_paye", "montant_total"]
    ].notna().all(axis=1)

    rapport["paiements_superieurs_total"] = int(
        (
            df.loc[paiements_verifiables, "montant_paye"]
            > df.loc[paiements_verifiables, "montant_total"]
        ).sum()
    )

    # Vérification des totaux uniquement lorsque
    # les trois valeurs nécessaires sont disponibles
    colonnes_total = [
        "quantite",
        "prix_unitaire",
        "montant_total"
    ]

    totaux_verifiables = df[colonnes_total].notna().all(axis=1)

    total_calcule = (
        df.loc[totaux_verifiables, "quantite"]
        * df.loc[totaux_verifiables, "prix_unitaire"]
    )

    ecarts = (
        df.loc[totaux_verifiables, "montant_total"]
        - total_calcule
    ).abs()

    rapport["totaux_incoherents"] = int(
        (ecarts > 0.01).sum()
    )

    return rapport


resultat = analyser_qualite(df)

print("\n--- RAPPORT DE QUALITÉ ---")

for controle, valeur in resultat.items():
    print(f"{controle} : {valeur}")

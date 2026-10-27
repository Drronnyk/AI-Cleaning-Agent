import pandas as pd

natures =  {
    "R-01": "Violation de règle métier",
    "R-02": "Violation de règle métier",
    "R-03": "Violation de règle métier",
    "R-04": "Incohérence chronologique",
    "R-05": "Répétition à examiner",
    "R-06": "Repetition Certaine",
    "R-07": "Violation de règle métier",
    "R-08": "Donnees manquantes obligatoires",
    "R-09": "Format de dates invalides",
    "R-10": "Format d'email ou de telephone invalides",
    "R-11": "Probleme de texte(casse,espace...)",
    "R-12": "Incoherence metier"


}



#1. Fonction de detection des paiements excessifs

def detecter_paiements_excessifs(df):
    masque = (
        df["montant_paye"].notna()
        & df["montant_total"].notna()
        & (df["montant_paye"] > df["montant_total"])
    )

    anomalies = df.loc[masque].copy()
    anomalies["ligne_csv"] = anomalies.index
    anomalies["regle"] = "R-01"
    anomalies["colonne"] = "montant_paye"
    anomalies["valeur_observee"] = anomalies["montant_paye"]
    anomalies["explication"] = (
        "Le paiement dépasse le montant total."
    )

    return anomalies

#2. Fonction de detection des quantites invalides.

def detecter_quantites_invalides(df):
    masque = df["quantite"].notna() & (df["quantite"] <= 0)

    anomalies = df.loc[masque].copy()
    anomalies["ligne_csv"] = anomalies.index
    anomalies["regle"] = "R-02"
    anomalies["colonne"] = "quantite"
    anomalies["valeur_observee"] = anomalies["quantite"]
    anomalies["explication"] = (
        "La quantité doit être strictement supérieure à zéro."
    )

    return anomalies



#3. Fonction de detection des prix invalides.
def detecter_prix_invalides(df):
    masque = df["prix_unitaire"].notna() & (df["prix_unitaire"] <= 0)
    anomalies = df.loc[masque].copy()
    anomalies["ligne_csv"] = anomalies.index
    anomalies["regle"] = "R-03"
    anomalies["colonne"] = "prix_unitaire"
    anomalies["valeur_observee"] = (anomalies["prix_unitaire"])
    anomalies["explication"] = (
        "Le prix unitaire ne peut etre nul ou negatif"
    )

    return anomalies


#4. Fonction de detection des dates de livraisons invalides.

def detecter_dates_livraisons(df):
    commandes =pd.to_datetime(
        df["date_commande"],
        errors="coerce",
        format="ISO8601" )
    livraisons = pd.to_datetime(
        df["date_livraison"],
        errors="coerce",
        format="ISO8601"
    )
    masque = (
        commandes.notna()&
        livraisons.notna()&
        (livraisons < commandes)
    )
    anomalies = df.loc[masque].copy()
    anomalies["ligne_csv"] = anomalies.index
    anomalies["regle"] = "R-04"
    anomalies["colonne"] = "date_livraison"
    anomalies["valeur_observee"] = anomalies["date_livraison"]
    anomalies["explication"] = (
        "La livraison est anterieure à la commande."
    )

    return anomalies


#5. Detection des identifiants repetees
def detecter_identifiants_repetées(df):
    masque = (
        df["commande_id"].notna()&
        df["commande_id"].duplicated(keep=False)
        & ~ df.duplicated(keep=False)
    )
    anomalies = df.loc[masque].copy()
    anomalies["ligne_csv"] = anomalies.index
    anomalies["regle"] = "R-05"
    anomalies["colonne"] = "commande_id"
    anomalies["valeur_observee"] = anomalies["commande_id"]
    anomalies["explication"] = (
        "Cet identifiant de Commande apparait plusieurs fois. Veuillez Verifier si la repetition est justifiée."
    )

    return anomalies
#6. Detection des doublons exacts
def detecter_doublons_exacts(df):
    masque = (
        df.duplicated(keep=False)
    )
    anomalies = df.loc[masque].copy()
    anomalies["ligne_csv"] = anomalies.index
    anomalies["regle"] = "R-06"
    anomalies["colonne"] = "commande_id"
    anomalies["valeur_observee"] = anomalies["commande_id"]
    anomalies["explication"] = (
        "Cet identifiant de Commande apparait plusieurs fois. Veuillez Verifier si la repetition est justifiée."
    )

    return anomalies
#7. Detection des totaux incoherents

def detecter_totaux_incoherents(df):
    colonnes_total = [
        "quantite",
        "prix_unitaire",
        "montant_total"
    ]
    totaux_verifiables = df[colonnes_total].notna().all(axis=1)
    total_calcule = df.loc[totaux_verifiables, "quantite"] * df.loc[totaux_verifiables, "prix_unitaire"]
    ecarts = (df.loc[totaux_verifiables, "montant_total"] - total_calcule).abs()

    masque = totaux_verifiables & (ecarts > 0.01)
    anomalies = df.loc[masque].copy()
    anomalies["ligne_csv"] = anomalies.index
    anomalies["regle"] = "R-07"
    anomalies["colonne"] = "montant_total"
    anomalies["valeur_observee"] = anomalies["montant_total"]
    anomalies["explication"] = (
        "Le montant total ne correspond pas au produit Quantite * Prix unitaire"
    )
    return anomalies


#8. Detection des donnees manquantes obligatoires.

def detecter_donnees_manquantes_obligatoires(df):
    colonnes_obligatoires = [
        "commande_id", "client_id", "nom_client", "ville", "date_commande",
        "produit", "categorie", "quantite", "prix_unitaire", "montant_total",
        "mode_paiement", "statut_paiement", "montant_paye", "statut_commande",
        "telephone_client"
    ]
    anomalies_par_colonne = []

    for colonne in colonnes_obligatoires:
        masque = df[colonne].isna()
        anomalies = df.loc[masque].copy()
        anomalies["ligne_csv"] = anomalies.index
        anomalies["regle"] = "R-08"
        anomalies["colonne"] = colonne
        anomalies["valeur_observee"] = "valeur vide"
        anomalies["explication"] = (
                f"la colonne obligatoire '{colonne}' ne peut pas etre vide. "
            )
        anomalies_par_colonne.append(anomalies)
    return pd.concat(anomalies_par_colonne)

#9. Detection des dates invalides ou impossible à lire.

def detecter_dates_invalides(df):
    colonnes_dates = ["date_commande", "date_livraison"]
    anomalies_par_colonne = []

    for colonne in colonnes_dates:
        converties = pd.to_datetime(
            df[colonne],
            errors="coerce",
            format="ISO8601"
        )
        non_vide = df[colonne].notna()
        format_correct = df[colonne].astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}")

        masque = non_vide & (~format_correct | converties.isna())
        anomalies = df.loc[masque].copy()
        anomalies["ligne_csv"] = anomalies.index
        anomalies["regle"] = "R-09"
        anomalies["colonne"] = colonne
        anomalies["valeur_observee"] = anomalies[colonne]
        anomalies["explication"] = (
            f"La date de la colonne '{colonne}' est illisible ou impossible (format ISO attendu)."
        )
        anomalies_par_colonne.append(anomalies)

    return pd.concat(anomalies_par_colonne)

#10. Detection des formats d'e-mail et de telephone invalides.

def detecter_formats_invalides(df):
    motifs = {
        "email_client": r"[^\s@]+@[^\s@]+\.[^\s@]+",
        "telephone_client": r"\+237 6\d{2} \d{2} \d{2} \d{2}",
    }
    anomalies_par_colonne = []

    for colonne, motif in motifs.items():
        format_correct = df[colonne].astype(str).str.fullmatch(motif)
        masque = df[colonne].notna() & ~format_correct

        anomalies = df.loc[masque].copy()
        anomalies["ligne_csv"] = anomalies.index
        anomalies["regle"] = "R-10"
        anomalies["colonne"] = colonne
        anomalies["valeur_observee"] = anomalies[colonne]
        anomalies["explication"] = (
            f"La valeur de la colonne '{colonne}' ne respecte pas le format attendu."
        )
        anomalies_par_colonne.append(anomalies)

    return pd.concat(anomalies_par_colonne)



#11. Detection des problemes de texte (espaces, casse, valeurs non autorisees).

def detecter_problemes_texte(df):
    colonnes_texte = [
        "nom_client", "ville", "produit", "categorie",
        "mode_paiement", "statut_paiement", "statut_commande"
    ]
    valeurs_autorisees = {
        "ville": ["Douala", "Yaoundé", "Bafoussam", "Garoua", "Bamenda", "Bertoua"],
        "categorie": ["Alimentaire", "Boissons", "Hygiène", "Électronique", "Papeterie", "Quincaillerie"],
        "mode_paiement": ["espèces", "Mobile Money", "virement", "carte bancaire"],
        "statut_paiement": ["payé", "partiellement payé", "impayé", "remboursé"],
        "statut_commande": ["en préparation", "expédiée", "livrée", "annulée", "retournée"],
    }
    resultats = []

    for colonne in colonnes_texte:
        brut = df[colonne].astype("string")
        propre = brut.str.strip()

        # 1) Espaces superflus
        masque_espaces = brut.notna() & (brut != propre)
        anomalies = df.loc[masque_espaces].copy()
        anomalies["ligne_csv"] = anomalies.index
        anomalies["regle"] = "R-11"
        anomalies["colonne"] = colonne
        anomalies["valeur_observee"] = '"' + brut[masque_espaces] + '"'
        anomalies["explication"] = (
            f"La colonne '{colonne}' contient des espaces au début ou à la fin."
        )
        resultats.append(anomalies)

        # 2) Valeurs non autorisees (seulement pour les colonnes a liste fermee)
        if colonne in valeurs_autorisees:
            autorisees = valeurs_autorisees[colonne]
            minuscules = [v.lower() for v in autorisees]

            masque_valeur = propre.notna() & ~propre.isin(autorisees)
            anomalies = df.loc[masque_valeur].copy()
            anomalies["ligne_csv"] = anomalies.index
            anomalies["regle"] = "R-11"
            anomalies["colonne"] = colonne
            anomalies["valeur_observee"] = propre[masque_valeur]

            casse = propre[masque_valeur].str.lower().isin(minuscules)
            anomalies["explication"] = casse.map({
                True: f"Casse incohérente dans '{colonne}'.",
                False: f"Valeur non autorisée dans '{colonne}' (faute de frappe probable).",
            })
            resultats.append(anomalies)

    return pd.concat(resultats)


def valeur_majoritaire(s):
    m = s.mode()
    return m.iloc[0] if not m.empty else pd.NA


#12. Detection des incoherences metier.
def detecter_incoherences_metier(df):
    resultats = []

    def signaler(masque, colonne, valeurs, message):
        a = df.loc[masque].copy()
        a["ligne_csv"] = a.index
        a["regle"] = "R-12"
        a["colonne"] = colonne
        a["valeur_observee"] = valeurs[masque]
        a["explication"] = message
        resultats.append(a)

    statut_cmd = df["statut_commande"].astype("string").str.strip()
    statut_pay = df["statut_paiement"].astype("string").str.strip()
    livraison = df["date_livraison"]
    paye = df["montant_paye"]
    resume = (statut_cmd.fillna("?") + " | " + statut_pay.fillna("?") + " | "
              + livraison.astype("string").fillna("date vide"))

    # --- A : statuts de commande / paiement / livraison ---
    cas = [
        (statut_cmd.isin(["livrée", "retournée"]) & livraison.isna(),
         "Commande livrée ou retournée sans date de livraison."),
        (statut_cmd.isin(["en préparation", "expédiée", "annulée"]) & livraison.notna(),
         "Date de livraison renseignée alors que la commande n'est pas livrée."),
        ((statut_cmd == "annulée") & statut_pay.notna() & ~statut_pay.isin(["impayé", "remboursé"]),
         "Commande annulée dont le paiement n'est ni impayé ni remboursé."),
        ((statut_cmd == "retournée") & statut_pay.notna() & (statut_pay != "remboursé"),
         "Commande retournée dont le paiement n'est pas remboursé."),
        ((statut_pay == "payé") & (paye == 0),
         "Paiement indiqué comme payé mais le montant payé est nul."),
        (statut_pay.isin(["impayé", "remboursé"]) & (paye > 0),
         "Paiement indiqué comme impayé ou remboursé mais le montant payé est positif."),
    ]
    for masque, message in cas:
        signaler(masque.fillna(False), "statut_commande", resume, message)

    # --- B : un produit = une seule categorie ---
    produit = df["produit"].astype("string").str.strip()
    categorie = df["categorie"].astype("string").str.strip()
    categories_valides = ["Alimentaire", "Boissons", "Hygiène", "Électronique", "Papeterie", "Quincaillerie"]
    cat_attendue = produit.map(categorie.groupby(produit).agg(valeur_majoritaire))
    masque = (produit.notna() & categorie.isin(categories_valides)
              & cat_attendue.notna() & (categorie != cat_attendue))
    signaler(masque.fillna(False), "categorie", df["categorie"],
             "Catégorie différente de celle habituellement associée à ce produit.")

    # --- C : un client_id = un seul nom et une seule ville ---
    for colonne in ["nom_client", "ville"]:
        valeur = df[colonne].astype("string").str.strip().str.lower()
        attendue = df["client_id"].map(valeur.groupby(df["client_id"]).agg(valeur_majoritaire))
        masque = valeur.notna() & attendue.notna() & (valeur != attendue)
        signaler(masque.fillna(False), colonne, df[colonne],
                 f"'{colonne}' différent de la valeur habituelle pour ce client_id.")

    # --- D : prix et quantites aberrants pour le produit ---
    prix = df["prix_unitaire"]
    med_prix = prix.where(prix > 0).groupby(produit).transform("median")
    masque = (prix > 0) & ((prix > 3 * med_prix) | (prix < med_prix / 3))
    signaler(masque.fillna(False), "prix_unitaire", prix,
             "Prix unitaire très éloigné du prix habituel de ce produit.")

    qte = df["quantite"]
    med_qte = qte.where(qte > 0).groupby(produit).transform("median")
    masque = (qte > 0) & (qte > 10 * med_qte)
    signaler(masque.fillna(False), "quantite", qte,
             "Quantité exceptionnellement élevée pour ce produit.")

    return pd.concat(resultats)





Détecteurs = [
    detecter_paiements_excessifs,
    detecter_quantites_invalides,
    detecter_prix_invalides,
    detecter_dates_livraisons,
    detecter_identifiants_repetées,
    detecter_doublons_exacts,
    detecter_totaux_incoherents,
    detecter_donnees_manquantes_obligatoires,
    detecter_dates_invalides,
    detecter_formats_invalides,
    detecter_problemes_texte,
    detecter_incoherences_metier
]

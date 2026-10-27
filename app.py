import pandas as pd
import streamlit as st

from Appliquer import appliquer_corrections, convertir_valeur

st.set_page_config(
    page_title="AI Data Cleaning Agent - Dashboard", layout="wide"
)
st.title("AI Data Cleaning Agent")

STATUT_ATTENTE = "Proposition prête"


@st.cache_data
def charger_donnees_initiales():
    ventes = pd.read_csv(
        "ventes_anomalies.csv", keep_default_na=False, na_values=""
    )
    rapport = pd.read_csv("rapport_enrichi.csv")
    if "statut" not in rapport.columns:
        rapport["statut"] = STATUT_ATTENTE
    if "correction_finale" not in rapport.columns:
        rapport["correction_finale"] = ""
    return ventes, rapport


df_ventes, df_rapport_init = charger_donnees_initiales()

if "rapport" not in st.session_state:
    st.session_state["rapport"] = df_rapport_init.copy()

df_rapport = st.session_state["rapport"]


# ---------- Décisions ----------
def enregistrer_decision(id_sig, nouveau_statut, corr_finale=""):
    idx = st.session_state["rapport"][
        st.session_state["rapport"]["id_signalement"] == id_sig
    ].index
    st.session_state["rapport"].loc[idx, "statut"] = nouveau_statut
    st.session_state["rapport"].loc[idx, "correction_finale"] = corr_finale


def changer_en_lot(ids, nouveau_statut):
    masque = st.session_state["rapport"]["id_signalement"].isin(ids)
    st.session_state["rapport"].loc[masque, "statut"] = nouveau_statut
    st.session_state["rapport"].loc[masque, "correction_finale"] = ""


def controler_saisie(colonne, saisie):
    """Renvoie un message d'erreur, ou "" si la saisie est valide.
    Utilise convertir_valeur : les mêmes règles que lors de l'application."""
    if str(saisie).strip() == "":
        return "La valeur ne peut pas être vide."
    _, motif = convertir_valeur(colonne, saisie)
    return motif or ""


def en_csv(df):
    return df.to_csv(index=False).encode("utf-8-sig")


COLONNES_TABLEAU = [
    "id_signalement", "regle", "colonne", "valeur_observee",
    "action", "correction_proposee", "statut",
]


# ---------- Fiche de détail d'un signalement ----------
def afficher_fiche_detail(df_a_afficher, cle, libelle_refus="Refuser"):
    if df_a_afficher.empty:
        st.info("Aucun signalement à afficher dans ce groupe.")
        return   # on quitte la fonction, pas le script : les autres onglets restent affichés

    mapping_options = {
        row["id_signalement"]: f"{row['id_signalement']} - {row['regle']} - {row['colonne']}"
        for _, row in df_a_afficher.iterrows()
    }
    id_choisi = st.selectbox(
        "Sélectionnez un signalement à traiter :",
        options=list(mapping_options.keys()),
        format_func=lambda x: mapping_options[x],
        key=f"choix_{cle}",
    )

    ligne_rapport = df_rapport[df_rapport["id_signalement"] == id_choisi].iloc[0]
    numero_ligne_csv = int(ligne_rapport["ligne_csv"])
    action_llm = ligne_rapport["action"]
    statut_actuel = ligne_rapport["statut"]
    colonne_cible = ligne_rapport["colonne"]
    proposee = "" if pd.isna(ligne_rapport["correction_proposee"]) else str(ligne_rapport["correction_proposee"])

    col_gauche, col_droite = st.columns(2)

    with col_gauche:
        st.subheader("Contexte de la ligne CSV")
        st.dataframe(df_ventes.loc[numero_ligne_csv].astype(str).to_frame(name="Valeur"))
        st.caption(f"Numéro de ligne correspondant dans Excel : {numero_ligne_csv + 2}")

    with col_droite:
        st.subheader("Détails de l'anomalie et analyse LLM")
        st.markdown(f"**Règle enfreinte :** {ligne_rapport['regle']}")
        st.markdown(f"**Colonne ciblée :** {colonne_cible}")
        st.markdown(f"**Valeur observée :** `{ligne_rapport['valeur_observee']}`")
        st.markdown(f"**Explication de l'anomalie :** {ligne_rapport['explication']}")
        st.info(f"""
        **Proposition du modèle :**
        - **Action :** `{action_llm}`
        - **Correction proposée :** `{proposee or '(aucune)'}`
        - **Justification :** {ligne_rapport['justification']}
        """)

        st.markdown("### Arbitrage humain")
        if statut_actuel not in (STATUT_ATTENTE, "Aucune action requise"):
            val_affichee = (
                ligne_rapport["correction_finale"] if statut_actuel == "Modifié" else proposee
            )
            st.success(
                f"**Décision déjà enregistrée :** `{statut_actuel}` (Valeur retenue : `{val_affichee}`)"
            )

        peut_accepter = action_llm in ["corriger", "supprimer"]
        boutons = st.columns(3 if peut_accepter else 2)
        if peut_accepter:
            boutons[0].button(
                "Accepter", key=f"acc_{id_choisi}",
                on_click=enregistrer_decision, args=(id_choisi, "Accepté"),
            )
            boutons = boutons[1:]
        boutons[0].button(
            libelle_refus, key=f"ref_{id_choisi}",
            on_click=enregistrer_decision, args=(id_choisi, "Refusé"),
        )
        boutons[1].button(
            "Réinitialiser", key=f"rst_{id_choisi}",
            on_click=enregistrer_decision, args=(id_choisi, STATUT_ATTENTE),
        )

        # Saisie manuelle : pas pour une suppression
        if action_llm in ["corriger", "verifier_manuellement"]:
            if action_llm == "corriger":
                st.markdown("**Option alternative : spécifier une valeur manuelle**")
                valeur_defaut = proposee
            else:
                st.markdown("**Saisie manuelle (tranchage humain) :**")
                valeur_defaut = ""
            saisie = st.text_input(
                "Valeur corrigée :", value=valeur_defaut, key=f"input_{id_choisi}"
            )
            motif_erreur = controler_saisie(colonne_cible, saisie)
            if saisie.strip() and motif_erreur:
                st.error(motif_erreur)
            st.button(
                "Enregistrer ma valeur", key=f"mod_{id_choisi}",
                on_click=enregistrer_decision, args=(id_choisi, "Modifié", saisie),
                disabled=bool(motif_erreur),
            )


# ---------- Un onglet par groupe d'actions ----------
def afficher_groupe(action, cle, titre, avec_lot=False, libelle_refus="Refuser"):
    groupe = df_rapport[df_rapport["action"] == action]
    if filtre_regle:
        groupe = groupe[groupe["regle"].isin(filtre_regle)]
    en_attente = groupe[groupe["statut"] == STATUT_ATTENTE]

    st.header(titre)
    st.write(f"**{len(en_attente)}** en attente sur **{len(groupe)}** dans ce groupe.")

    if avec_lot:
        ids_attente = en_attente["id_signalement"].tolist()
        ids_acceptes = groupe.loc[groupe["statut"] == "Accepté", "id_signalement"].tolist()
        c1, c2 = st.columns(2)
        c1.button(
            f"Accepter les {len(ids_attente)} propositions en attente",
            key=f"lot_{cle}", on_click=changer_en_lot, args=(ids_attente, "Accepté"),
            disabled=not ids_attente,
        )
        c2.button(
            f"Remettre en attente les {len(ids_acceptes)} acceptés",
            key=f"annul_{cle}", on_click=changer_en_lot, args=(ids_acceptes, STATUT_ATTENTE),
            disabled=not ids_acceptes,
        )

    voir_traites = st.checkbox("Afficher aussi les cas déjà traités", key=f"traites_{cle}")
    a_afficher = groupe if voir_traites else en_attente

    if a_afficher.empty and not voir_traites and len(groupe) > 0:
        st.success("Tous les cas de ce groupe sont traités.")
    st.dataframe(a_afficher[COLONNES_TABLEAU])
    st.markdown("---")
    afficher_fiche_detail(a_afficher, cle, libelle_refus)


# ---------- Anomalies restantes ----------
def anomalies_restantes():
    rapport = st.session_state["rapport"]
    supprimees = set(rapport.loc[(rapport["action"] == "supprimer")
                                 & (rapport["statut"] == "Accepté"), "ligne_csv"])
    restantes = rapport[
        ~rapport["statut"].isin(["Accepté", "Modifié", "Aucune action requise"])
        & ~rapport["ligne_csv"].isin(supprimees)
    ]
    if "journal" in st.session_state:   # décisions acceptées mais refusées à l'application
        journal = st.session_state["journal"]
        ids_refuses = journal.loc[journal["resultat"] == "refusee", "id_signalement"]
        restantes = pd.concat([restantes, rapport[rapport["id_signalement"].isin(ids_refuses)]])
    restantes = restantes.drop_duplicates(subset="id_signalement").copy()
    restantes["ligne_excel"] = restantes["ligne_csv"] + 2
    colonnes = ["id_signalement", "ligne_excel", "commande_id", "regle", "colonne",
                "valeur_observee", "explication", "statut", "justification"]
    return restantes[colonnes]


# ---------- Appliquer et exporter ----------
def afficher_application():
    st.header("Appliquer les décisions")

    nb_retenues = int(df_rapport["statut"].isin(["Accepté", "Modifié"]).sum())
    st.metric("Décisions retenues (acceptées ou modifiées)", nb_retenues)

    if st.button("Appliquer les décisions validées", key="btn_appliquer",
                 disabled=(nb_retenues == 0)):
        ventes_ok, journal = appliquer_corrections(df_ventes, st.session_state["rapport"])
        st.session_state["ventes_corrigees"] = ventes_ok
        st.session_state["journal"] = journal
        st.session_state["rapport_applique"] = st.session_state["rapport"].copy()

    if "journal" in st.session_state:
        ventes_ok = st.session_state["ventes_corrigees"]
        journal = st.session_state["journal"]

        if not st.session_state["rapport_applique"].equals(st.session_state["rapport"]):
            st.warning("Tes décisions ont changé depuis la dernière application : "
                       "clique à nouveau sur « Appliquer » pour mettre le résultat à jour.")

        st.subheader("Résultat")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Lignes avant", len(df_ventes))
        c2.metric("Lignes après", len(ventes_ok))
        c3.metric("Modifications appliquées", int((journal["resultat"] == "appliquee").sum()))
        c4.metric("Refusées", int((journal["resultat"] == "refusee").sum()))

        refusees = journal[journal["resultat"] == "refusee"]
        if not refusees.empty:
            st.warning("Certaines décisions n'ont pas pu être appliquées :")
            st.dataframe(refusees)

        st.subheader("Journal des modifications")
        st.dataframe(journal)

        st.subheader("Téléchargements du nettoyage")
        st.download_button("Télécharger ventes_corrigees.csv", en_csv(ventes_ok),
                           file_name="ventes_corrigees.csv", mime="text/csv", key="dl_ventes")
        st.download_button("Télécharger journal_modifications.csv", en_csv(journal),
                           file_name="journal_modifications.csv", mime="text/csv", key="dl_journal")

    st.markdown("---")
    st.subheader("Suivi")
    restantes = anomalies_restantes()
    st.write(f"**{len(restantes)}** anomalies ne sont pas résolues à ce stade.")
    st.download_button("Télécharger les anomalies restantes (pour l'équipe métier)",
                       en_csv(restantes), file_name="anomalies_restantes.csv",
                       mime="text/csv", key="dl_restantes")
    st.download_button("Télécharger le rapport avec mes décisions", en_csv(df_rapport),
                       file_name="rapport_decisions.csv", mime="text/csv", key="dl_rapport")


# ---------- Page ----------
actionnables = df_rapport[df_rapport["action"] != "conserver"]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total signalements", len(df_rapport))
c2.metric("En attente", int((actionnables["statut"] == STATUT_ATTENTE).sum()))
c3.metric("Acceptés", int((df_rapport["statut"] == "Accepté").sum()))
c4.metric("Modifiés", int((df_rapport["statut"] == "Modifié").sum()))
c5.metric("Refusés", int((df_rapport["statut"] == "Refusé").sum()))

nb_conserver = int((df_rapport["action"] == "conserver").sum())
if nb_conserver:
    st.caption(f"{nb_conserver} lignes originales sont conservées sans action : "
               "leurs copies sont dans l'onglet « À supprimer ».")

st.sidebar.header("Filtres d'affichage")
filtre_regle = st.sidebar.multiselect(
    "Filtrer par Règle", options=sorted(df_rapport["regle"].unique().tolist())
)

onglet_corriger, onglet_supprimer, onglet_verifier, onglet_application = st.tabs(
    ["À corriger", "À supprimer", "À vérifier", "Appliquer et exporter"]
)

with onglet_corriger:
    afficher_groupe("corriger", "corriger", "Corrections proposées", avec_lot=True)

with onglet_supprimer:
    afficher_groupe("supprimer", "supprimer", "Suppressions proposées (copies exactes)", avec_lot=True)

with onglet_verifier:
    afficher_groupe("verifier_manuellement", "verifier", "Cas à trancher par un humain",
                    libelle_refus="Laisser tel quel")

with onglet_application:
    afficher_application()
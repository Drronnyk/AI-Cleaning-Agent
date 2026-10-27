# ventes_anomalies.csv — Dictionnaire et règles métier

Jeu de données synthétique (326 lignes, 17 colonnes, UTF-8, séparateur virgule) simulant les commandes d'une petite entreprise de distribution au Cameroun. Devise : franc CFA (XAF). Toutes les données sont fictives.

Les valeurs manquantes sont des champs CSV vides (lus comme `NaN` par Pandas).

## 1. Dictionnaire des colonnes

| Colonne | Type attendu | Valeurs / format attendus |
|---|---|---|
| `commande_id` | texte | Unique, format `CMD-0001` |
| `client_id` | texte | Répétable, format `CLI-001` |
| `nom_client` | texte | Nom fictif d'une personne ou d'une entreprise |
| `ville` | texte (catégoriel) | Douala, Yaoundé, Bafoussam, Garoua, Bamenda, Bertoua |
| `date_commande` | date | ISO `YYYY-MM-DD` |
| `produit` | texte | 30 produits au catalogue |
| `categorie` | texte (catégoriel) | Alimentaire, Boissons, Hygiène, Électronique, Papeterie, Quincaillerie |
| `quantite` | entier | > 0 |
| `prix_unitaire` | entier | > 0, en XAF |
| `montant_total` | entier | En XAF |
| `mode_paiement` | texte (catégoriel) | espèces, Mobile Money, virement, carte bancaire |
| `statut_paiement` | texte (catégoriel) | payé, partiellement payé, impayé, remboursé |
| `montant_paye` | entier | ≥ 0, en XAF |
| `statut_commande` | texte (catégoriel) | en préparation, expédiée, livrée, annulée, retournée |
| `email_client` | texte | Adresse valide, facultatif |
| `telephone_client` | texte | Format `+237 6XX XX XX XX` |
| `date_livraison` | date | ISO `YYYY-MM-DD`, facultative selon le statut |

## 2. Règles métier prévues

### Identifiants
- `commande_id` est unique.
- `client_id` peut se répéter : un client peut passer plusieurs commandes.
- Un même `client_id` garde toujours le même nom et la même ville.

### Montants
- `quantite` est un entier strictement positif.
- `prix_unitaire` est strictement positif.
- `montant_total = quantite × prix_unitaire`.
- `montant_paye` n'est jamais négatif et ne dépasse pas `montant_total`.
- Chaque produit appartient à une seule catégorie et garde un prix cohérent d'une commande à l'autre.

### Paiement
- « payé » : `montant_paye = montant_total`.
- « partiellement payé » : `0 < montant_paye < montant_total`.
- « impayé » : `montant_paye = 0`.
- « remboursé » : `montant_paye = 0` (montant net après remboursement).

### Statuts et dates
- `date_livraison ≥ date_commande`.
- Commande « livrée » ou « retournée » : `date_livraison` renseignée.
- Commande « en préparation », « expédiée » ou « annulée » : pas de `date_livraison`.
- Commande « annulée » : statut de paiement « impayé » ou « remboursé ».
- Commande « retournée » : statut de paiement « remboursé ».

### Formats et valeurs autorisées
- Dates au format ISO `YYYY-MM-DD`.
- Les e-mails respectent une structure valide.
- Les téléphones suivent le format `+237 6XX XX XX XX`.
- Les valeurs catégorielles appartiennent aux ensembles définis ci-dessus, sans espaces superflus ni variation de casse.

### Cas qui ne sont pas des anomalies
- Clients qui reviennent avec plusieurs commandes.
- Commandes partiellement payées.
- E-mail absent (champ facultatif).
- Date de livraison absente pour une commande non livrée.
- Montants liés à un remboursement.

## 3. Catégories d'anomalies injectées

Environ 21 % des lignes comportent au moins une anomalie ; certaines en cumulent plusieurs, et la majorité des lignes reste valide.

| Famille | Anomalies |
|---|---|
| Structurelles | Valeurs manquantes (fréquences variées), doublons exacts, `commande_id` dupliqués avec contenus différents |
| Numériques | Prix nuls ou négatifs, quantités nulles, négatives ou extrêmes, totaux incorrects, montants payés supérieurs au total |
| Dates | Formats variés ou impossibles, livraison antérieure à la commande |
| Texte | Casse variable, espaces superflus, fautes de frappe dans statuts, catégories et modes de paiement |
| Formats | E-mails mal formés, téléphones de formats incohérents |
| Règles métier (subtiles) | Statuts incohérents entre commande, paiement et livraison ; prix aberrants par rapport au produit ; catégorie ne correspondant pas au produit ; nom ou ville différents pour un même client |

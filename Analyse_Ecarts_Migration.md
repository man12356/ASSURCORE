# Analyse d'Écart Exhaustive : Migration Oracle → Odoo AssurCore

Cette analyse couvre **la totalité des 49 fichiers** présents dans le répertoire `\DATA_TEST`. Elle identifie les tables contenant réellement des données (qui doivent être migrées) et celles qui sont vides (fonctionnalités non utilisées dans l'ancien système).

## 1. Tables de Paramétrage Global (À paramétrer dans Odoo)

* **`PR_PARAMETRE` (1 ligne)** : Contient les valeurs globales comme `VAL_TAUX_TVA` et `TIMBRE_FISCAL`. 
  * *Odoo :* Déjà mappé sur les taxes comptables (`account.tax`) rattachées à la compagnie (`res.company`).
* **`PR_CODE_OPERATION` (87 lignes)** : Liste des 87 codes d'opération et leurs honoraires par défaut.
  * *Odoo :* Manquant. À créer (`insurance.operation.code`).
* **`PR_RISQUE` (37 lignes)** : Catégories de risques par branche (Auto, Incendie, etc.).
  * *Odoo :* Manquant. À créer (`insurance.risk`).
* **`PR_BANQUE` (11 lignes)** et **`PR_COMPTE_BANCAIRE` (3 lignes)** : Les banques tunisiennes.
  * *Odoo :* Modèle `insurance.bank` existant, à alimenter.
* **`PR_COMPAGNIE` (13 lignes)** :
  * *Odoo :* Déjà migré (`insurance.company`).

## 2. Utilisateurs, Droits et Commerciaux (À configurer manuellement)

* **`PR_UTILISATEUR` (8 lignes)**, **`PR_USER_MODULE` (248 lignes)**, **`PR_DROIT_MENU` (23 lignes)**, **`PR_DROIT_BOUTON` (18 lignes)**, **`PR_MODULE` (31 lignes)** : Toute la gestion des accès Oracle.
  * *Odoo :* Ne se migre pas tel quel. Odoo utilise des Groupes (`res.groups`) et des règles de sécurité (`ir.rule`). Il suffira de créer les 8 utilisateurs et de leur affecter les bons profils (Admin, Gestionnaire, etc.).
* **`PR_COMMERCIAL` (3 lignes)** : Vos apporteurs d'affaires.
  * *Odoo :* À mapper sur les utilisateurs standards.

## 3. Données de Production Principales (Le Cœur de la Migration)

Ce sont les données massives qui nécessitent un nouveau script d'importation (ETL) :

* **`PR_CLIENT` (3 726 lignes)** : Toutes les coordonnées, CIN, Matricules Fiscaux. 
  * *Odoo :* À fusionner/mettre à jour avec les `res.partner` actuels.
* **`PR_POLICE` (7 411 lignes)** : Les contrats. 
  * *Odoo :* Déjà importé.
* **`PR_OPERATION` (17 108 lignes)** : Les mouvements sur polices. 
  * *Odoo :* Déjà importé, et nous venons de générer les Quittances.
* **`PR_OPERATION_FACTUREE_ANNULEE` (3 598 lignes)** : Historique des annulations.
  * *Odoo :* Doit être importé en tant qu'opérations annulées pour garder l'historique exact.
* **`PR_REGELEMENT` (15 767 lignes)** : L'historique des chèques, espèces et virements.
  * *Odoo :* À importer dans `insurance.settlement`.

## 4. Comptabilité et Lettrage (Nouveau point critique identifié !)

J'ai trouvé les tables qui expliquent comment l'ancien système gérait le lettrage (Imputation) entre les Règlements et les Factures :

* **`PR_FACTURE` (15 738 lignes)** : L'historique des factures de primes.
  * *Odoo :* Ces factures (`account.move`) doivent être recréées à l'identique pour correspondre aux quittances.
* **`PR_REG_FACTURE` (16 561 lignes)** : C'est la table de **Lettrage**. Elle lie spécifiquement le `NUM_REG_CLT` (Règlement) au `NUM_FACTURE` (Facture). 
  * *Odoo :* Crucial ! Lors de l'import, c'est cette table qui permettra de lier les Règlements Odoo aux Factures Odoo et de calculer les vrais soldes (sans ça, tous les clients seraient débiteurs !).
* **`PR_COMPTE_CLIENT` (19 283 lignes)** et **`PR_SOLDE_CLIENT` (3 646 lignes)** : L'extrait de compte client Oracle avec débits/crédits.
  * *Odoo :* Inutile de les importer telles quelles, car Odoo recalculera automatiquement les soldes exacts une fois les Règlements lettrés sur les Factures via `PR_REG_FACTURE`.

## 5. Sinistres et Experts (Très peu utilisés)

* **`PR_SINISTRE` (1 ligne)** et **`PR_EXPERT` (1 ligne)** : Votre ancien système ne contient qu'un seul sinistre et un seul expert !
  * *Odoo :* Inutile de faire un développement massif de migration pour ça. Vous pourrez les recréer manuellement en 2 minutes. Les tables `PR_FACTURE_EXPERT`, `PR_TEXTE_SINISTRE`, etc., sont vides.

## 6. Fonctionnalités Vides (Abandonnées)

Les 25 autres tables (soit 50% du dictionnaire de données) sont **strictement vides (0 ligne)**. Cela prouve que ces modules n'ont jamais été utilisés ou ont été abandonnés :
* **Journées d'encaissement et Dépenses** : `PR_JOUR_ENC`, `PR_JOURNAL_DEPENSE`, `PR_FACT_JOUR_ENC`, etc.
* **Services Additionnels** : `PR_SERVICE_DATA_TABLE`, `PR_CODE_SERVICE`, etc.
* **Envois Compagnies (Bordereaux de reversement automatiques)** : `PR_ENVOI_COMPAGNIE`.
* **Avoirs** : `PR_AVOIR`, `PR_PAYEMENT_AVOIR`.

---

## Bilan et Plan d'Action Recommandé

L'analyse confirme que la priorité absolue pour finaliser la migration est le développement du **Script d'import de Comptabilité Client**.

1. **Phase 1 (Modèles)** : Mettre à jour Odoo avec les modèles `Risque` et `Code Opération`.
2. **Phase 2 (Mise à jour Clients)** : Importer `PR_CLIENT` pour remplir les adresses, CIN, et téléphones des clients existants.
3. **Phase 3 (Facturation & Lettrage - Le plus lourd)** : 
   * Créer les factures comptables à partir de `PR_FACTURE`.
   * Importer les Règlements à partir de `PR_REGELEMENT`.
   * Effectuer le lettrage Odoo automatiquement grâce à `PR_REG_FACTURE` pour que le "Reste à payer" de chaque client retombe juste.

Voulez-vous que l'on commence par la Phase 1 (ajouter Risques et Codes Opérations au système) ou que l'on attaque directement la Phase 2 et 3 (le script pour la comptabilité client) ?

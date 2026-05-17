# Contexte Général
Tu es un expert technique Odoo 17 et Python. Ta mission est de finaliser la migration complète d'une ancienne application métier métier d'assurance (Oracle) vers un nouveau module Odoo 17 nommé `assurcore`. Le client est extrêmement exigeant : **aucune perte d'information n'est tolérée**, même pour les tables ne contenant qu'une seule ligne d'historique.

Les données sources se trouvent dans un répertoire `\DATA_TEST` sous forme de fichiers `.tsv`. Le schéma a été extrait et analysé. 

Une première migration a déjà créé les Polices (`insurance.policy`), les Opérations (`insurance.operation`) et les Quittances (`insurance.receipt`). Cependant, l'architecture Odoo actuelle est incomplète par rapport à l'ancienne, et toute la partie financière (Clients, Factures, Règlements, Lettrage, Sinistres, Experts) manque.

---

# MISSION 1 : Mise à niveau de l'architecture Odoo (Développement)

L'ancien système utilisait des tables de paramétrage que nous avions simplifiées en champs "Texte" ou "Sélection" dans Odoo. Le client exige que ces tables soient recréées sous forme de modèles relationnels complets.

Tu dois fournir le code Python/XML pour créer ou mettre à jour les modèles suivants dans le module `assurcore` :

1. **Les Risques (`insurance.risk`)** :
   * Doit remplacer l'actuel champ `risque` (Char) sur `insurance.policy`.
   * Champs : `name` (Désignation), `branche_id` (Lien vers `insurance.branch`).
   * Correspond à l'ancienne table `PR_RISQUE`.

2. **Les Codes Opérations (`insurance.operation.code`)** :
   * Doit remplacer l'actuel champ `code_operation` (Selection) sur `insurance.operation`.
   * Champs : `name` (ex: EMI, REN), `designation`, `description`, `libelle_honoraire`.
   * Correspond à l'ancienne table `PR_CODE_OPERATION`.

3. **Les Experts (`insurance.expert` ou via `res.partner`)** :
   * Doit gérer les experts en assurance (Nom, Prénom, Téléphone, Adresse, Ville).
   * Correspond à l'ancienne table `PR_EXPERT`.

4. **Les Sinistres (`insurance.claim`)** :
   * Mettre à jour le modèle pour inclure le lien `expert_id` vers l'expert assigné.
   * Ajouter les champs manquants provenant de `PR_SINISTRE` (Catégorie indemnisation, Montant indemnité, Honoraires expert, etc.).

---

# MISSION 2 : Développement du Script ETL de Migration (`import_assurcore_v2.py`)

Tu dois concevoir un script Python (utilisant XML-RPC ou exécutable via `odoo shell`) capable de lire les fichiers `.tsv` du répertoire `\DATA_TEST` et d'importer les données manquantes de manière **idempotente** et robuste (par lots/batches).

Voici l'ordre strict d'injection et les spécifications de mapping pour le script :

### Étape 1 : Le Paramétrage et les Référentiels
* Importer `PR_RISQUE_DATA_TABLE.tsv` vers `insurance.risk`.
* Importer `PR_CODE_OPERATION_DATA_TABLE.tsv` vers `insurance.operation.code`.
* Importer `PR_EXPERT_DATA_TABLE.tsv` vers la base des experts.

### Étape 2 : Mise à jour exhaustive des Clients
* Table source : `PR_CLIENT_DATA_TABLE.tsv` (3726 lignes).
* Action : Mettre à jour les `res.partner` existants (déjà créés partiellement lors de la phase 1) pour y injecter toutes les coordonnées manquantes (CIN, RC, MF, Adresse, Villes, Téléphones, Email). Le lien se fait via le `NUM_CLIENT`.

### Étape 3 : La Comptabilité et le Lettrage (CRITIQUE)
C'est le cœur du système. Les soldes clients d'Odoo doivent correspondre exactement à l'ancien système (`PR_SOLDE_CLIENT`).
* **Factures** (`PR_FACTURE_DATA_TABLE.tsv`) : Créer les `account.move` correspondantes (invoices).
* **Règlements** (`PR_REGELEMENT_DATA_TABLE.tsv`) : Créer les `insurance.settlement` (ou `account.payment`).
* **Lettrage / Imputation** (`PR_REG_FACTURE_DATA_TABLE.tsv`) : C'est la table de liaison ! Le script doit impérativement lier le Règlement à la Facture dans Odoo (créer la réconciliation `account.partial.reconcile` ou utiliser les méthodes Odoo de lettrage) pour que les factures passent au statut "Payé" et que le Reste à Payer du client soit juste.

### Étape 4 : Les Sinistres et Experts (Exigence Client)
* Table source : `PR_SINISTRE_DATA_TABLE.tsv` (même s'il n'y a qu'une ligne).
* Action : Créer le sinistre (`insurance.claim`), l'associer à la bonne police et au bon expert.

---

# Contraintes Techniques
1. Ton script Python doit inclure un système de **logging avancé** et un mode **`--dry-run`**.
2. Tu dois gérer les **dates** (format `DD/MM/YY` ou `DD/MM/YYYY`) et les **montants financiers** (virgules comme séparateur décimal si nécessaire).
3. Utilise l'idempotence (`search` avant `create` ou utilisation du champ `ref` (Ex: `ORA-CLIENT-123`, `ORA-FACT-456`)) pour éviter tout doublon si le script est interrompu.

Tu es attendu sur la qualité professionnelle du code Odoo et du script Python. Rédige ta réponse en fournissant d'abord le code des modèles Odoo (XML/Python), puis le script complet d'importation ETL.

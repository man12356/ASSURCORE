# SPEC EVO03 — Bordereaux de Versement & Règlements Encaissés

**Projet :** AssurCore – Migration Oracle → Odoo  
**Date :** 14/06/2026  
**Statut :** Spécification fonctionnelle v1.1  
**Branche cible :** `evo03-bordereaux-encaissement`

---

## 1. Contexte & Problématique

À l'issue d'EVO02, un règlement (espèces, chèque, traité ou compensation) est créé et imputé sur des mémoires/quittances. Mais **l'encaissement réel n'est pas contrôlé** : le système ne distingue pas un règlement saisie d'un règlement effectivement en caisse.

Le client demande que **tout règlement soit considéré "en instance" jusqu'à preuve de son encaissement effectif**, matérialisé par :
1. Son inclusion dans un **bordereau de versement** remis à la banque.
2. La **confirmation bancaire** (rapprochement avec relevé bancaire / décharge).

Cas particulier : les **règlements par compensation** (crédit sinistre utilisé pour payer des primes) ne passent pas par la banque — ils sont encaissés directement par écriture interne.

---

## 2. Périmètre Fonctionnel

| Axe | Description |
|-----|-------------|
| **A1** | Bordereau de versement : regroupement des règlements par (mode + établissement) pour remise en banque/caisse |
| **A2** | Rapprochement bancaire : confirmation encaissement vs relevé bancaire + suivi des non-encaissés |
| **A3** | Règlements par compensation : solde crédit sinistre utilisé comme mode de paiement de primes |
| **A4** | Vue liste clients enrichie : colonnes financières consolidées par client (règlements par statut, imputations, solde à imputer, anomalie) |

---

## 3. Machine à États des Règlements

### 3.1 Nouveaux états

```
                    ┌──────────────────────────────────┐
  Saisie            │                                  │
  règlement ──────► │  en_instance                     │
                    │  (par défaut pour tout nouveau   │
                    │   règlement non-compensation)    │
                    └────────┬──────────────┬──────────┘
                             │              │ Déclarer perdu (avant dépôt)
                             │              ▼
                             │     ┌─────────────────┐
                             │     │     perdu        │
                             │     │  (titre perdu,  │
                             │     │  avant dépôt)   │
                             │     └────────┬────────┘
                             │              │ Remplacement
                             ▼              ▼
                    ┌──────────────────────────────────┐
                    │  en_cours_versement               │
                    │  (bordereau déposé/remis banque) │
                    └────────┬──────────────┬──────────┘
                             │              │ Déclarer perdu (après dépôt)
                             │              ▼
                             │     ┌─────────────────┐
                             │     │     perdu        │
                             │     │  (titre perdu,  │
                             │     │  après dépôt)   │
                             │     └────────┬────────┘
                             │              │ Remplacement
                             ▼              ▼
                    ┌────────┴────────┐ ┌──────────────────┐
                    │  encaisse       │ │     rejete        │
                    │  (confirmé      │ │  (non honoré,    │
                    │   banque)       │ │   retourné)      │
                    └────────┬────────┘ └──────────────────┘
                             │ Imputation (lettrage EVO02)
                             ▼
                    ┌─────────────────┐
                    │      regle      │  (quittances apurées)
                    └─────────────────┘

  Compensation :
  Saisie ──► en_instance ──► encaisse  (validation interne, sans bordereau)
```

### 3.2 Mapping états Oracle → Odoo (complété)

| Oracle       | Odoo (EVO02) | Odoo (EVO03)        |
|-------------|--------------|---------------------|
| IMPAYE      | impaye       | impaye (inchangé)   |
| ENCAISSE    | encaisse     | encaisse (inchangé) |
| IMPUTER     | regle        | regle (inchangé)    |
| (nouveau)   | brouillon    | **en_instance**     |
| (nouveau)   | —            | **en_cours_versement** |
| (nouveau)   | —            | **rejete**          |
| (nouveau)   | —            | **perdu**           |

> **Règle migration historique :** les règlements Oracle avec état ENCAISSE restent `encaisse`. Les règlements sans état clair (brouillon) passent à `en_instance` par défaut.

---

## 4. Modèle de Données

### 4.1 Mapping TYPE_REG Oracle → mode de paiement Odoo

Issu de l'analyse des données réelles Oracle (21 773 règlements) :

| CODE Oracle | Libellé | Nb | Mode Odoo | Bordereau requis | Confirmation encaissement |
|------------|---------|-----|-----------|-----------------|--------------------------|
| `C` | Chèque | 11 262 | `cheques` | **Oui** | Rapprochement bordereau vs relevé bancaire |
| `E` | Espèces | 7 623 | `especes` | **Oui** (Circuit A allégé) | Banque : relevé bancaire / Caisse interne : décharge caissier signée |
| `V` | Virement client | 1 844 | `virement` | Non (Circuit B) | Relevé bancaire + justificatif obligatoire |
| `T` | Traité | 1 024 | `traites` | **Oui** | Rapprochement bordereau vs relevé bancaire |
| `A` | Avoir | 18 | `compensation` | **Non** | Validation interne responsable |
| `R` | Remboursement | 2 | `compensation` | **Non** | Validation interne responsable |
| — | Paiement internet | 0 | `paiement_internet` | Non (Circuit B) | Notification plateforme + justificatif obligatoire (EVO future pour workflow spécifique) |

### Deux circuits d'encaissement

```
Circuit A — Avec bordereau physique (chèques / traités / espèces)
  en_instance ──► en_cours_versement ──► encaisse
  (bordereau créé, déposé à la banque, rapproché vs relevé)

Circuit B — Sans bordereau physique (virements / compensation / paiement internet)
  en_instance ──► encaisse
  (justificatif bancaire joint + bordereau de regroupement OPTIONNEL état encaisse par défaut)
```

**Virement client & Paiement internet — workflow Circuit B :**

| Étape | Action | Obligatoire |
|-------|--------|-------------|
| 1. Création règlement | Saisie du montant, client, date, mode=virement ou paiement_internet | — |
| 2. Justificatif | Joindre le justificatif bancaire (avis de virement, notification plateforme, capture relevé) | **Oui** |
| 3. Référence | Saisir la référence virement (visible sur relevé) ou ID transaction | **Oui** |
| 4. Confirmation | Le responsable valide → `encaisse` | — |
| 5. Bordereau (optionnel) | Regrouper dans un bordereau par (banque + mode) → état `encaisse` par défaut | Non |

> Le bordereau virement/internet sert de **récapitulatif de trésorerie** (regrouper les mouvements par banque pour les arrêtés de caisse) — il n'a pas de rôle de dépôt physique. Son état est `encaisse` dès la création car l'argent est déjà sur le compte.

**Notification Odoo — règlements sans bordereau (tous modes) :**
Chaque matin à 8h00, un cron consolide tous les règlements sans bordereau et envoie une notification par mode dans la cloche Odoo (voir §6.8 pour le détail).

> **Virements Oracle (V=1 844) :** migration → state `encaisse` direct, `reference_virement` alimenté depuis `NOTES` Oracle si disponible.

> **Paiement internet :** type `paiement_internet` inclus dans le Circuit B dès EVO03. Le workflow spécifique plateforme (Konnect/e-dinar/Flouci…) sera défini dans une EVO dédiée ; pour l'instant, traitement identique au virement (justificatif + référence + validation manuelle).

### 4.2 Extension `insurance.settlement` (règlements)

Nouveaux champs sur le modèle existant :

| Champ | Type | Description |
|-------|------|-------------|
| `state` | Selection | Ajout de `en_instance`, `en_cours_versement`, `rejete`, `perdu` aux états existants |
| `bordereau_id` | Many2one → `insurance.bordereau` | Bordereau auquel appartient ce règlement |
| `is_compensation` | Boolean | Règlement par compensation ou avoir (pas de flux bancaire) |
| `compensation_source_id` | Many2one → `insurance.compensation.credit` | Source du crédit compensation |
| `motif_rejet` | Selection | Motif si état = rejete (voir §4.6) |
| `date_rejet` | Date | Date du rejet bancaire |
| `num_cheque` | Char | N° chèque ou N° effet traité (Oracle : `NUM_CHEQUE`) |
| `tireur` | Char | Nom du tireur (Oracle : `TIREUR`) |
| `banque_tireur` | Char | Banque du client émetteur du chèque/traité (Oracle : `BANQUE_TIREUR`) — info sur le titre, **pas** l'établissement du bordereau |
| `reference_virement` | Char | Référence virement (visible sur relevé bancaire) ou ID transaction internet — obligatoire pour Circuit B |
| `justificatif_ids` | Many2many → `ir.attachment` | Pièces justificatives bancaires (avis de virement, notification plateforme, capture relevé) — **obligatoires** pour mode `virement` et `paiement_internet` |
| `has_justificatif` | Boolean (computed) | True si au moins 1 justificatif joint — affiché en pastille sur la liste |
| `date_perte` | Date | Date de déclaration de perte |
| `motif_perte` | Selection | Motif perte : `perte_physique` / `vol` / `destruction` / `autre` |
| `opposition_banque` | Boolean | Opposition/blocage demandé à la banque sur le titre perdu |
| `date_opposition` | Date | Date de la demande d'opposition |
| `replacement_of_id` | Many2one → `insurance.settlement` | Si ce règlement remplace un règlement perdu/rejeté |
| `replacement_id` | Many2one → `insurance.settlement` (computed) | Règlement de remplacement créé suite à perte/rejet |
| `transfert_imputations` | Boolean | Lors du remplacement : transférer les imputations du titre original |


### 4.3 Nouveau modèle `insurance.etablissement`

Référentiel unique des établissements de réception des fonds (banques + caisses internes).

| Champ | Type | Description |
|-------|------|-------------|
| `name` | Char | Libellé (ex : BIAT, BH, Caisse Siège) |
| `type` | Selection | `banque` / `caisse` |
| `code` | Char | Code court (BIAT, BH, STB…) |
| `agence` | Char | Nom de l'agence bancaire (ex : Agence Lac, Agence Centre) — requis pour l'édition PDF bordereau |
| `rib` | Char | RIB du compte courtier dans cet établissement (ex : 08 006 0123456789 47) — requis pour instructions bancaires PDF |
| `res_bank_id` | Many2one → `res.bank` | Lien optionnel vers banque Odoo standard |
| `active` | Boolean | — |

> **Caisse locale :** type = `caisse`. Circuit A allégé : un bordereau espèces est créé normalement, déposé (état `depose`), puis le responsable caisse valide la **décharge interne** (pas de relevé bancaire) → bordereau passe directement à `rapproche`, settlement passe à `encaisse`. Même workflow qu'une banque mais validation par décharge physique au lieu du relevé bancaire.
>
> **Établissements Oracle identifiés dans REMIS_CHEZ :** ATTIJARI BANK (3 773), BIAT (1 234), ABC LLOYD (1 092), ABC BH (511), ABC MAGHREBIA (109), ABC STAR (65). Les préfixes "ABC" correspondent aux comptes courtier chez ces banques. À créer dans le référentiel au démarrage.

### 4.4 Nouveau modèle `insurance.bordereau`

Bordereau de versement regroupant des règlements remis à un même établissement.

| Champ | Type | Description |
|-------|------|-------------|
| `name` | Char | Référence bordereau (séquence auto : BV-2026-XXXX) |
| `date_creation` | Date | Date de création |
| `date_depot` | Date | Date de dépôt à l'établissement |
| `etablissement_id` | Many2one → `insurance.etablissement` | Établissement destinataire (banque ou caisse) |
| `mode_paiement` | Selection | especes / cheques / traites |
| `state` | Selection | `brouillon` / `depose` / `rapproche` / `partiellement_rapproche` / `encaisse` (Circuit B uniquement) |
| `settlement_ids` | One2many → `insurance.settlement` | Règlements inclus |
| `montant_total` | Monetary (computed) | Somme des règlements |
| `montant_rapproche` | Monetary (computed) | Montant confirmé par banque |
| `montant_non_rapproche` | Monetary (computed) | En attente / rejeté |
| `num_bordereau_banque` | Char | Numéro de bordereau **fourni par la banque** lors du dépôt — **facultatif**, utilisé pour le rapprochement (Oracle : `NUM_BOREDERAU_BANQ`) |
| `date_valeur` | Date | Date valeur banque |
| `responsable_id` | Many2one → `res.users` | Responsable caisse/compta |
| `note` | Text | Observations |
| `company_id` | Many2one → `res.company` | Société |

**Contraintes :**
- Un bordereau regroupe des règlements du **même mode de paiement ET du même établissement** (`mode_paiement` + `etablissement_id`). Exemple : 2 chèques BIAT + 1 chèque BH = 2 bordereaux séparés.
- Un règlement ne peut appartenir qu'à **un seul bordereau**.
- Un bordereau en état `depose` ou `rapproche` ne peut plus être modifié.

### 4.5 Nouveau modèle `insurance.compensation.credit`

Crédit de compensation issu d'un remboursement sinistre non versé.

| Champ | Type | Description |
|-------|------|-------------|
| `name` | Char | Référence (COMP-2026-XXXX) |
| `partner_id` | Many2one → `res.partner` | Client bénéficiaire |
| `montant_initial` | Monetary | Montant du remboursement sinistre |
| `montant_utilise` | Monetary (computed) | Montant déjà utilisé en compensation |
| `montant_disponible` | Monetary (computed) | Solde restant |
| `date_creation` | Date | — |
| `state` | Selection | actif / epuise / annule |
| `origine` | Char | Référence dossier sinistre / avoir |
| `settlement_comp_ids` | One2many → `insurance.settlement` | Règlements compensation qui l'utilisent |
| `note` | Text | — |

**Règle :** `montant_utilise = SUM(settlement.amount for settlement in settlement_comp_ids)`. Si `montant_utilise >= montant_initial` → state = `epuise`.

### 4.6 Motifs de rejet (`motif_rejet`)

| Code | Libellé |
|------|---------|
| `provision` | Chèque sans provision |
| `compte_clos` | Compte clôturé |
| `opposition` | Opposition du titulaire |
| `signature` | Défaut de signature / signature non conforme |
| `irregularite` | Irrégularité du titre |
| `expire` | Chèque/Traité expiré |
| `impaye_banque` | Impayé bancaire (traité) |
| `autre` | Autre motif |

---

## 5. Workflows Détaillés

### 5.1 Workflow Règlement Standard (espèces / chèque / traité)

```
[Caissier/Gestionnaire]
        │
        ▼
  Créer règlement
  state = en_instance
        │
        ▼
  Créer/Ouvrir Bordereau
  (mode = especes|cheques|traites)
        │
        ▼
  Ajouter règlement au bordereau
  settlement.bordereau_id = bordereau.id
  settlement.state = en_cours_versement     ← déclenché par action bordereau
  bordereau.state = brouillon → depose      ← action "Déposer à la banque"
        │
        ▼
  [Responsable compta]
  Rapprochement bancaire
  (comparaison relevé bancaire)
        │
   ┌────┴────┐
   │ Confirmé│                  │ Rejeté
   ▼         ▼
settlement  settlement
.state =    .state = rejete
 encaisse   + motif_rejet
            + date_rejet
        │
        ▼
  Bordereau.state = rapproche | partiellement_rapproche
        │
        ▼
  [EVO02] Imputation sur quittances
  settlement.state = regle (si solde = 0)
```

### 5.2 Workflow Règlement par Compensation

```
[Gestionnaire]
        │
        ▼
  Vérifier credit compensation disponible
  insurance.compensation.credit (partner = client)
        │
        ▼
  Créer règlement
  is_compensation = True
  compensation_source_id = credit.id
  state = en_instance
        │
        ▼
  Valider compensation
  (pas de bordereau — flux interne)
  settlement.state = encaisse   ← validation par responsable
  compensation_credit.montant_utilise += settlement.amount
        │
        ▼
  [EVO02] Imputation sur quittances
  settlement.state = regle
```

### 5.3 Workflow Titre Perdu (chèque / traité)

#### Cas A — Perte avant dépôt (state = en_instance)

```
[Gestionnaire]
Constate la perte du titre physique
        │
        ▼
Action "Déclarer perdu"
  settlement.state = perdu
  settlement.date_perte = today
  settlement.motif_perte = perte_physique | vol | ...
        │
        ├──► Si chèque/traité : proposer opposition bancaire
        │    settlement.opposition_banque = True
        │    settlement.date_opposition = today
        │    → Courrier/alerte à générer vers la banque tirée
        │
        ▼
Imputations existantes → état annule (automatique)
        │
        ▼
[Optionnel] Créer règlement de remplacement
  nouveau_settlement.replacement_of_id = settlement.id
  si transfert_imputations = True :
    → imputations originales rattachées au nouveau règlement
      (state = en_attente_encaissement sur le nouveau)
  nouveau_settlement.state = en_instance
```

#### Cas B — Perte après dépôt (state = en_cours_versement)

```
[Gestionnaire]
Constate la perte du titre après remise bordereau
        │
        ▼
Action "Déclarer perdu"
  settlement.state = perdu
  settlement.bordereau_id → retrait du bordereau
    (si bordereau.state = depose : possible)
    (si bordereau.state = rapproche : impossible — contacter responsable)
  bordereau recalculé (montant_total réduit)
  si bordereau devient vide → bordereau annulé
        │
        ├──► Opposition bancaire OBLIGATOIRE recommandée
        │    (le titre a été présenté à la banque)
        │
        ▼
Imputations existantes → état annule (automatique)
        │
        ▼
[Optionnel] Créer règlement de remplacement
  (même logique que Cas A)
```

#### Règles spécifiques Perte

| Règle | Description |
|-------|-------------|
| Un titre `perdu` ne peut plus être ajouté à un bordereau | — |
| Un titre `perdu` ne peut plus recevoir de nouvelles imputations | Blocage identique à `rejete` |
| Le remplacement crée un **nouveau** règlement en `en_instance` | Traçabilité via `replacement_of_id` |
| Si `transfert_imputations = True` : les imputations passent en `en_attente_encaissement` sur le nouveau règlement | Le gestionnaire n'a pas à les re-saisir |
| Un seul remplacement actif par titre perdu | Contrôle unicité via `replacement_id` |

### 5.4 Workflow Suivi Non-Encaissés

Règlements en état `rejete` ou bordereaux en `partiellement_rapproche` nécessitent un suivi :

- **Relance** : contacter le client pour régularisation (nouveau chèque, virement, etc.)
- **Nouveau règlement** : créer un nouveau règlement de remplacement
- **Annulation** : annuler le règlement rejeté (retour à `impaye` ou `annule`)
- **Tableau de bord** : vue dédiée liste des règlements non-encaissés avec ancienneté et motif

---

## 6. Interface Utilisateur

### 6.1 Menus ajoutés (sous menu AssurCore > Caisse & Banque)

```
AssurCore
└── Caisse & Banque
    ├── Bordereaux de Versement
    ├── Règlements en Instance
    ├── Règlements Non Encaissés (rejetés / en attente > X jours)
    ├── Crédits Compensation
    └── Rapprochement Bancaire
```

### 6.2 Vue Liste Bordereaux

Colonnes : Référence | Date dépôt | Banque | Mode | Nb règlements | Montant total | Montant rapproché | État (pastille)

Actions groupées :
- Déposer à la banque (brouillon → depose)
- Rapprocher (depose → rapproche)
- Imprimer bordereau (PDF)

### 6.3 Vue Formulaire Bordereau

- Entête : référence, dates, banque, mode, responsable, état
- Onglet **Règlements** : liste des settlements inclus (référence, client, date, montant, état, motif rejet)
- Onglet **Rapprochement** : numéro bordereau banque (facultatif), référence relevé bancaire, date valeur, montant confirmé, écart
- Totaux bas de page : total bordereau / total rapproché / total rejeté / écart

### 6.4 Vue Règlements en Instance

Filtre par défaut : `state in (en_instance, en_cours_versement)`.  
Groupage par : mode_paiement, bordereau_id, gestionnaire.  
Action rapide : **Créer bordereau** depuis une sélection de règlements.

### 6.5 Vue Liste Clients — Colonnes Financières (A4)

La liste des clients (`res.partner` filtré assurés) est enrichie de colonnes calculées stockées, recalculées à chaque mouvement de règlement ou d'imputation.

#### Colonnes affichées

| Colonne | Champ stocké | Formule |
|---------|-------------|---------|
| **En instance** | `reg_montant_instance` | Σ settlements (state ∈ {en_instance, en_cours_versement}) |
| **Encaissé** | `reg_montant_encaisse` | Σ settlements (state = encaisse) |
| **Rejeté / Impayé** | `reg_montant_rejete` | Σ settlements (state ∈ {rejete, impaye}) |
| **Total réglé** | `reg_montant_regle` | Σ settlements (state = regle) |
| **Imputations en attente** | `imp_montant_attente` | Σ imputations (state = en_attente_encaissement) |
| **Imputations confirmées** | `imp_montant_confirme` | Σ imputations (state = confirme) |
| **Solde encaissé à imputer** | `solde_encaisse_a_imputer` | `reg_montant_encaisse` − `imp_montant_confirme` — ce qui est confirmé en banque mais pas encore ventilé sur des quittances |
| **Solde réglé résiduel** | `solde_regle_residuel` | `reg_montant_regle` − Σ imputations confirmées portant sur des settlements (state = regle) — écart résiduel sur règlements déjà clôturés |
| **Solde global à imputer** | `solde_global_a_imputer` | `reg_montant_encaisse` + `reg_montant_regle` − `imp_montant_confirme` — vision consolidée toutes sources |
| **État encaissement** | `etat_encaissement` | Voir règle ci-dessous |

#### Règle colonne "État encaissement"

| Condition | Valeur affichée | Couleur |
|-----------|----------------|---------|
| `solde_global_a_imputer` < 0 | ⚠ Anomalie | Rouge |
| `solde_regle_residuel` > 0 | ⚠ Résidu réglé : X TND | Rouge |
| `solde_encaisse_a_imputer` > 0 | Solde : X TND | Orange |
| `solde_global_a_imputer` = 0 AND `reg_montant_instance` > 0 | En instance | Bleu |
| `solde_global_a_imputer` = 0 AND `reg_montant_instance` = 0 | Apuré | Vert |

> **Anomalie (sur-imputation)** : `imp_montant_confirme` > `reg_montant_encaisse + reg_montant_regle` — les imputations dépassent les encaissements. Cas typique sur l'historique Oracle migré.
>
> **Résidu réglé** : un règlement est en état `regle` (considéré soldé) mais la somme de ses imputations confirmées est inférieure à son montant. Cela signifie qu'il a été clôturé prématurément en Oracle. Ces deux cas génèrent automatiquement une `insurance.anomaly` EVO02 sur la fiche client.

#### Implémentation Odoo

Champs **stored computed** sur `res.partner` (recalcul via `_compute_reg_stats`, déclencheur `inverse_name` sur `insurance.settlement.partner_id` et `insurance.settlement.imputation`).

```python
reg_montant_instance = fields.Monetary(
    compute='_compute_reg_stats', store=True,
    compute_sudo=True
)
# ... idem pour chaque colonne

@api.depends(
    'settlement_ids.state', 'settlement_ids.amount',
    'settlement_ids.imputation_ids.state',
    'settlement_ids.imputation_ids.amount',
)
def _compute_reg_stats(self):
    for partner in self:
        settlements = partner.settlement_ids.filtered(
            lambda s: s.state not in ('annule',)
        )
        partner.reg_montant_instance = sum(
            s.amount for s in settlements
            if s.state in ('en_instance', 'en_cours_versement')
        )
        partner.reg_montant_encaisse = sum(
            s.amount for s in settlements if s.state == 'encaisse'
        )
        # ...
        partner.solde_a_imputer = (
            partner.reg_montant_encaisse - partner.imp_montant_confirme
        )
        if partner.imp_montant_confirme > partner.reg_montant_encaisse:
            partner.etat_encaissement = 'anomalie'
        elif partner.solde_a_imputer > 0:
            partner.etat_encaissement = 'solde'
        elif partner.reg_montant_instance > 0:
            partner.etat_encaissement = 'instance'
        else:
            partner.etat_encaissement = 'apure'
```

#### Filtres et groupages disponibles

- Filtre rapide : **Anomalies** | **Solde > 0** | **En instance** | **Apurés**
- Groupage par : gestionnaire, mode de paiement dominant, établissement
- Tri par défaut : anomalies en tête, puis solde décroissant

### 6.7 Vue Suivi Non-Encaissés

Filtre : `state = rejete` ou `state = en_cours_versement AND date_depot < TODAY - N jours`.  
Colonnes : Client | Référence | Mode | Montant | Date dépôt | Ancienneté (j) | Motif | Actions.

### 6.8 Notification Odoo — Règlements sans bordereau (tous modes)

**Déclencheur :** tout règlement **quel que soit le mode**, non encore affecté à un bordereau (`bordereau_id = False`), dans l'un des états suivants :
- `en_instance` — pour les modes Circuit A (chèques/traités/espèces) : devrait être dans un bordereau
- `encaisse` — pour les modes Circuit B (virement/paiement_internet) : encaissé mais non regroupé

**Canal :** notification Odoo native (cloche 🔔 top-right) via `mail.bus` / `mail.message` — visible par tous les utilisateurs du groupe **Responsable Caisse** et **Gestionnaire Encaissement**.

**Messages (un par mode concerné) :**
> *"X règlement(s) chèques en instance sans bordereau. [Voir →]"*
> *"Y règlement(s) traités en instance sans bordereau. [Voir →]"*
> *"Z règlement(s) espèces en instance sans bordereau. [Voir →]"*
> *"N règlement(s) virement encaissés non regroupés dans un bordereau. [Voir →]"*
> *"M règlement(s) paiement internet encaissés non regroupés dans un bordereau. [Voir →]"*

**Fréquence :** action planifiée quotidienne (cron) à **8h00** uniquement. Pas de trigger temps réel sur `write()` — évite le spam lors des imports ETL ou saisies en masse.

**Implémentation Odoo :**
```python
# Cron quotidien 8h00 — ir.cron configuré dans data/evo03_cron.xml
# (pas de trigger dans write() — choix délibéré pour éviter le spam)

def _cron_notify_sans_bordereau(self):
    # Modes Circuit A : alerte si en_instance sans bordereau
    circuit_a = self.search([
        ('type_reg', 'in', ('cheques', 'traites', 'especes')),
        ('state', '=', 'en_instance'),
        ('bordereau_id', '=', False),
    ])
    # Modes Circuit B : alerte si encaisse sans bordereau
    circuit_b = self.search([
        ('type_reg', 'in', ('virement', 'paiement_internet')),
        ('state', '=', 'encaisse'),
        ('bordereau_id', '=', False),
    ])
    all_sans_bordereau = circuit_a | circuit_b
    if not all_sans_bordereau:
        return
    # Grouper par mode pour un message distinct par mode
    by_mode = {}
    for s in all_sans_bordereau:
        by_mode.setdefault(s.type_reg, []).append(s)
    responsables = self._get_caisse_responsables()
    for mode, settlements in by_mode.items():
        msg = f"{len(settlements)} règlement(s) par {mode} sans bordereau affecté."
        self.env['bus.bus']._sendone(
            responsables,
            'mail.message/insert',
            {'id': False, 'body': msg, 'message_type': 'notification'},
        )
```

**Lien "Voir la liste" :** ouvre la vue Règlements filtrée sur `bordereau_id = False AND state in (en_instance, encaisse)` groupée par `type_reg`.

### 6.9 Bordereau de Regroupement Circuit B (Virement / Internet)

**Création :** manuelle par le courtier depuis la vue "Règlements en instance Circuit B".

**Granularité :** 1 bordereau par **(banque + mode)** — regroupe tous les virements de la même banque.

**Comportement spécial :**
- État = `encaisse` **par défaut** à la création (l'argent est déjà reçu)
- Pas d'étape `depose` / `en_cours_versement`
- Pas d'impression physique requise (bordereau interne de trésorerie)
- Sert à l'**arrêté de caisse** et au suivi trésorerie par banque

**Action rapide :** depuis la notification cloche → clic → liste des règlements non groupés → bouton **"Créer bordereau de regroupement"** → sélection banque → bordereau créé immédiatement en `encaisse`.

### 6.10 Dashboard Encaissement (extension EVO02 dashboard)

Nouveaux KPIs :

| KPI | Formule |
|-----|---------|
| Règlements en instance | COUNT(state=en_instance) |
| En cours de versement | COUNT(state=en_cours_versement) |
| Encaissés ce mois | SUM(state=encaisse AND date_valeur in mois) |
| Taux rejet | COUNT(rejete) / COUNT(total) * 100 |
| Crédits compensation disponibles | SUM(compensation.montant_disponible) |
| Non encaissés > 30 j | COUNT(en_cours_versement AND ancienneté > 30) |

### 6.11 Bouton Graphe sur la Fiche Bordereau

Le même explorateur de graphe développé en EVO02 (GraphExplorer, `assurcore_graph` JS component) est accessible depuis la fiche bordereau via un bouton dédié.

**Positionnement :** bouton en haut de la fiche bordereau (zone `<header>` ou `<div class="oe_button_box">`), libellé **"Voir le graphe"** avec icône 🕸 / graphe.

**Point d'entrée du graphe :** le bordereau lui-même comme nœud racine.

**Graphe affiché :**
```
bordereau (racine)
  └── règlement (BLEU)
        └── client / partner (VERT)
              └── imputation (ORANGE)
                    └── opération / quittance (ROUGE)
```

**Comportement :**
- Clic sur un nœud = re-racine (navigation dans le graphe)
- Survol = info-bulle avec les champs clés (montant, état, date)
- Bouton ← Précédent pour revenir à la vue précédente (pile interne)
- Icônes SVG par type de nœud (bordereau = icône banque, règlement = €, client = personne, imputation = lien, quittance = document)

**Implémentation :**
```python
# Dans insurance.bordereau, action_open_graph()
def action_open_graph(self):
    return {
        'type': 'ir.actions.client',
        'tag': 'assurcore_graph',
        'context': {
            'root_model': 'insurance.bordereau',
            'root_id': self.id,
            'root_label': self.name,
        },
    }
```

```xml
<!-- Dans la vue form du bordereau -->
<button name="action_open_graph" type="object"
        string="Voir le graphe" icon="fa-share-alt"
        class="oe_stat_button"/>
```

**Backend graph_actions :** ajouter la résolution depuis `insurance.bordereau` vers ses règlements (`settlement_ids`) comme nouveau point d'entrée dans `evo02_graph_actions.py`.

---

### 6.12 Statistiques Smart Buttons sur la Fiche Bordereau

La fiche bordereau affiche une barre de **smart buttons** (stat buttons Odoo) donnant accès aux KPIs en un clic.

#### 6.12.1 Smart Buttons — Fiche Bordereau (individuel)

| Bouton | Calcul | Action clic |
|--------|--------|-------------|
| **Règlements** `X` | `COUNT(settlement_ids)` | Vue liste règlements du bordereau |
| **Encaissés** `X` | `COUNT(settlement_ids filtered state=encaisse)` | Liste filtrée encaisse |
| **En instance** `X` | `COUNT(settlement_ids filtered state=en_instance)` | Liste filtrée en_instance |
| **Rejetés** `X` | `COUNT(settlement_ids filtered state=rejete)` | Liste filtrée rejete |
| **Imputations** `X` | `COUNT(imputation via settlements)` | Vue liste imputations liées |
| **Montant total** `X DT` | `SUM(settlement_ids.amount)` | — (stat display only) |

```xml
<!-- Exemple smart button dans la vue form bordereau -->
<div class="oe_button_box" name="button_box">
    <button type="object" name="action_view_settlements"
            class="oe_stat_button" icon="fa-money">
        <field name="settlement_count" widget="statinfo" string="Règlements"/>
    </button>
    <button type="object" name="action_view_settlements_encaisse"
            class="oe_stat_button" icon="fa-check-circle">
        <field name="settlement_encaisse_count" widget="statinfo" string="Encaissés"/>
    </button>
    <button type="object" name="action_view_settlements_rejete"
            class="oe_stat_button" icon="fa-times-circle">
        <field name="settlement_rejete_count" widget="statinfo" string="Rejetés"/>
    </button>
</div>
```

#### 6.12.2 Statistiques Globales — Vue Analyse Bordereaux

Accessible depuis le menu **Encaissement > Analyse**, une vue pivot/graphe dédiée aux statistiques croisées demandées par le client :

**1. Statuts des règlements (par mode)**

| Dimension | Mesure |
|-----------|--------|
| `type_reg` (mode) en ligne | `COUNT` et `SUM(montant)` en colonne |
| `state` (statut) en colonne | Pivot avec totaux |

Filtre rapide : par établissement, par période (mois/trimestre), par gestionnaire.

**2. Statuts des imputations (par mode)**

Vue pivot `insurance.settlement.imputation` groupée par :
- `settlement_id.type_reg` (mode de paiement)
- `state` (confirme / en_attente_encaissement / annule)

**3. Bordereaux par banque**

| Dimension | Mesure |
|-----------|--------|
| `etablissement_id.name` (banque) en ligne | `COUNT(bordereau)` en colonne |
| `state` (statut bordereau) | Montant total et nombre |
| `mode_paiement` | Regroupement secondaire |

Vue graphe (barres empilées) : X = banque, Y = montant total, couleur = état bordereau.

**4. Modes de paiement par banque**

Vue pivot `insurance.settlement` groupée par :
- `bordereau_id.etablissement_id.name` (banque)
- `type_reg` (mode)

Avec mesures : `COUNT`, `SUM(montant)`, `AVG(montant)`.

**Implémentation :**
```python
# Champs computed stockés sur insurance.bordereau
settlement_count = fields.Integer(compute='_compute_settlement_stats', store=True)
settlement_encaisse_count = fields.Integer(compute='_compute_settlement_stats', store=True)
settlement_rejete_count = fields.Integer(compute='_compute_settlement_stats', store=True)
settlement_instance_count = fields.Integer(compute='_compute_settlement_stats', store=True)
montant_total = fields.Monetary(compute='_compute_settlement_stats', store=True, currency_field='currency_id')

@api.depends('settlement_ids.state', 'settlement_ids.amount')
def _compute_settlement_stats(self):
    for rec in self:
        settlements = rec.settlement_ids
        rec.settlement_count = len(settlements)
        rec.settlement_encaisse_count = len(settlements.filtered(lambda s: s.state == 'encaisse'))
        rec.settlement_rejete_count = len(settlements.filtered(lambda s: s.state == 'rejete'))
        rec.settlement_instance_count = len(settlements.filtered(lambda s: s.state == 'en_instance'))
        rec.montant_total = sum(settlements.mapped('amount'))
```

---

---

## 7. Règles Métier

| # | Règle |
|---|-------|
| R01 | Tout nouveau règlement (hors compensation) démarre en `en_instance`. |
| R02 | Un règlement peut être imputé quel que soit son état, **sauf** `rejete` ou `perdu`. |
| R03 | Un bordereau regroupe des règlements de **même mode ET même établissement** (1 bordereau = 1 couple mode+établissement). |
| R04 | Un règlement `rejete` ou `perdu` **bloque** toute création de nouvelle imputation. |
| R05 | Un règlement passant à `rejete` ou `perdu` **annule automatiquement** toutes ses imputations existantes. |
| R06 | Un règlement passant à `encaisse` **confirme automatiquement** toutes ses imputations `en_attente_encaissement`. |
| R07 | Un crédit compensation ne peut être utilisé que pour le **même client** (partner_id). |
| R08 | Le montant d'un règlement compensation ne peut pas dépasser le `montant_disponible` du crédit. |
| R09 | Un bordereau `depose` ou `rapproche` est **verrouillé** (pas d'ajout/retrait de règlements). |
| R10 | Un règlement `rejete` génère automatiquement une **anomalie santé** (insurance.anomaly EVO02). |
| R11 | La compensation est validée par un profil **Responsable Caisse** uniquement. |
| R12 | Les espèces versées en caisse interne (établissement type `caisse`) sont validées par décharge interne — pas de relevé bancaire. |
| R13 | Les règlements historiques migrés depuis Oracle conservent leur état (pas de forçage à `en_instance`). |
| R13a | Un règlement `virement` ou `paiement_internet` peut être ajouté à un **bordereau Circuit B** (type `virement`/`paiement_internet`) mais **jamais** à un bordereau Circuit A (chèques/traités/espèces). |
| R13b | Un règlement `virement` ou `paiement_internet` en `en_instance` depuis plus de **15 jours** génère une alerte ancienneté. |
| R13c | Confirmation virement/internet → `encaisse` : `reference_virement` **obligatoire** + au moins 1 pièce jointe dans `justificatif_ids`. |
| R13d | Bordereau Circuit B créé avec état `encaisse` par défaut — pas d'étape `depose`/`en_cours_versement`. |
| R13e | Notification cloche consolidée quotidiennement à 8h00 (cron) pour tous les règlements sans bordereau, quel que soit le mode de paiement. Pas de déclenchement temps réel pour éviter le spam ETL. |
| R14 | Les colonnes financières de la liste clients sont des **champs stored computed** — recalculées à chaque changement d'état sur les règlements ou imputations du client. |
| R15 | Si `imp_montant_confirme` > `reg_montant_encaisse` pour un client → `etat_encaissement = anomalie` + génération automatique d'une `insurance.anomaly` EVO02. |
| R16 | Le tri par défaut de la liste clients (vue encaissement) : anomalies en tête, puis solde_a_imputer décroissant. |
| R17 | Un bordereau ne peut contenir que des règlements du **même mode de paiement**. Tout bordereau Oracle multi-modes détecté lors de la migration est obligatoirement éclaté en sous-bordereaux distincts, avec anomalie `bordereau_oracle_eclate` et notification explicative sur chaque sous-bordereau. |

---

## 8. Impact sur EVO02

### 8.1 Modification wizard imputation (insurance.ventilation.wizard)

#### Règle selon l'état du règlement au moment de l'imputation

| État règlement | Comportement | Statut imputation créée |
|---|---|---|
| `encaisse` | Autorisé, normal | `confirme` |
| `en_instance` | Autorisé avec avertissement | `en_attente_encaissement` |
| `en_cours_versement` | Autorisé avec avertissement | `en_attente_encaissement` |
| `rejete` | **Bloqué** — impossible de créer une nouvelle imputation | — |
| `perdu` | **Bloqué** — titre perdu, aucune imputation possible (R04) | — |

Avertissement affiché (non-bloquant) :
> *"Ce règlement n'est pas encore confirmé par la banque. L'imputation est enregistrée en attente d'encaissement et sera confirmée automatiquement lors du rapprochement bancaire."*

#### Basculement automatique sur encaissement

Quand un règlement passe à `encaisse` (rapprochement bancaire ou validation caisse), **toutes ses imputations** en état `en_attente_encaissement` basculent automatiquement en `confirme`.

#### Annulation automatique sur rejet

Quand un règlement passe à `rejete` :
1. Toutes ses imputations existantes (quel que soit leur état) passent à `annule` **automatiquement**.
2. Toute tentative de créer une nouvelle imputation sur ce règlement est **bloquée** avec message :
   > *"Règlement rejeté — motif : [motif_rejet]. Aucune imputation ne peut être créée sur un règlement rejeté."*

```python
# Déclencheur sur insurance.settlement, write() state → rejete
def _on_state_rejete(self):
    self.imputation_ids.write({'state': 'annule'})

# Contrôle wizard
if settlement.state == 'rejete':
    raise UserError(
        f"Le règlement {settlement.name} est rejeté "
        f"({settlement.motif_rejet}). Création d'imputation impossible."
    )
if settlement.state == 'perdu':
    raise UserError(
        f"Le règlement {settlement.name} est déclaré perdu "
        f"({settlement.motif_perte}). Création d'imputation impossible."
    )
```

> **Exception migration :** flag `evo03_skip_encaissement_check` pour l'historique Oracle (analogue à `evo02_skip_checks`).

### 8.2 Nouveau champ sur `insurance.settlement.imputation`

Ajouter `state` (Selection) sur le modèle d'imputation existant :

| Valeur | Libellé |
|---|---|
| `en_attente_encaissement` | En attente confirmation bancaire |
| `confirme` | Encaissement confirmé |
| `annule` | Annulée (règlement rejeté) |

Les imputations créées avant EVO03 (historique migré) sont initialisées à `confirme` par défaut.

### 8.3 Dashboard EVO02 — onglet Encaissement

Ajouter les KPIs EVO03 dans le dashboard existant (nouvelle colonne ou nouvel onglet).

---

## 9. Migration Historique

### 9.1 Révélations issues de l'analyse des données Oracle réelles

L'analyse de `PR_REGELEMENT_DATA_TABLE` (21 773 enregistrements) a révélé :

| Champ Oracle | Taux remplissage | Rôle réel |
|---|---|---|
| `BANQUE_TIREUR` | 96% | Banque du **client** (émetteur du chèque) — info sur le titre, **pas** l'établissement du bordereau |
| `REMIS_CHEZ` | 31% | Banque du **courtier** où les règlements sont déposés = **établissement du bordereau** |
| `NUM_BOREDERAU_BANQ` | 31% | Référence bordereau Oracle — **1 976 bordereaux déjà existants à migrer directement** |
| `DATE_VERSEMENT_BANQ` | 31% | Date de versement en banque |
| `PR_BQ_CLT` | **0% (vide)** | Table banque client sans données — cascade Niveau 2 supprimée |

**Cascade corrigée pour l'établissement du bordereau :**
```
Niveau 1 — REMIS_CHEZ sur le règlement (banque du courtier)
    │ renseigné → utiliser cet établissement
    │ absent ↓
Niveau 2 — Établissement par défaut = ATTIJARI BANK
    (valeur la plus fréquente dans REMIS_CHEZ : 3 773 cas / 55%)
```

**Établissements Oracle identifiés dans REMIS_CHEZ :**
ATTIJARI BANK (3 773), BIAT (1 234), ABC LLOYD (1 092), ABC BH (511), ABC MAGHREBIA (109), ABC STAR (65).
→ À créer dans `insurance.etablissement` avant l'ETL.

### 9.2 Populations et stratégie par catégorie

| Population | Nb | TYPE_REG | Traitement Odoo |
|---|---|---|---|
| Avec `NUM_BOREDERAU_BANQ` — ENCAISSE=O | 3 299 | C/T/E | Migrer bordereau Oracle → state `encaisse` + anomalie |
| Avec `NUM_BOREDERAU_BANQ` — non encaissé | 3 518 | C/T/E | Migrer bordereau Oracle → state `depose`, settlement → `en_cours_versement` |
| Sans bordereau — ENCAISSE=O | 6 646 | C/T/E | Créer bordereau régularisation par (client + REMIS_CHEZ + mode) → `encaisse` + anomalie |
| Sans bordereau — brouillon (C/T) | 8 310 | C, T | Créer bordereau par (REMIS_CHEZ + mode) → `depose`, settlement → `en_cours_versement` |
| Virements (V) | 1 844 | V | **Pas de bordereau** — encaissement direct, state `encaisse` |
| Avoir / Remboursement (A, R) | 20 | A, R | Workflow compensation, state `encaisse` sans bordereau |
| REGLE / IMPAYE | — | — | Aucun bordereau, états inchangés |

### 9.3 Migration des bordereaux Oracle existants (1 976 bordereaux)

Grouper les règlements par `NUM_BOREDERAU_BANQ` → **1 bordereau Odoo par (référence + mode_paiement)**.

> **Règle éclatement multi-modes :** si un même `NUM_BOREDERAU_BANQ` Oracle contient des règlements de types différents (ex : C et T mélangés), il est **obligatoirement éclaté** en autant de bordereaux Odoo qu'il y a de modes distincts. Chaque bordereau éclat hérite du même `num_bordereau_banque` Oracle et reçoit une anomalie de type `bordereau_oracle_eclate` avec la notification explicative suivante :
> *"Le bordereau Oracle [NUM] a été séparé en X bordereaux distincts (chèques / traités / espèces) car la règle métier impose 1 bordereau par mode de paiement."*

| Champ bordereau | Valeur |
|---|---|
| `name` | Séquence interne Odoo (BV-HIST-XXXX) — **nouveau numéro local généré** |
| `num_bordereau_banque` | `NUM_BOREDERAU_BANQ` Oracle — numéro banque conservé pour le rapprochement |
| `etablissement_id` | `REMIS_CHEZ` du groupe |
| `date_depot` | `DATE_VERSEMENT_BANQ` |
| `state` | `encaisse` si ENCAISSE=O sur au moins 1 règlement, sinon `depose` |
| `is_migration` | True |
| Anomalie | Si state=`encaisse` : "bordereau_sans_justification_bancaire" |
| Anomalie éclat | Si bordereau Oracle multi-modes : "bordereau_oracle_eclate" sur chaque sous-bordereau créé |

> Distribution taille des bordereaux Oracle : 820 à 1 règlement, 319 à 2, jusqu'à 25 maximum.

### 9.4 Bordereaux de régularisation — encaissés sans bordereau (6 646)

**Granularité :** 1 bordereau par **(partner_id + établissement + mode_paiement)**.

Chaque bordereau → anomalie "bordereau_sans_justification_bancaire".
Action **"Justifier a posteriori"** disponible → le courtier joint un document (scan relevé, décharge) via `justificatif_ids` → l'anomalie passe de `ouverte` à `justifiee`. L'état `encaisse` et les imputations existantes **ne sont pas modifiés**. Aucune perte d'historique.

> ⚠️ L'action "Remettre en instance" (qui aurait repassé le règlement à `en_instance`) est **supprimée** de cette spec — trop risquée sur l'historique migré.

### 9.5 Bordereaux en instance — chèques/traités brouillons (8 310)

**Granularité :** 1 bordereau par **(établissement + mode_paiement)** — tous clients confondus.

- bordereau.state = `depose` / settlement.state = `en_cours_versement`
- Anomalie : "bordereau_historique_non_rapproche"

### 9.6 Virements et compensations

**Virements (1 844) :** 100% encaissés Oracle, quasi aucun REMIS_CHEZ → state `encaisse` direct, pas de bordereau.

**Avoir/Remboursement (20) :** compensations historiques → state `encaisse`, compensation.credit de régularisation si solde disponible.

### 9.7 Flags migration sur `insurance.bordereau`

| Champ | Type | Description |
|-------|------|-------------|
| `is_migration` | Boolean | Bordereau créé lors de la migration historique |
| `date_migration` | Date | Date d'exécution |
| `num_bordereau_banque` | Char | Numéro bordereau fourni par la banque (facultatif) — pour nouveaux bordereaux : saisi lors du rapprochement ; pour bordereaux migrés : `NUM_BOREDERAU_BANQ` Oracle |

### 9.8 Script ETL (evo03_migration_bordereaux.py)

```python
DEFAULT_ETABLISSEMENT = 'ATTIJARI BANK'  # plus fréquent dans REMIS_CHEZ
TYPE_MAP = {'C': 'cheques', 'E': 'especes', 'T': 'traites',
            'V': 'virement', 'A': 'compensation', 'R': 'compensation'}

def resolve_etablissement(reg):
    return normalize(reg['REMIS_CHEZ']) or DEFAULT_ETABLISSEMENT

# Lot 1 : Bordereaux Oracle existants (grouper par NUM_BOREDERAU_BANQ + mode)
for bord_ref, group in groupby(regs_with_bord, key='NUM_BOREDERAU_BANQ'):
    etab = resolve_etablissement(group[0])
    is_enc = any(r['ENCAISSE'] == 'O' for r in group)
    # Détecter les modes présents dans ce bordereau Oracle
    modes_presents = list({TYPE_MAP[r['TYPE_REG']] for r in group})
    is_multi_mode = len(modes_presents) > 1

    # Éclater en autant de sous-bordereaux que de modes distincts
    for mode in modes_presents:
        group_mode = [r for r in group if TYPE_MAP[r['TYPE_REG']] == mode]
        bordereau = create_bordereau(
            etablissement=etab,
            mode=mode,
            date_depot=group_mode[0]['DATE_VERSEMENT_BANQ'],
            state='encaisse' if any(r['ENCAISSE']=='O' for r in group_mode) else 'depose',
            is_migration=True,
            num_bordereau_banque=bord_ref,  # même référence banque conservée sur tous les éclats
        )
        for r in group_mode:
            r.write({'bordereau_id': bordereau.id,
                     'state': 'encaisse' if r['ENCAISSE']=='O' else 'en_cours_versement'})
        if any(r['ENCAISSE']=='O' for r in group_mode):
            create_anomaly(bordereau, 'bordereau_sans_justification_bancaire')
        if is_multi_mode:
            create_anomaly(bordereau, 'bordereau_oracle_eclate',
                note=f"Le bordereau Oracle {bord_ref} a été séparé en {len(modes_presents)} "
                     f"bordereaux distincts ({' / '.join(modes_presents)}) car la règle métier "
                     f"impose 1 bordereau par mode de paiement.")

# Lot 2 : Encaissés sans bordereau (par client + etablissement + mode)
for (partner, etab, mode), group in groupby(
        regs_enc_no_bord,
        key=lambda r: (r['NUM_CLIENT'], resolve_etablissement(r), TYPE_MAP[r['TYPE_REG']])):
    bordereau = create_bordereau(etablissement=etab, mode=mode,
                                  state='encaisse', is_migration=True)
    for r in group:
        r.write({'bordereau_id': bordereau.id})
    create_anomaly(bordereau, 'bordereau_sans_justification_bancaire')

# Lot 3 : Brouillons C/T (par etablissement + 
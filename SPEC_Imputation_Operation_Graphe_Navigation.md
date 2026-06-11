# Spécification technique — Imputation règlement↔opération & écran graphe de navigation

**Projet :** AssurCore (Odoo) · **Date :** 11/06/2026 · **Réf. :** EVO-LETTRAGE-OP-01
**Prérequis lus :** Rapport_Verification_Regles_Gestion_DATA_REEL_2026-06-11.md

---

## 1. Contexte et objectif

L'ancien système Oracle lettre les règlements au niveau **mémoire** (PR_REG_FACTURE) : impossible de savoir quelle opération (quittance compagnie) est réglée par quel règlement, ni de détecter une opération réglée par plusieurs règlements. Le client demande :

1. Une **granularité d'imputation règlement ↔ opération** (montant ventilé).
2. Un **écran graphe navigable** : mémoire / client / règlement / opération comme sommet, navigation par clic, info-bulle au survol, et exclusion des nœuds du même type que le sommet.

## 2. Modèle de données

### 2.1 Nouvelle table `insurance.settlement.allocation` (imputation)

| Champ | Type | Contrainte |
|---|---|---|
| `settlement_id` | M2O `insurance.settlement` | required, ondelete=restrict, index |
| `operation_id` | M2O `insurance.operation` | required, ondelete=restrict, index |
| `memoire_id` | M2O `account.move` (mémoire) | related stocké = `operation_id.memoire_id`, index |
| `amount` | Monetary | `> 0` |
| `date_allocation` | Date | défaut = date règlement |
| `is_third_party` | Boolean | payeur ≠ client facturé (cf. §2.3) |
| `is_reconstructed` | Boolean | ventilation reconstituée à la migration (§4) |
| `company_insurance_id` | M2O | related `operation_id.company_id` (compagnie) |

SQL : `UNIQUE(settlement_id, operation_id)` — la ventilation d'un règlement sur une opération est une seule ligne (modifiable), pas plusieurs.

### 2.2 Contraintes d'intégrité (Python + SQL)

Ces contraintes répondent directement aux anomalies trouvées dans DATA_REEL :

- **C1 — non sur-imputation règlement** : `SUM(amount)` des allocations d'un règlement ≤ `montant du règlement`. (Anomalie Oracle : 3 règlements sur-imputés, ex. règ. 7966.)
- **C2 — non sur-règlement opération** : `SUM(amount)` reçus par une opération ≤ `montant TTC de l'opération`. (Anomalie : 29 mémoires sur-réglées.)
- **C3 — opération facturée obligatoire** : interdiction de créer une allocation si `operation_id.memoire_id` est vide (règle de gestion n°4 du client) ou si la mémoire est annulée.
- **C4 — cohérence mémoire** : le lettrage niveau mémoire est **calculé**, jamais saisi : `lettré(M) = SUM(allocations des opérations de M)`. Supprime la classe d'anomalies TOTAL_REG incohérent (253 cas, −725 k TND).
- **C5 — devise/société** identiques entre règlement et opération.

### 2.3 Paiement pour compte de tiers

Constaté dans l'existant (434 lettrages cross-client, flag `TIERS`). Le modèle doit l'autoriser explicitement :

- `settlement_id.partner_id` (payeur) peut différer de `operation_id.partner_id` (client facturé) → `is_third_party = True` (calculé, non saisi).
- Écriture comptable de transfert inter-comptes générée automatiquement (compte 411 payeur → 411 facturé) pour que les deux comptes clients restent justes.
- L'écran de lettrage doit demander une confirmation quand le client diffère (éviter le cas inverse trouvé : flag oublié 3 fois).

### 2.4 Statut dérivé de l'opération

Champ calculé `settlement_state` sur `insurance.operation` : `non_facturee` (pas de mémoire), `non_reglee`, `partielle` (0 < reçu < dû), `soldee`. Stocké + indexé pour les filtres et le graphe.

### 2.5 Santé de l'objet — second statut transversal (évolution majeure)

**Principe** : les anomalies de l'existant sont **migrées telles quelles**, jamais bloquées ni corrigées silencieusement. Chaque objet porte un second statut indépendant du statut métier : sa **santé**.

**Mixin `insurance.health.mixin`** appliqué à : opération, mémoire/facture, règlement, allocation, client (extensible) :

| Champ | Type | Description |
|---|---|---|
| `health_state` | Selection | `ok` / `anomalie` (calculé depuis les lignes, stocké, indexé) |
| `anomaly_ids` | O2M `insurance.anomaly` | détail des anomalies de l'objet |
| `anomaly_note` | Text calculé | concaténation lisible des détails (affichage rapide) |

**Modèle `insurance.anomaly`** (une ligne par anomalie constatée) :

| Champ | Description |
|---|---|
| `res_model` / `res_id` | objet porteur (référence générique) |
| `type_id` | M2O `insurance.anomaly.type` (catalogue) |
| `detail` | note libre : valeurs constatées, montants, écart (ex. « lettré 9 917,650 pour un dû de 4 958,825 — règ. 10695 + 10712, montants identiques, aucun impayé saisi ») |
| `origin` | `migration` / `exploitation` |
| `detected_date`, `detected_by` | traçabilité |
| `state` | `ouverte` / `justifiée` / `corrigée` (avec qui/quand/commentaire) |

**Catalogue `insurance.anomaly.type`** initialisé avec les anomalies du rapport du 11/06/2026 : `MEM_INEXISTANTE` (réf. mémoire cassée), `MEM_ORPHELINE` (mémoire sans opération), `SUR_IMPUTATION` (règlement), `SUR_REGLEMENT` (mémoire/opération), `LETTRAGE_ORPHELIN` (vers règlement/mémoire inexistant), `TOTAL_REG_INCOHERENT`, `TIERS_NON_FLAGUE`, `QUITTANCE_GENERIQUE` (NF/INST/DIVERS), `OP_NON_FACTUREE_ANCIENNE`, `VENTILATION_RECONSTITUEE`.

**Articulation avec les contraintes C1-C5** : les contraintes s'appliquent aux **saisies et modifications nouvelles**. Les enregistrements migrés porteurs d'anomalies sont importés avec leurs valeurs réelles + lignes d'anomalie (contraintes Python non rétroactives ; pas de contrainte SQL stricte sur les colonnes concernées). Toute modification ultérieure d'un objet en anomalie exige soit la mise en conformité, soit la justification (passage `justifiée` avec commentaire).

**Impact UI — transversal à tous les menus** :

- *Vues liste* : pastille santé (vert/rouge) en colonne, filtre « Avec anomalie » et regroupement par type d'anomalie dans tous les menus (opérations, mémoires, factures, règlements, clients).
- *Vues formulaire* : bandeau d'alerte si `health_state = anomalie`, affichant `anomaly_note` + lien vers les lignes de détail.
- *Graphe (§5)* : liseré rouge sur les nœuds en anomalie ; l'info-bulle ajoute la section « Anomalies » avec le détail.
- *Menu dédié* « Qualité des données » : vue pivot/liste de toutes les anomalies (par type, par état, par ancienneté), tableau de bord de résorption.
- *Workflow de résorption* : depuis la ligne d'anomalie, action « corriger » (ouvre l'objet) ou « justifier » (motif obligatoire) ; l'objet repasse `ok` quand toutes ses lignes sont fermées.

### 2.6 Identification des quittances — référence interne + clé métier

**Règle GÉNÉRALE, applicable à toutes les compagnies/opérateurs** (pas seulement LLOYD) : le critère de bascule est l'absence d'un identifiant exploitable — le couple **(n° de contrat + ID quittance)** fourni par la compagnie. Constat dans l'existant : LLOYD (3 647 « NF »), STAR/MAGHREBIA (« INST », « DIVERS »), valeurs vides ou n° de police recopié en guise de quittance.

**Règles :**

1. **Référence interne systématique** : toute opération reçoit un identifiant technique interne unique (séquence `insurance.operation.ref`, ex. `OP-2026-000123`), indépendant du n° de quittance compagnie. C'est lui qui sert aux liens techniques (allocations, graphe, écritures). Le n° de quittance compagnie devient un attribut descriptif, jamais une clé.
2. **Test d'identifiant + clé métier de repli** : à chaque création/import d'opération, quelle que soit la compagnie, le système teste si le couple (contrat + ID quittance) est présent et exploitable (non vide, non générique — liste paramétrable : `NF`, `INST`, `DIVERS`, valeur = n° de police…). Si oui → identification directe par ce couple. Sinon → bascule automatique sur la **clé métier de rapprochement** : compagnie + n° de contrat/police + date d'effet (du/au) + nature d'opération + montant prime. Index composite dédié. Champ `ident_mode` (`quittance` / `cle_metier`) stocké sur l'opération pour tracer le mode d'identification.
3. **Rapprochement assisté — service unique** : moteur de rapprochement `insurance.receipt.matcher` (`match(compagnie, identifiants, clé_métier) → opération + score`) appliquant la cascade du point 2, avec score (exact → automatique ; approchant → proposition à valider ; aucun → création en anomalie `QUITTANCE_GENERIQUE`). **Tous les canaux l'utilisent** — saisie manuelle, import de relevés/bordereaux, OCR — aucune logique de rapprochement dupliquée.
4. **Prise en charge OCR (obligatoire)** : le pipeline OCR des documents compagnie (quittances, bordereaux, avis d'échéance) doit extraire au minimum les champs de la cascade — compagnie, n° quittance / contrat + ID s'ils existent, n° de police, dates d'effet (du/au), nature d'opération, montant prime — puis appeler le même service `receipt.matcher` :
   - score exact → rattachement automatique, document attaché à l'opération en pièce jointe ;
   - score approchant → écran de validation OCR présentant les candidats avec écarts champ par champ ;
   - aucun candidat → création en anomalie `QUITTANCE_GENERIQUE` avec le document attaché.
   Les gabarits d'extraction OCR par compagnie doivent couvrir ces champs au minimum ; le `ident_mode` est renseigné comme pour les autres canaux.
5. **Recherche utilisateur** : la barre de recherche des opérations doit chercher indifféremment sur référence interne, n° quittance compagnie, n° de police et plage de dates (champs de recherche dédiés dans le filtre avancé).
6. **Migration** : les opérations à quittance générique (toutes compagnies) sont importées avec référence interne générée + anomalie `QUITTANCE_GENERIQUE` portant en détail la valeur d'origine, pour ne rien perdre.

## 3. Migration de l'historique

La ventilation par opération n'existe pas dans Oracle. Reconstruction à l'import :

1. Pour chaque ligne PR_REG_FACTURE (règlement R → mémoire M, montant X) : répartir X sur les opérations de M **en FIFO par date d'opération** (puis par NUM_OPERATION croissant), à concurrence du restant dû de chaque opération.
2. Marquer toutes ces lignes `is_reconstructed = True` (bandeau d'avertissement dans l'UI : « ventilation reconstituée, non contractuelle »).
3. **Cas dégradés (du rapport d'anomalies) — migrés tels quels + santé** (cf. §2.5, pas de blocage ni de correction silencieuse) :
   - lettrages vers mémoires inexistantes (95) ou vides (186) → importés, anomalie `LETTRAGE_ORPHELIN` / `MEM_ORPHELINE` avec détail (clé d'origine, montant) ;
   - sur-règlements (29) et sur-imputations (3) → importés avec leurs montants réels, anomalie `SUR_REGLEMENT` / `SUR_IMPUTATION` détaillant l'écart ;
   - règlements non imputés (258, 2,1 M TND) → importés non lettrés (état « à imputer », santé `ok` — ce n'est pas une anomalie) ;
   - TOTAL_REG incohérents (253) → le champ Oracle est ignoré (recalcul), anomalie `TOTAL_REG_INCOHERENT` à titre documentaire sur la mémoire ;
   - opérations sans mémoire (484) → importées, anomalie `OP_NON_FACTUREE_ANCIENNE` si antérieures à un seuil à définir avec le client ;
   - quittances génériques NF/INST/DIVERS → cf. §2.6.5.
4. Contrôle de recette : pour chaque mémoire, `SUM(allocations)` == ancien lettrage PR_REG_FACTURE (tolérance 0,005), anomalies comprises ; et chaque anomalie du rapport du 11/06/2026 doit se retrouver en ligne `insurance.anomaly` (comptages identiques).

## 4. API du graphe

### 4.1 Endpoint

`POST /assurcore/graph/node` (type `json`, auth `user`)

```json
{ "model": "memoire|operation|settlement|partner",
  "res_id": 1234,
  "limit_per_level": 25,
  "offset": {"settlement": 0, "memoire": 0} }
```

### 4.2 Réponse

```json
{
  "root": {"key": "memoire:1234"},
  "nodes": [
    {"key": "operation:88", "type": "operation", "label": "OP 88",
     "subtitle": "500,000 · reste 300,000", "state": "partielle",
     "tooltip": {"Quittance": "LLOYD n°55780", "Compagnie": "LLOYD",
                 "Date": "05/12/2025", "Prime": "500,000",
                 "Réglé": "200,000", "Reste": "300,000"},
     "action": {"res_model": "insurance.operation", "res_id": 88}}
  ],
  "edges": [
    {"from": "settlement:42", "to": "operation:88", "kind": "allocation",
     "amount": "200,000", "reconstructed": false},
    {"from": "memoire:1234", "to": "operation:88", "kind": "structure"}
  ],
  "truncated": {"settlement": false, "memoire": true, "remaining": 190}
}
```

### 4.3 Règles de construction (serveur)

- **RG-1 (exclusion de type)** : parcours en largeur depuis la racine ; un nœud n'est ajouté que si `type ≠ type(racine)`. Les feuilles sont donc toujours d'un type différent du sommet.
- **RG-2 (arêtes)** : `allocation` (règlement↔opération, porte le montant), `structure` (mémoire→opération, client→règlement, client→mémoire). Une arête n'est émise que si ses deux nœuds sont retenus.
- **RG-3 (pagination)** : `limit_per_level` par type (défaut 25), tri par date décroissante ; `truncated` permet à l'UI d'afficher « +N autres… » (clic = offset suivant).
- **RG-4 (droits)** : `check_access_rights/rules` sur chaque modèle ; les nœuds non autorisés sont omis (pas d'erreur).
- **RG-5** : profondeur max 4 niveaux (suffisant : chaque type n'apparaît qu'une fois en couche grâce à RG-1).

## 5. UI — composant OWL `assurcore.GraphExplorer`

- **Client action** `assurcore_graph` ouvrable depuis : fiche mémoire, opération, règlement, client (bouton « Graphe ») — l'enregistrement devient la racine.
- **Rendu** : SVG généré par le composant (option : Cytoscape.js si zoom/drag exigés en V2). Disposition en couches par distance à la racine ; racine en haut, encadrée.
- **Couleurs** : mémoire = violet, opération = gris (ambre si `partielle`, vert si `soldee`), règlement = corail, client = sarcelle. Légende fixe en bas.
- **Interactions** :
  - *survol* : info-bulle avec les paires clé/valeur de `tooltip` (date, montant, lettré, reste, n° quittance, compagnie…) ;
  - *clic* : le nœud devient racine → nouvel appel API → `pushState` dans le breadcrumb Odoo (bouton retour natif) ;
  - *double-clic* : `ir.actions.act_window` vers la fiche de l'enregistrement ;
  - *« +N autres »* : pagination du niveau concerné.
- **Arêtes** : trait plein + montant = allocation ; pointillé sans montant = structurel ; allocation `reconstructed` en pointillé + mention « reconstitué » dans l'info-bulle de l'arête.
- **États visuels** : badge « reste X » sur les nœuds partiels ; bandeau si données reconstituées présentes.

## 6. Critères d'acceptation

1. Créer une allocation violant C1/C2/C3 → refus avec message explicite (test unitaire par contrainte).
2. Saisie d'un règlement de C22 lettré sur opération de C1 → `is_third_party` coché automatiquement + écriture de transfert générée + confirmation UI.
3. Graphe racine M1 : aucune autre mémoire affichée ; opérations d'autres mémoires atteintes via un règlement commun visibles ; feuilles ≠ type mémoire. Idem pour chaque type (4 tests).
4. Client à 200+ mémoires : réponse < 1 s, niveau tronqué à 25 avec « +N autres » fonctionnel.
5. Migration : sur DATA_REEL, `SUM(allocations)` par mémoire = lettrage Oracle (écart ≤ 0,005) ; 100 % des allocations historiques `is_reconstructed = True` ; comptage des anomalies migrées = comptage du rapport du 11/06/2026 (95+186 lettrages, 29+3 sur-règlements/imputations, 253 TOTAL_REG, 484 ops, quittances génériques).
6. Info-bulle ≤ 150 ms après survol ; navigation par clic conserve l'historique navigateur/breadcrumb.
7. Santé : un objet migré en anomalie s'affiche avec pastille rouge dans sa vue liste, bandeau + note détaillée en formulaire, liseré rouge dans le graphe ; filtre « Avec anomalie » présent dans chaque menu ; justification d'une anomalie → motif obligatoire, objet repasse `ok` quand toutes les lignes sont fermées.
8. Quittance sans identifiant exploitable (toutes compagnies, ex. LLOYD « NF ») : l'opération a une référence interne unique, `ident_mode = cle_metier`, la recherche par police + date d'effet la retrouve, et le rapprochement d'un bordereau par clé métier propose le bon candidat.
9. OCR : un document scanné AVEC identifiant exploitable → rattachement direct ; SANS identifiant → rapprochement par clé métier via le même `receipt.matcher` (vérifiable : même candidat que la saisie manuelle des mêmes champs) ; document toujours attaché à l'opération ou à l'anomalie créée.

## 7. Estimation indicative

| Lot | Contenu | Charge |
|---|---|---|
| 1 | Modèle allocation + contraintes + statut dérivé + tiers | 3-4 j |
| 2 | Écran de lettrage par opération (saisie/modif ventilation) | 3 j |
| 3 | API graphe + composant OWL + tests | 4-5 j |
| 4 | Script migration FIFO + anomalies migrées flaguées + recette | 4-6 j |
| 5 | Santé transversale : mixin + modèle anomalie + impact sur toutes les vues (pastilles, bandeaux, filtres) + menu Qualité des données + workflow résorption | 5-7 j |
| 6 | Référence interne + clé métier quittance (toutes compagnies) + service `receipt.matcher` + intégration au pipeline OCR | 4-6 j |

*Hypothèse : modèles `insurance.operation`, `insurance.settlement` et mémoires (`account.move`) déjà en place conformément au plan de migration existant.*

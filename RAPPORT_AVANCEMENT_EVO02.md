# Rapport d'avancement — EVO02 (session du 11/06/2026)

> **MISE À JOUR 12/06/2026 — VALIDATION RUNTIME RÉUSSIE ✅**
> Module installé sur Odoo 17.0 réel (Docker, base restaurée depuis dump) :
> **10/10 tests EVO02 passent — 0 failed, 0 error** (`odoo.tests.result`).
> Corrections apportées en boucle courte pendant la validation :
> mixin graphe converti en AbstractModel (TypeError object layout au registre),
> wizard d'imputation : fusion dans la ligne existante au lieu d'un doublon,
> données de test alignées sur les champs obligatoires réels (branche, dates,
> code opération, timbre fiscal inclus dans le total dû).
> Environnement remis d'aplomb au passage : disque Docker migré définitivement
> sur D: (Disk image location), base restaurée depuis data_db\assurcore_db.dump.

**Branche :** `evo02-lettrage-sante-graphe-ocr` · **Version module :** 17.0.3.0.0
**Référentiels :** SPEC_Imputation_Operation_Graphe_Navigation.md · PLAN_TACHES_EVO_Lettrage_Sante_Graphe_OCR.md

## Étape 0 — Repérage de l'existant ✅

Constat structurant : EVO01 avait déjà posé `insurance.settlement.imputation` (lettrage règlement↔quittance) et chaque opération génère sa quittance 1-1 (`action_generate_receipt`). **Décision d'architecture : étendre l'existant au lieu de créer une table doublon** — la granularité opération est obtenue en ajoutant `operation_id` sur la ligne de lettrage. Moins de migration, pas de double vérité.

## Étape 1 — Lot 1 : socle modèle ✅ (commit `4ae4ef1`)

`models/evo02_settlement_allocation.py` :

- `operation_id` (stocké, déduit de la quittance, modifiable), `is_third_party` (calculé : payeur ≠ assuré), `is_reconstructed` (historique migré), compagnie liée.
- Contraintes nouvelles saisies : **C2** non sur-règlement de quittance (exclut les règlements impayés/remplacés du cumul), **C3** opération annulée → imputation refusée + unicité opération/quittance, **C5** cohérence devise, **anti-doublon** (une ligne par couple règlement-quittance). C1 (non sur-imputation du règlement) existait depuis EVO01.
- Exemption : lignes `is_reconstructed` et contexte `evo02_skip_checks` (migration) — l'historique anormal reste importable tel quel, conformément à la décision « santé ».
- `insurance.operation.settlement_state` (non facturée / non réglée / partielle / soldée — stocké, indexé) + encaissé/reste ; totaux d'imputation et `is_fully_allocated` sur le règlement ; **confirmation obligatoire du paiement pour tiers** dans le wizard d'imputation.

## Étape 2 — Lot 5 : santé des données ✅ (commit `0c57e18`)

`models/evo02_health.py`, `data/evo02_anomaly_types.xml`, `views/evo02_health_views.xml` :

- `insurance.anomaly.type` (catalogue initialisé avec les **10 types du rapport du 11/06/2026**, sévérités), `insurance.anomaly` (référence générique vers tout objet, détail libre, origine migration/exploitation, réf. Oracle, workflow **ouverte → justifiée (motif obligatoire) / corrigée**, réouverture possible).
- `insurance.health.mixin` (`health_state`, `anomaly_note`, compteur) appliqué à : opération, quittance, règlement, imputation, client. Recalcul automatique à chaque création/clôture d'anomalie. Helper `add_anomaly()` pour la migration et les contrôles.
- UI : menu **Qualité des données** (liste + pivot + types), pastilles santé et filtres « Avec anomalie » sur opérations/quittances/règlements, bandeau rouge détaillé sur la fiche opération, droits agent/manager.

## Étape 3 — Lot 6 : identification quittances + matcher ✅ (commit `93ec448`)

`models/evo02_receipt_matcher.py`, `data/evo02_sequences.xml` :

- `internal_ref` unique (séquence `OP-AAAA-NNNNNN`, contrainte SQL) + `ident_mode` (quittance / clé métier) stocké et tracé. Liste des valeurs génériques **paramétrable** (`assurcore.generic_quittance_values` = NF, INST, DIVERS… — arbitrage T0.3) ; le n° de police recopié est détecté comme non exploitable.
- Service unique `insurance.receipt.matcher.match()` : cascade identifiant compagnie → clé métier (police + dates d'effet + nature + montant ± 0,005) avec score exact / approchant (≤10 candidats) / aucun.
- Branchement OCR : champs `matched_operation_id`, `match_score`, `match_candidate_ids` sur le parseur de documents + `action_match_operation()` qui appelle le même service et rattache le document à l'opération si score exact. *(Reste T3.5 partiel : enrichir les gabarits d'extraction par compagnie pour alimenter tous les champs de la cascade — à faire avec des documents réels.)*

## Étape 4 — Lot 2 : écran de lettrage ✅ (commit `4bae545`)

`views/evo02_lettrage_views.xml` : colonnes opération/compagnie/tiers/reconstitué/santé dans le lettrage, alerte + case de confirmation tiers dans le wizard, onglet **« Règlements (lettrage) »** sur la fiche opération (réf. interne, mode d'identification, encaissé/reste, ventilation détaillée) et badge du statut de règlement dans l'en-tête.

## Étape 5 — Lot 3 : graphe de navigation ✅ (commit `612300f`)

- `controllers/evo02_graph.py` — `POST /assurcore/graph/node` : **RG-1** exclusion du type racine (les feuilles sont toujours d'un autre type), **RG-2** arêtes `allocation` (montant, tiers, reconstitué) / `structure` (pointillé), **RG-3** pagination 25/niveau avec compteur « +N », **RG-4** droits (nœuds non autorisés omis), **RG-5** profondeur max 4. Info-bulles complètes (quittance compagnie, dates, montants, reste, santé).
- `static/src/js/evo02_graph_explorer.js` + template OWL — rendu SVG en couches, couleurs par type (quittance violet, opération gris/ambre selon règlement, règlement corail, client sarcelle), **liseré rouge si anomalie**, clic = nouveau sommet (breadcrumb Odoo natif), double-clic = fiche, survol = info-bulle, arêtes reconstituées en ambre.
- Boutons **Graphe** sur les fiches opération, quittance, règlement.

## Étape 6 — Tests unitaires ✅ (commit `7fc8406`)

`tests/test_evo02.py` — 10 tests alignés sur les critères d'acceptation : refus C2/C3/doublon, exemption historique reconstitué, tiers (flag + wizard bloquant), cycle complet `settlement_state`, cycle santé (anomalie → note → justification avec motif obligatoire), cascade matcher (exact / clé métier / aucun ; NF, INST, police recopiée), **parité canal manuel vs OCR** (même candidat).

## Limites de la session & prochaines étapes

## Étape 7 — Validation environnement (sandbox) ✅ partiel

Docker absent de la sandbox et proxy bloquant github.com/nightly.odoo.com → impossible d'y faire tourner Odoo 17 complet. Réalisé à la place :

- **PostgreSQL embarqué démarré réellement** (pgserver) — l'environnement data fonctionne.
- **Validateur sémantique d'installation** (`tools_validate_evo02.py`, commité) : vérifie par AST que chaque champ référencé dans les vues EVO02 existe dans les modèles Python, que chaque ancre xpath/field d'héritage existe dans la vue parente, que les `inherit_id`/menus/actions pointent sur des ids existants, ACL des nouveaux modèles, cohérence du manifest (fichiers + ordre + assets). **Résultat : 0 erreur** (30 modèles, 77 vues analysés). Le validateur a été éprouvé par tests négatifs (champ bidon et inherit_id cassé détectés).
- **Fix Odoo 17.0** appliqué au passage : `rpc` via `useService("rpc")` (l'import direct `@web/core/network/rpc` n'existe qu'en 17.2+).

| # | Point | Statut |
|---|---|---|
| 1 | **Run réel sur votre machine** (dernier filet) : `docker compose up -d` puis `docker compose exec odoo odoo -d <db> -u assurcore --test-tags evo02 --stop-after-init`. Le validateur a éliminé les erreurs statiques ; restent les comportements runtime (calculs stockés, séquences). | ⚠️ à faire |
| 2 | **Lot 4 — migration FIFO + anomalies flaguées** : non démarré (dépend de l'arbitrage T0.1 FIFO et du seuil T0.2). Le socle est prêt (`is_reconstructed`, `evo02_skip_checks`, `add_anomaly`, types catalogués). | ⏳ phase suivante |
| 3 | **T3.5 partiel — gabarits OCR par comp
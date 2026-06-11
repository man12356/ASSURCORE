# Plan de tâches — EVO Lettrage par opération · Santé des données · Graphe · Identification quittances/OCR

**Réf. :** EVO-LETTRAGE-OP-01 · **Date :** 11/06/2026
**Spec :** SPEC_Imputation_Operation_Graphe_Navigation.md · **Base :** Rapport_Verification_Regles_Gestion_DATA_REEL_2026-06-11.md

---

## Phase 0 — Cadrage et arbitrages client (prérequis bloquants)

| ID | Tâche | Durée | Dépend de | Livrable |
|---|---|---|---|---|
| T0.1 | Valider la règle FIFO de reconstitution de la ventilation historique (ou autre règle proposée par le client) | 0,5 j | — | PV de décision |
| T0.2 | Arbitrer le seuil d'ancienneté des 484 opérations non facturées (anomalie vs en-cours) | 0,5 j | — | PV de décision |
| T0.3 | Valider la liste initiale des valeurs de quittance « génériques » par compagnie (NF, INST, DIVERS…) et le catalogue des 10 types d'anomalies | 0,5 j | — | Listes signées |
| T0.4 | Valider le traitement des 29 sur-règlements et 3 sur-imputations (migrés tels quels + anomalie — confirmer) | 0,5 j | — | PV de décision |

**Jalon J0 : cadrage validé — feu vert développement.**

## Phase 1 — Socle modèle de données (lot 1, 3-4 j)

| ID | Tâche | Durée | Dépend de | Livrable |
|---|---|---|---|---|
| T1.1 | Modèle `insurance.settlement.allocation` (champs, index, unicité) | 1 j | J0 | Module + tests |
| T1.2 | Contraintes C1-C5 (Python, applicables aux nouvelles saisies uniquement) | 1 j | T1.1 | Tests unitaires (1 test/contrainte) |
| T1.3 | Statut dérivé `settlement_state` sur l'opération (calcul, stockage, index) | 0,5 j | T1.1 | Champ + tests |
| T1.4 | Paiement pour tiers : `is_third_party` calculé + écriture de transfert 411→411 + confirmation UI | 1-1,5 j | T1.1 | Tests (critère d'acceptation n°2) |

## Phase 2 — Santé des données, transversal (lot 5, 5-7 j)

| ID | Tâche | Durée | Dépend de | Livrable |
|---|---|---|---|---|
| T2.1 | Mixin `insurance.health.mixin` + modèle `insurance.anomaly` + catalogue `insurance.anomaly.type` (10 types initiaux) | 1,5 j | J0 | Module + tests |
| T2.2 | Application du mixin : opération, mémoire/facture, règlement, allocation, client | 0,5 j | T2.1 | — |
| T2.3 | Impact vues liste (pastille santé, filtre « Avec anomalie », regroupement par type) sur tous les menus | 1,5 j | T2.2 | Vues XML |
| T2.4 | Bandeau formulaire + note détaillée + liens vers lignes d'anomalie | 1 j | T2.2 | Vues XML |
| T2.5 | Menu « Qualité des données » : liste/pivot des anomalies + tableau de bord de résorption | 1 j | T2.2 | Vues + action |
| T2.6 | Workflow résorption : corriger / justifier (motif obligatoire), recalcul `health_state` | 1 j | T2.1 | Tests (critère n°7) |

*Parallélisable avec la phase 1 (équipes distinctes) ; T2.2 sur allocation dépend de T1.1.*

## Phase 3 — Identification quittances + OCR (lot 6, 4-6 j)

| ID | Tâche | Durée | Dépend de | Livrable |
|---|---|---|---|---|
| T3.1 | Référence interne `insurance.operation.ref` (séquence) + champ `ident_mode` | 0,5 j | J0 | — |
| T3.2 | Clé métier composite + index (compagnie, police, dates d'effet, nature, montant) | 0,5 j | T3.1 | — |
| T3.3 | Service `insurance.receipt.matcher` : cascade identifiant → clé métier, scoring exact/approchant/aucun, liste génériques paramétrable (T0.3) | 1,5 j | T3.2 | Tests unitaires de cascade |
| T3.4 | Branchement saisie manuelle + import bordereaux sur le matcher | 1 j | T3.3 | — |
| T3.5 | Branchement pipeline OCR : extraction des champs de la cascade dans les gabarits par compagnie, appel matcher, écran de validation des candidats (écarts champ par champ), attachement du document | 1,5-2 j | T3.3 | Tests (critère n°9) |
| T3.6 | Recherche avancée opérations (réf. interne, n° quittance, police, plage de dates) | 0,5 j | T3.2 | Vue search |

## Phase 4 — Écran de lettrage par opération (lot 2, 3 j)

| ID | Tâche | Durée | Dépend de | Livrable |
|---|---|---|---|---|
| T4.1 | Écran de ventilation d'un règlement sur les opérations (saisie/modification, contrôles C1-C3 en direct, reste à imputer affiché) | 2 j | T1.2 | Vue + tests |
| T4.2 | Gestion tiers dans l'écran (confirmation client différent) + affichage `is_reconstructed` | 1 j | T4.1, T1.4 | — |

## Phase 5 — Graphe de navigation (lot 3, 4-5 j)

| ID | Tâche | Durée | Dépend de | Livrable |
|---|---|---|---|---|
| T5.1 | Contrôleur `/assurcore/graph/node` : RG-1 exclusion de type, RG-2 arêtes, RG-3 pagination, RG-4 droits, RG-5 profondeur | 1,5 j | T1.1 | Tests API (critères n°3, 4) |
| T5.2 | Composant OWL `GraphExplorer` : rendu SVG en couches, couleurs/légende, liseré rouge anomalies | 1,5 j | T5.1, T2.1 | Composant |
| T5.3 | Interactions : info-bulle survol, clic = re-racine + breadcrumb, double-clic = fiche, « +N autres » | 1 j | T5.2 | Tests (critère n°6) |
| T5.4 | Boutons « Graphe » sur fiches mémoire/opération/règlement/client | 0,5 j | T5.2 | Vues |

## Phase 6 — Migration de l'historique (lot 4, 4-6 j)

| ID | Tâche | Durée | Dépend de | Livrable |
|---|---|---|---|---|
| T6.1 | Script ventilation FIFO PR_REG_FACTURE → allocations (`is_reconstructed`) | 1,5 j | T0.1, T1.1 | Script + log |
| T6.2 | Import des cas dégradés AVEC création des lignes d'anomalie (95+186 lettrages, 29+3 sur-règl., 253 TOTAL_REG, 484 ops selon T0.2, génériques selon T0.3) | 1,5 j | T2.1, T6.1 | Script + log |
| T6.3 | Génération références internes + `ident_mode` sur tout l'historique | 0,5 j | T3.1 | Script |
| T6.4 | Recette chiffrée : SUM(allocations)/mémoire = lettrage Oracle (±0,005) ; comptages anomalies = rapport du 11/06/2026 (critère n°5) | 1 j | T6.2 | Rapport de recette |
| T6.5 | Répétition générale sur copie de production + chronométrage | 0,5-1 j | T6.4 | PV |

## Phase 7 — Recette globale et déploiement

| ID | Tâche | Durée | Dépend de | Livrable |
|---|---|---|---|---|
| T7.1 | Recette des 9 critères d'acceptation (spec §6) | 1,5 j | toutes phases | PV de recette |
| T7.2 | Formation utilisateurs : écran lettrage, menu Qualité des données, graphe, validation OCR | 1 j | T7.1 | Support |
| T7.3 | Mise en production + bascule + surveillance J+1 | 0,5 j | T7.1 | — |

**Jalon J1** : fin phases 1+2 (socle + santé). **J2** : fin phases 3+4 (identification + lettrage). **J3** : fin phase 5 (graphe). **J4** : recette migration (T6.4). **J5** : mise en production.

## Synthèse

| Phase | Charge |
|---|---|
| 0 — Cadrage | 2 j (client) |
| 1 — Socle modèle | 3,5-4 j |
| 2 — Santé transversale | 6,5 j |
| 3 — Identification + OCR | 5,5-6 j |
| 4 — Écran lettrage | 3 j |
| 5 — Graphe | 4,5 j |
| 6 — Migration | 5-5,5 j |
| 7 — Recette/déploiement | 3 j |
| **Total** | **~31-34 j·h** (≈ 5-6 semaines à 1 dev, ≈ 3-4 semaines à 2 devs) |

**Parallélisation à 2 développeurs** : dev A = phases 1 → 4 → 6 ; dev B = phases 2 → 3 → 5 ; phase 7 commune. Chemin critique : T0.1 → T1.1 → T6.1 → T6.4 → T7.x.

## Risques principaux

1. **Arbitrages phase 0 retardés** → tout le chemin critique glisse ; verrouiller la réunion de cadrage dès maintenant.
2. **Qualité OCR insuffisante sur certains gabarits compagnie** (T3.5) → prévoir liste des compagnies/documents prioritaires et tolérer la validation manuelle au lancement.
3. **Volumétrie client dans le graphe** (clients à 200+ pièces) → pagination RG-3 testée tôt (T5.1) avec données réelles migrées.
4. **Écarts de recette migration** (T6.4) → les 95 lettrages vers mémoires inexistantes peuvent empêcher l'égalité parfaite ; la règle de comparaison doit les compter à part (déjà prévu, à ne pas perdre).

# Chiffrage des travaux v2.0-stable & estimation EVO02

**Projet :** AssurCore — courtage assurance (Odoo 17) · **Date :** 11/06/2026
**Périmètre constaté :** dépôt Git au tag `v2.0-stable` (30 commits, du 17/05/2026 au 11/06/2026) — module `assurcore` : 21 modèles métier, ~10 100 lignes Python, 24 vues XML (~5 700 lignes), ~5 300 lignes de scripts ETL, déploiement OVH/Docker, monitoring.

## Hypothèses de chiffrage

| Profil | TJM (DT HT) |
|---|---|
| Chef de projet / AMOA | 650 |
| Architecte / expert Odoo–données | 600 |
| Développeur Odoo senior | 450 |
| Développeur Odoo | 350 |

*TJM hypothèses marché tunisien à ajuster selon votre grille réelle. Montants hors taxes, hors licences, hors hébergement (VPS OVH facturé à part).*

---

## 1. Rétro-chiffrage des travaux réalisés (v2.0-stable)

| Lot | Contenu constaté | Charge | Profil | Montant (DT) |
|---|---|---|---|---|
| A — Cadrage & analyse de l'existant | Dictionnaire des 49 tables Oracle, analyse d'écarts migration, règles de gestion, ateliers client | 8 j | Architecte | 4 800 |
| B — Module AssurCore cœur | 21 modèles (polices, opérations, quittances, compagnies, clients, sinistres, branches, risques, commissions, journaux d'encaissement, rapports mouvements + wizards), 24 vues, droits | 28 j | Dev senior | 12 600 |
| C — OCR documents compagnie | Parser de documents, wizards OCR (classification, entraînement, rattachement) | 9 j | Dev senior | 4 050 |
| D — ETL migration Oracle → Odoo | Scripts d'import (clients, polices, opérations, factures, règlements), lettrage SQL, multiples itérations recette (logs ETL phase 2) | 14 j | Dev senior | 6 300 |
| E — Déploiement & exploitation | Docker compose, scripts déploiement local/OVH, génération quittances manquantes, monitoring quotidien VPS | 6 j | Dev senior | 2 700 |
| F — EVO01 : lettrage multi-quittances | Refactoring architecture paiements, imputation des règlements multi-quittances (v17.0.1.5.0 → 17.0.2.0.0) | 7 j | Dev senior | 3 150 |
| G — Audit qualité DATA_REEL & préparation EVO02 | Vérification des 5 règles de gestion sur 24 443 opérations / 21 773 règlements, rapport d'anomalies chiffré, script de contrôle reproductible, spécification EVO02, plan de tâches | 5 j | Architecte | 3 000 |
| **Sous-total production** | | **77 j** | | **36 600** |
| Pilotage projet (~12 %) | Comitologie, suivi, gestion dépôt/versions, coordination client | 9 j | CP | 5 850 |
| **Total v2.0-stable** | | **86 j** | | **≈ 42 450 DT HT** |

**Lecture PM** : la valeur livrée est concentrée sur les lots B+D (un ERP métier opérationnel avec son historique migré). Le ratio pilotage est volontairement bas (12 %) car le projet a fonctionné en binôme court avec le client ; sur un compte client classique on serait à 15-18 %.

---

## 2. Estimation de charge — nouvelle version (EVO02, branche `evo02-lettrage-sante-graphe-ocr`)

Base : SPEC_Imputation_Operation_Graphe_Navigation.md + PLAN_TACHES_EVO_Lettrage_Sante_Graphe_OCR.md.

| Phase | Charge | Profil | Montant (DT) |
|---|---|---|---|
| 0 — Cadrage (4 arbitrages client) — accompagnement | 1 j | CP | 650 |
| 1 — Socle modèle (allocation, contraintes C1-C5, statut, tiers) | 4 j | Dev senior | 1 800 |
| 2 — Santé des données transversale (mixin, anomalies, toutes les vues, menu Qualité, workflow) | 6,5 j | Dev | 2 275 |
| 3 — Identification quittances toutes compagnies + `receipt.matcher` + intégration OCR | 6 j | Dev senior | 2 700 |
| 4 — Écran de lettrage par opération | 3 j | Dev | 1 050 |
| 5 — Graphe de navigation (API + composant OWL + interactions) | 4,5 j | Dev senior | 2 025 |
| 6 — Migration historique (FIFO, anomalies flaguées, recette chiffrée, répétition générale) | 5,5 j | Dev senior | 2 475 |
| 7 — Recette des 9 critères + formation + MEP | 3 j | 1,5 CP + 1,5 dev senior | 1 650 |
| **Sous-total production** | **33,5 j** | | **14 625** |
| Pilotage projet (12 %) | 4 j | CP | 2 600 |
| **Sous-total** | 37,5 j | | 17 225 |
| Provision pour risques (15 %) — qualité OCR par compagnie, volumétrie graphe, écarts recette migration | ~5 j | | 2 585 |
| **Total EVO02** | **≈ 42 j** | | **≈ 19 800 DT HT** |

**Fourchette de négociation** : 18 500 DT (sans provision, périmètre OCR limité aux 3 compagnies prioritaires) à 21 500 DT (provision complète, tous gabarits OCR).

### Conditions et exclusions

1. Les 4 arbitrages de la phase 0 sont rendus avant démarrage (sinon glissement du chemin critique, à la charge du client).
2. Gabarits OCR : couverture initiale limitée aux compagnies représentant 80 % du volume (LLOYD, STAR, COMAR, GAT…) ; les autres en validation manuelle au lancement.
3. La résorption métier des anomalies migrées (justifier/corriger les 993 k DT de lettrages orphelins, 484 opérations non facturées, etc.) est un travail client, hors chiffrage — l'outillage (menu Qualité des données) est inclus.
4. Hors : évolutions de périmètre en cours de lot, reprise de données autres que DATA_REEL, hébergement, formation au-delà d'une session.

### Comparatif de cohérence

EVO02 ≈ 49 % de la charge de tout l'existant (42 j vs 86 j) : cohérent avec son caractère structurant — elle touche le modèle comptable (granularité d'imputation), tous les menus (santé), un écran innovant (graphe) et la chaîne OCR. Si le budget est contraint, le découpage permet de livrer en deux paliers : **palier 1** = phases 1+2+4+6 (socle + santé + lettrage + migration, ~24 j, ~11 500 DT) ; **palier 2** = phases 3+5 (identification/OCR + graphe, ~13 j, ~6 500 DT).

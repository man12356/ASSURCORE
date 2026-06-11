# Vérification des règles de gestion — DATA_REEL (22-05-2026)

**Date d'analyse :** 11/06/2026 · **Source :** `DATA_REEL_22-05-2026\DATA_REEL`

## Volumes analysés

| Table | Rôle | Lignes |
|---|---|---|
| PR_OPERATION | Opérations (= quittances compagnie) | 24 443 |
| PR_OPERATION_FACTUREE_ANNULEE | Opérations annulées (historique) | 5 677 |
| PR_FACTURE | Mémoires (CATEGORIE='M' : 22 927) + factures ('F' : 3) | 22 930 |
| PR_REGELEMENT | Règlements clients | 21 773 |
| PR_REG_FACTURE | Lettrage règlement ↔ mémoire | 22 844 |

Modèle confirmé : opération → mémoire via (`ANNEE_FACT_PRIME`, `NUM_FACTURE_PRIME`, `CATEGORIE_FACTURE_PRIME`) ; lettrage via `PR_REG_FACTURE`.

---

## Règle 1 — Toute quittance compagnie a une opération correspondante

**✅ Conforme à 100 % sur la présence** : 0 opération active sans `NUM_QUITTANCE`.

**⚠️ Réserve — unicité** : 415 couples (COMPAGNIE + N° quittance) partagés par plusieurs opérations (6 013 opérations). L'essentiel provient de valeurs génériques, pas de vrais doublons : `NF` (LLOYD : 3 647, COMAR : 94), `INST` (STAR : 310, MAGHREBIA : 273…), `DIVERS` (STAR : 66), ou du n° de police utilisé comme quittance (STAR `2000/09231` : 175 avis d'aliment). **La règle de correspondance 1-1 n'est donc pas vérifiable pour ces cas** : la quittance compagnie réelle n'est pas tracée. À normaliser avant/pendant migration Odoo (générer une référence interne unique).

## Règle 2 — Chaque opération doit être détail d'une mémoire d'opération

**⚠️ 484 opérations actives (2 %) sans mémoire** (`PRIME_FACTURE='N'`, flag cohérent) — montant prime cumulé : **3 168 850 TND**. Présentes sur toutes les années (2015→2026, pic 2022 : 118). Ce sont des quittances en attente de facturation : tolérées par la conception, mais elles bloquent leur règlement (règle 4) — à apurer.

**❌ 123 opérations référencent une mémoire INEXISTANTE dans PR_FACTURE** (ex. op 7098 → 2019/5022/M, op 11167 → 2021/8824/M). Violation d'intégrité référentielle : mémoires supprimées physiquement sans détacher les opérations.

**❌ 316 mémoires sans AUCUNE opération rattachée** (ni active ni annulée), dont 45 annulées — TOTAL_FACT cumulé : **1 442 661 TND**. Mémoires « orphelines » : pièces comptables client sans détail compagnie.

✔️ Conception multi-compagnies confirmée : 1 868 mémoires regroupent plusieurs opérations, dont **234 mémoires avec opérations de plusieurs compagnies** — conforme à la règle énoncée.

## Règle 3 — Règlement total/partiel d'une ou plusieurs quittances

✔️ Conception confirmée : 867 règlements imputés sur plusieurs mémoires ; 619 règlements partiellement imputés. Le mécanisme total/partiel/multiple fonctionne.

**Anomalies détectées :**

| Anomalie | Nb | Montant (TND) |
|---|---|---|
| Règlements SUR-imputés (lettré > montant règlement) | 3 | écart max 1 708,400 (règ. 7966 : 3 772,902 réglé, 5 481,302 lettré) |
| Mémoires SUR-réglées (lettré > TOTAL_FACT) | 29 | écart cumulé ≈ 70 000 |
| TOTAL_REG stocké ≠ somme lettrage réel | 253 | écart cumulé −725 096 |
| Lettrages vers mémoire inexistante | 95 lignes | 325 590 |
| Lettrages vers règlement inexistant | 28 lignes | 51 548 |
| Règlements jamais imputés (IMPUTER='N') | 258 | 2 106 472 |

Cas vérifiés manuellement (pas des doublons techniques — aucun doublon exact dans PR_REG_FACTURE) :
- **2021/8616/M** : deux chèques distincts (règ. 10695 et 10712) de 4 958,825 chacun lettrés sur la même mémoire, aucun marqué impayé → double règlement réel ou impayé non saisi.
- **2023/13635/M** : un virement (règ. 15374) lettré 10 584,108 sur une mémoire de 5 292,054 (exactement le double).
- **2023/13634/M** : TOTAL_REG stocké **négatif** (−19 780) alors que le lettrage réel est de 88 451 — corruption du champ agrégé.

Le champ `TOTAL_REG`/`TOTAL_RESTANT` de PR_FACTURE n'est **pas fiable** : lors de la migration, recalculer les soldes uniquement depuis PR_REG_FACTURE (après nettoyage), comme déjà prévu dans le plan de migration.

## Règle 4 — Une quittance hors mémoire ne peut pas être réglée

**✅ Respectée structurellement** : 0 règlement pointe vers une opération sans mémoire ; le lettrage passe obligatoirement par la mémoire.

**❌ Contournements détectés** : 186 lignes de lettrage (666 974 TND) portent sur des mémoires **vides** (sans opération rattachée), et 95 lignes (325 590 TND) sur des mémoires **inexistantes**. Dans l'esprit de la règle, ces règlements règlent des quittances introuvables.

## Règle 5 — Une opération appartient à une seule mémoire

**✅ Respectée** : 0 NUM_OPERATION dupliqué dans PR_OPERATION ; le modèle (colonne unique NUM_FACTURE_PRIME) garantit l'unicité ; facture honoraires toujours identique à la mémoire prime (0 divergence).

Note : 3 434 opérations figurent à la fois en actif et en annulé avec une mémoire différente (3 433 cas) = cycle normal annulation → refacturation, pas une violation. 1 584 doublons de NUM_OPERATION dans la table des annulées (historique multiple, attendu).

---

## Synthèse financière

| Indicateur | Montant (TND) |
|---|---|
| Total facturé (TOTAL_FACT, factures actives) | 98 046 541 |
| Total lettré (PR_REG_FACTURE) | 53 459 732 |
| Total règlements saisis | 56 095 861 |
| Reste à régler calculé (hors factures annulées) | 17 257 835 |

## Verdict global

| Règle | Statut |
|---|---|
| R1 — Quittance ↔ opération | ✅ Présence OK · ⚠️ quittances génériques (NF/INST) non traçables |
| R2 — Opération → mémoire | ⚠️ 484 non facturées (2 %) · ❌ 123 réf. cassées · ❌ 316 mémoires orphelines |
| R3 — Règlement total/partiel | ✅ Mécanisme OK · ❌ 3 sur-imputations, 29 sur-règlements, TOTAL_REG non fiable |
| R4 — Pas de règlement sans mémoire | ✅ Structurellement · ❌ ~993 k TND lettrés sur mémoires vides/inexistantes |
| R5 — Une seule mémoire par opération | ✅ Respectée |

## Actions recommandées (priorité décroissante)

1. **Corriger les 3 règlements sur-imputés et les 29 mémoires sur-réglées** (validation métier cas par cas — listes extractibles via le script).
2. **Réparer l'intégrité référentielle** : 123 opérations → mémoires fantômes, 95 + 28 lettrages orphelins, 316 mémoires vides.
3. **Apurer les 484 opérations non facturées** (3,17 M TND) et les 258 règlements non imputés (2,1 M TND) avant migration.
4. **Migration Odoo** : ignorer TOTAL_REG/TOTAL_RESTANT stockés, recalculer le lettrage depuis PR_REG_FACTURE nettoyé ; ajouter des contraintes (FK + check « lettré ≤ montant règlement » et « lettré ≤ TOTAL_FACT ») pour empêcher la récurrence — l'ancien système Oracle ne les imposait pas.
5. **Normaliser les quittances génériques** (NF, INST, DIVERS) avec une référence interne unique.

*Script de contrôle reproductible : `verif_regles_gestion.py` (même dossier).*

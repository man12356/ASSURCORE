#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vérification des règles de gestion AssurCore sur DATA_REEL 22-05-2026."""
import pandas as pd, numpy as np, re, sys

D = "/sessions/loving-great-lovelace/mnt/ASSURPROD/DATA_REEL_22-05-2026/DATA_REEL/"

def load(name, **kw):
    return pd.read_csv(D + name, sep="\t", dtype=str, keep_default_na=False, na_values=[], **kw)

def num(s):
    return pd.to_numeric(s.astype(str).str.replace(" ", "").str.replace(",", "."), errors="coerce").fillna(0)

op   = load("PR_OPERATION_DATA_TABLE.tsv")
opan = load("PR_OPERATION_FACTUREE_ANNULEE_DATA_TABLE.tsv")
fact = load("PR_FACTURE_DATA_TABLE.tsv")
reg  = load("PR_REGELEMENT_DATA_TABLE.tsv")
rf   = load("PR_REG_FACTURE_DATA_TABLE.tsv")

print(f"Volumes: operations={len(op)}, op_annulees={len(opan)}, factures/memoires={len(fact)}, reglements={len(reg)}, lettrage={len(rf)}")

# filtres logiques supprimés
op_act = op[op["SUPP_LOG"].str.strip() != "O"].copy()
fact_act = fact[fact["SUPP_LOG"].str.strip() != "O"].copy()
reg_act = reg[reg["SUPP_LOG"].str.strip() != "O"].copy()
rf_act = rf[rf["SUPP_LOG"].str.strip() != "O"].copy()
print(f"Apres SUPP_LOG: op={len(op_act)}, fact={len(fact_act)}, reg={len(reg_act)}, rf={len(rf_act)}")
print(f"FACTURE_ANNULEE=O: {(fact_act['FACTURE_ANNULEE'].str.strip()=='O').sum()}")

def k(s): return s.astype(str).str.strip()

# clé mémoire
fact_act["KEY"] = k(fact_act["ANNEE_FACT"]) + "/" + k(fact_act["NUM_FACTURE"]) + "/" + k(fact_act["CATEGORIE_FACTURE"])
fact_keys = set(fact_act["KEY"])

print("\n" + "="*70)
print("R1 — QUITTANCE COMPAGNIE <-> OPERATION")
print("="*70)
q = k(op_act["NUM_QUITTANCE"])
sans_q = op_act[(q == "") | (q.str.lower().isin(["nan", "null", "0"]))]
print(f"Operations actives sans NUM_QUITTANCE: {len(sans_q)} / {len(op_act)}")
if len(sans_q):
    print(sans_q.groupby("COMPAGNIE").size().sort_values(ascending=False).head(10).to_string())
# doublons quittance (même compagnie + même n° quittance + même police)
avec_q = op_act[~op_act.index.isin(sans_q.index)].copy()
dup = avec_q[avec_q.duplicated(subset=["COMPAGNIE", "NUM_QUITTANCE"], keep=False)]
print(f"Quittances (COMPAGNIE+NUM_QUITTANCE) partagees par >1 operation: {dup.groupby(['COMPAGNIE','NUM_QUITTANCE']).ngroups} cles, {len(dup)} operations")
dup2 = avec_q[avec_q.duplicated(subset=["COMPAGNIE", "NUM_QUITTANCE", "NUM_POLICE"], keep=False)]
print(f"  dont memes COMPAGNIE+QUITTANCE+POLICE: {dup2.groupby(['COMPAGNIE','NUM_QUITTANCE','NUM_POLICE']).ngroups} cles, {len(dup2)} operations")

print("\n" + "="*70)
print("R2 — CHAQUE OPERATION DOIT ETRE DETAIL D'UNE MEMOIRE")
print("="*70)
op_act["KEY_FP"] = k(op_act["ANNEE_FACT_PRIME"]) + "/" + k(op_act["NUM_FACTURE_PRIME"]) + "/" + k(op_act["CATEGORIE_FACTURE_PRIME"])
op_act["HAS_FP"] = (k(op_act["NUM_FACTURE_PRIME"]) != "") & (k(op_act["NUM_FACTURE_PRIME"]) != "0")
nb_sans_mem = (~op_act["HAS_FP"]).sum()
print(f"Operations actives SANS memoire (NUM_FACTURE_PRIME vide): {nb_sans_mem} / {len(op_act)}")
if nb_sans_mem:
    sm = op_act[~op_act["HAS_FP"]]
    print("  PRIME_FACTURE flag:", sm["PRIME_FACTURE"].str.strip().value_counts().to_dict())
    print("  Montant prime total concerne:", round(num(sm["MONTANT_PRIME"]).sum(), 3))
    print("  Par annee (DATE_OP):", sm["DATE_OP"].str[-2:].value_counts().sort_index().to_dict())
# incohérence flag
flag_incoh = op_act[(k(op_act["PRIME_FACTURE"]) == "O") != op_act["HAS_FP"]]
print(f"Incoherences flag PRIME_FACTURE vs NUM_FACTURE_PRIME: {len(flag_incoh)}")
# référence mémoire inexistante (orphelins)
avec_fp = op_act[op_act["HAS_FP"]]
orph = avec_fp[~avec_fp["KEY_FP"].isin(fact_keys)]
print(f"Operations referencant une memoire INEXISTANTE dans PR_FACTURE: {len(orph)}")
if len(orph): print(orph[["NUM_OPERATION","KEY_FP","COMPAGNIE","MONTANT_PRIME"]].head(10).to_string())
# memoire multi-operations / multi-compagnies (conception attendue)
g = avec_fp.groupby("KEY_FP").agg(nb_op=("NUM_OPERATION","count"), nb_comp=("COMPAGNIE","nunique"))
print(f"Memoires referencees: {len(g)}; avec >1 operation: {(g.nb_op>1).sum()}; avec operations de >1 compagnie: {(g.nb_comp>1).sum()} (conception OK)")
# mémoires sans aucune opération
mem_used = set(avec_fp["KEY_FP"])
opan["KEY_FP"] = k(opan["ANNEE_FACT_PRIME"]) + "/" + k(opan["NUM_FACTURE_PRIME"]) + "/" + k(opan["CATEGORIE_FACTURE_PRIME"])
mem_used |= set(opan[k(opan["NUM_FACTURE_PRIME"]) != ""]["KEY_FP"])
mem_vides = fact_act[~fact_act["KEY"].isin(mem_used)]
print(f"Memoires/factures sans AUCUNE operation rattachee (ni active ni annulee): {len(mem_vides)}")
if len(mem_vides):
    print("  dont annulees:", (k(mem_vides["FACTURE_ANNULEE"])=="O").sum(),
          "| montant TOTAL_FACT cumule:", round(num(mem_vides["TOTAL_FACT"]).sum(),3))

print("\n" + "="*70)
print("R3 — REGLEMENTS TOTAUX/PARTIELS (LETTRAGE)")
print("="*70)
rf_act["KEY"] = k(rf_act["ANNEE_FACT"]) + "/" + k(rf_act["NUM_FACTURE"]) + "/" + k(rf_act["CATEGORIE_FACTURE"])
rf_act["M"] = num(rf_act["MONTANT_REG"])
reg_act["NUM_REG_CLT"] = k(reg_act["NUM_REG_CLT"])
rf_act["NUM_REG_CLT"] = k(rf_act["NUM_REG_CLT"])
# a) allocations par règlement vs montant règlement
alloc = rf_act.groupby("NUM_REG_CLT")["M"].sum()
regm = reg_act.set_index("NUM_REG_CLT")
regm["MONTANT"] = num(regm["MONTANT_REG"])
j = regm.join(alloc.rename("ALLOUE"), how="left")
j["ALLOUE"] = j["ALLOUE"].fillna(0)
sur_alloc = j[j["ALLOUE"] > j["MONTANT"] + 0.005]
print(f"Reglements SUR-imputes (somme lettrages > montant reglement): {len(sur_alloc)}")
if len(sur_alloc):
    print(sur_alloc[["MONTANT","ALLOUE"]].assign(ECART=lambda d: round(d.ALLOUE-d.MONTANT,3)).sort_values("ECART",ascending=False).head(10).to_string())
multi = (rf_act.groupby("NUM_REG_CLT")["KEY"].nunique() > 1).sum()
print(f"Reglements imputes sur PLUSIEURS factures/memoires: {multi} (conception OK)")
partiels = (j[(j['ALLOUE']>0) & (j['ALLOUE'] < j['MONTANT']-0.005)])
print(f"Reglements partiellement imputes (reste a imputer): {len(partiels)}")
non_imputes = j[(j["ALLOUE"]==0)]
print(f"Reglements sans aucun lettrage: {len(non_imputes)} | montant: {round(non_imputes['MONTANT'].sum(),3)}")
# b) par facture: somme règlements vs TOTAL_FACT et TOTAL_REG
pf = rf_act.groupby("KEY")["M"].sum().rename("REGLE_CALC")
f2 = fact_act.set_index("KEY").join(pf, how="left")
f2["REGLE_CALC"] = f2["REGLE_CALC"].fillna(0)
f2["TF"] = num(f2["TOTAL_FACT"]); f2["TR"] = num(f2["TOTAL_REG"])
sur_reg = f2[f2["REGLE_CALC"] > f2["TF"] + 0.005]
print(f"Factures/memoires SUR-reglees (lettre > TOTAL_FACT): {len(sur_reg)}")
if len(sur_reg):
    print(sur_reg[["TF","REGLE_CALC"]].assign(ECART=lambda d: round(d.REGLE_CALC-d.TF,3)).sort_values("ECART",ascending=False).head(10).to_string())
incoh_tr = f2[(f2["TR"] - f2["REGLE_CALC"]).abs() > 0.005]
print(f"Incoherences TOTAL_REG (champ stocke) vs somme lettrage PR_REG_FACTURE: {len(incoh_tr)}")
if len(incoh_tr):
    print("  ecart cumule:", round((incoh_tr['TR']-incoh_tr['REGLE_CALC']).sum(),3))
    print(incoh_tr[["TF","TR","REGLE_CALC"]].assign(ECART=lambda d: round(d.TR-d.REGLE_CALC,3)).reindex((incoh_tr['TR']-incoh_tr['REGLE_CALC']).abs().sort_values(ascending=False).index)[:8].to_string())
# lettrages vers factures inexistantes
rf_orph = rf_act[~rf_act["KEY"].isin(fact_keys)]
print(f"Lignes de lettrage vers facture/memoire INEXISTANTE: {len(rf_orph)} | montant: {round(rf_orph['M'].sum(),3)}")
rf_noreg = rf_act[~rf_act["NUM_REG_CLT"].isin(set(reg_act["NUM_REG_CLT"]))]
print(f"Lignes de lettrage vers reglement INEXISTANT: {len(rf_noreg)} | montant: {round(rf_noreg['M'].sum(),3)}")

print("\n" + "="*70)
print("R4 — PAS DE REGLEMENT SANS MEMOIRE")
print("="*70)
# Une quittance dont l'opération n'est pas dans une mémoire ne peut pas être réglée.
# Structurellement le lettrage passe par la facture/mémoire => violation = lettrage vers mémoire vide ou inexistante (déjà ci-dessus)
mem_vide_keys = set(mem_vides["KEY"])
rf_memvide = rf_act[rf_act["KEY"].isin(mem_vide_keys)]
print(f"Lettrages sur memoires SANS operation rattachee: {len(rf_memvide)} | montant: {round(rf_memvide['M'].sum(),3)}")
# règlements liés directement à une opération sans mémoire
reg_act["NUM_OPERATION"] = k(reg_act["NUM_OPERATION"])
ops_sans_mem = set(k(op_act[~op_act["HAS_FP"]]["NUM_OPERATION"]))
reg_op_sans_mem = reg_act[reg_act["NUM_OPERATION"].isin(ops_sans_mem) & (reg_act["NUM_OPERATION"] != "")]
print(f"Reglements pointant (NUM_OPERATION) vers une operation SANS memoire: {len(reg_op_sans_mem)} | montant: {round(num(reg_op_sans_mem['MONTANT_REG']).sum(),3)}")

print("\n" + "="*70)
print("R5 — UNE OPERATION DANS UNE SEULE MEMOIRE")
print("="*70)
dup_op = op_act[op_act.duplicated(subset=["NUM_OPERATION"], keep=False)]
print(f"NUM_OPERATION duplique dans PR_OPERATION: {dup_op['NUM_OPERATION'].nunique()} numeros, {len(dup_op)} lignes")
if len(dup_op):
    chk = dup_op.groupby("NUM_OPERATION")["KEY_FP"].nunique()
    print(f"  dont rattaches a des memoires DIFFERENTES: {(chk>1).sum()}")
# présence dans actif ET annulé
both = set(k(op_act["NUM_OPERATION"])) & set(k(opan["NUM_OPERATION"]))
print(f"NUM_OPERATION presents a la fois dans PR_OPERATION et PR_OPERATION_FACTUREE_ANNULEE: {len(both)}")
if both:
    a = op_act[k(op_act['NUM_OPERATION']).isin(both)][["NUM_OPERATION","KEY_FP"]].set_index("NUM_OPERATION")
    b = opan[k(opan['NUM_OPERATION']).isin(both)][["NUM_OPERATION","KEY_FP"]].set_index("NUM_OPERATION")
    m = a.join(b, lsuffix="_ACT", rsuffix="_ANN")
    diff = m[m["KEY_FP_ACT"] != m["KEY_FP_ANN"]]
    print(f"  dont memoire active != memoire annulee: {len(diff)} (refacturation apres annulation: normal)")
# honoraires sur mémoire différente de la prime
hp = op_act[(k(op_act["NUM_FACTURE_HON"])!="") & op_act["HAS_FP"]]
hdiff = hp[(k(hp["NUM_FACTURE_HON"])!=k(hp["NUM_FACTURE_PRIME"])) | (k(hp["ANNEE_FACT_HON"])!=k(hp["ANNEE_FACT_PRIME"]))]
print(f"Operations avec facture HONORAIRES distincte de la memoire PRIME: {len(hdiff)} (a confirmer si autorise)")

print("\n" + "="*70)
print("SYNTHESE FINANCIERE")
print("="*70)
print(f"Total TOTAL_FACT (factures actives): {round(f2['TF'].sum(),3)}")
print(f"Total lettre (PR_REG_FACTURE actif): {round(rf_act['M'].sum(),3)}")
print(f"Total reglements actifs: {round(num(reg_act['MONTANT_REG']).sum(),3)}")
restant = f2["TF"] - f2["REGLE_CALC"]
print(f"Reste a regler calcule (factures non annulees): {round(restant[k(f2['FACTURE_ANNULEE'])!='O'].sum(),3)}")

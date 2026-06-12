# Déploiement manuel OVH — EVO02 (démo du 13/06/2026)

> Le ZIP `assurcore_prod_latest.zip` (31 Mo) a déjà été uploadé sur le VPS lors
> de la 1ère tentative : **`/root/assurcore_latest.zip`**. Il contient le module,
> les TSV DATA_REEL, les scripts de migration et le dump de config.
> Il ne reste que l'exécution côté serveur.

---

## Étape 1 — Connexion SSH au VPS

Dans PowerShell (le client OpenSSH est intégré à Windows) :

```powershell
ssh root@vps784643.ovh.net
```

Saisir le mot de passe root habituel (celui de `deploy_to_ovh.ps1`).

## Étape 2 — Dézipper et lancer le rebuild détaché

Une fois connecté au VPS, copier-coller ce bloc :

```bash
mkdir -p /root/assurcore_prod
unzip -oq /root/assurcore_latest.zip -d /root/assurcore_prod
cd /root/assurcore_prod
chmod +x rebuild_vps.sh
nohup ./rebuild_vps.sh > rebuild.log 2>&1 &
echo "Rebuild lancé, PID $!"
```

Grâce à `nohup`, le rebuild **continue même si la connexion SSH tombe**.

## Étape 3 — Suivre la progression (15 à 25 min)

```bash
tail -f /root/assurcore_prod/rebuild.log
```

(`Ctrl+C` arrête seulement l'affichage, jamais le rebuild. Si la connexion
tombe : se reconnecter en SSH et relancer le `tail -f`.)

Les 10 étapes attendues dans le log :

| Étape | Contenu | Durée indicative |
|---|---|---|
| 1/10 | Préparation addons (module + TSV + scripts) | < 1 min |
| 2/10 | Restart containers Docker | 1–3 min |
| 3/10 | Recréation base + restore dump (config/users) | 1–2 min |
| 4/10 | Upgrade module (schéma EVO02) | 2–4 min |
| 5/10 | Génération SQL ETL | 1–2 min |
| 6/10 | RESET + IMPORT métier (une transaction) | 2–5 min |
| 7/10 | Recalculs + Lot 4 FIFO → doit afficher **`>>> RECETTE CONFORME`** | 3–6 min |
| 8/10 | Correctifs états (timbre OFF, statuts, clients actifs, impayés) | < 1 min |
| 9/10 | Tests EVO02 → doit afficher **`>>> TESTS OK`** | 3–5 min |
| 10/10 | Restart final | < 1 min |

**Succès = dernière ligne : `=== REBUILD EVO02 TERMINE — recette conforme, tests OK ===`**

En cas d'échec, le log s'arrête sur `>>> ECHEC RECETTE LOT4` ou
`>>> ECHEC TESTS EVO02` (ou une erreur SQL/Docker). Récupérer les 60
dernières lignes et me les transmettre :

```bash
tail -n 60 /root/assurcore_prod/rebuild.log
```

## Étape 4 — Vérification finale

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://assurcore.metadidomi.com/web/health   # attendu : 200
docker ps          # 2 containers UP (web + db)
```

Puis dans le navigateur : **https://assurcore.metadidomi.com** (faire
`Ctrl+F5` à la première connexion pour purger le cache des assets).

## Check-list démo (5 min)

1. Connexion admin → ordre des menus : Tableau de Bord, Clients, Contrats, Mémoires opération, Opérations, Règlements, Trésorerie, Sinistres, Qualité des données, Paramétrage, Importation OCR.
2. Clients → ~4 678 actifs → ouvrir une fiche → bouton **Graphe** → naviguer (clic = nouveau sommet, ↗ = fiche, ← Précédent).
3. Mémoires opération → ouvrir une fiche → onglets **Opérations** et règlements.
4. Un règlement *Encaissé* → bouton **Ventiler sur opérations** → montants auto, Tout ventiler.
5. Tableau de Bord → Bordereau de production, Balance des impayés, Rendement par gestionnaire.
6. Qualité des données → 7 575 anomalies, filtres par type/sévérité.

---

## Annexe — seulement si le ZIP n'est plus sur le VPS

Vérifier d'abord, côté VPS : `ls -lh /root/assurcore_latest.zip` (attendu ≈ 31 Mo).
S'il est absent, le renvoyer depuis le PC (PowerShell, hors session SSH) :

```powershell
scp D:\Robot\assurcore_prod_latest.zip root@vps784643.ovh.net:/root/assurcore_latest.zip
```

Puis reprendre à l'Étape 2.

## Notes

- Le rebuild **écrase la base du VPS** (voulu pour la démo).
- Le script PowerShell figé peut être interrompu par `Ctrl+C` sans aucune conséquence : il était bloqué sur l'étape git locale, rien n'a été lancé côté serveur.
- Après la démo : remplacer le mot de passe root en clair par une clé SSH.

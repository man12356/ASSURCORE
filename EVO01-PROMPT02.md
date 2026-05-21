**Contexte : Évolution AssurCore — Étape 2 (Le Wizard de Validation)**

L'Étape 1 est validée. L'architecture est très propre (mention spéciale pour `action_test_ocr` et `selection_add`). 

Cependant, il faut faire une correction métier sur `_create_policy_from_ocr` : **Le script automatique ne doit JAMAIS créer de nouveau client (`res.partner`) de son propre chef.** C'est l'humain qui doit valider cette création via le Wizard pour éviter les doublons.

**Objectifs de l'Étape 2 :**

**1. Ajustement de `insurance.policy` (Le Modèle) :**
- Ajoute deux champs temporaires sur la police pour stocker la donnée brute lue par l'OCR en cas de doute : `ocr_raw_partner_name` (Char) et `ocr_raw_cin` (Char).
- Modifie ta logique `_create_policy_from_ocr` : Le script cherche le client par CIN ou par Nom exact. Si trouvé = il lie le `partner_id`. Si non trouvé = il laisse `partner_id` vide, mais il remplit `ocr_raw_partner_name` et `ocr_raw_cin`, puis crée la police en `draft_ocr`.

**2. Création du Wizard `insurance.ocr.wizard` (TransientModel) :**
- Ce wizard s'ouvre depuis une police en `draft_ocr`.
- **Champs du Wizard :** `policy_id` (Many2one), `ocr_raw_partner_name` (Readonly), `ocr_raw_cin` (Readonly), `partner_id` (Many2one), et un booléen `create_new_partner`.
- **Logique UI :**
  - Si un `partner_id` était déjà trouvé par le backend, il l'affiche.
  - S'il n'y a pas de `partner_id`, l'utilisateur peut chercher manuellement dans le Many2one.
  - S'il coche `create_new_partner`, cela doit déclencher la création du client (via ORM) avec les données `ocr_raw_partner_name` et `ocr_raw_cin` lors de la validation.
- **Action de validation (`action_confirm`) :** Met à jour la police avec le bon `partner_id`, efface les champs `ocr_raw_*`, et passe la police à l'état `'active'` (ou le statut par défaut post-brouillon).

Fournis le code Python mis à jour (le Wizard et les modifications de la police). Ne fournis pas encore le XML.
**Contexte : Évolution du module AssurCore existant**
Ceci est une évolution (nouvelle fonctionnalité) de notre module Odoo `AssurCore` actuel. Le modèle `insurance.policy` et les vues de base existent déjà. Ton code doit étendre l'existant, pas le recréer. Nous allons implémenter un workflow d'importation OCR pas à pas, en utilisant uniquement les composants Odoo Community (pas de dépendance au module Enterprise 'documents').

**Objectif de l'Étape 1 : Réception Email & Mock OCR**
Crée un nouveau modèle `insurance.document.parser` avec les spécifications techniques suivantes :

1. **Héritage :** Il doit hériter de `mail.thread` et `mail.activity.mixin` pour bénéficier de la gestion des alias email (`message_new`).

2. **Surcharge de `message_new` :** Lorsqu'un email contenant une pièce jointe PDF arrive, le système doit :
   - Sauvegarder la pièce jointe (`ir.attachment`).
   - Appeler une méthode privée `_mock_ocr_extract(attachment_id)`.

3. **Le Bouchon (Mock) et le Normalisateur :**
   - Crée une méthode `_normalize_ocr_data(raw_data, company_code)` qui aura pour but (plus tard) de standardiser les données hétérogènes des différentes compagnies. 
   - Pour l'instant, cette méthode est appelée par `_mock_ocr_extract` et doit retourner un dictionnaire Python fixe et standardisé basé sur notre dictionnaire interne AssurCore (données réelles) : 
     `{'compagnie': 'MAGHREBIA', 'num_police': 'J54554', 'nom_client': 'ABIDI ANOUAR', 'cin': '08422621', 'immatriculation': 'RS294328', 'prime_totale': 2858.781, 'date_effet': '2026-05-15', 'date_echeance': '2027-05-14'}`.

4. **Génération du Brouillon :** À partir de ce dictionnaire, le code doit créer ou mettre à jour un enregistrement `insurance.policy` en forçant l'ajout d'un nouveau statut : ajoute `state = 'draft_ocr'` dans les sélections existantes. 
   - L'Odoo ORM doit mapper les champs (ex: chercher l'ID de la compagnie Maghrebia, injecter les dates et la prime).
   - La pièce jointe PDF doit être automatiquement liée au Chatter de cette nouvelle police.

Fournis uniquement le code Python de ce modèle `insurance_document_parser.py` (et l'héritage éventuel de `insurance.policy` pour le nouveau statut) pour validation. Ne fournis pas de vues XML pour l'instant.
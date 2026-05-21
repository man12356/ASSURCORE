**Contexte : Évolution AssurCore — Étape 2.5 (Correction Métier B2B / Entreprises)**

Le code de l'Étape 2 est très propre et la logique métier de validation est respectée. Cependant, notre client courtier a fait une remarque métier majeure : **les assurés ne sont pas uniquement des personnes physiques (CIN), ce sont aussi très souvent des entreprises (Matricule Fiscal / Registre de Commerce).**

Il faut adapter le code Python existant (`insurance.policy`, le parser, et le wizard) pour gérer ces deux cas avant de passer aux vues XML.

**1. Ajustement des Modèles (`insurance.policy` & `insurance.document.parser`) :**
- Sur `insurance.policy`, ajoute deux nouveaux champs temporaires : `ocr_raw_company_type` (Selection : 'person' ou 'company') et `ocr_raw_matricule_fiscal` (Char).
- Dans le bouchon (Mock) de `insurance.document.parser`, le `_normalize_ocr_data` doit maintenant pouvoir retourner un dictionnaire avec : `{'company_type': 'company', 'nom_client': 'SOCIETE TUNISIENNE DE TRANSPORT', 'matricule_fiscal': '1234567/A/B/M/000', ...}` en plus du cas classique (CIN).
- Dans `_create_policy_from_ocr` : Modifie la logique de recherche. Si `company_type == 'company'`, le script doit chercher le partenaire d'abord par son matricule fiscal (`vat` ou champ équivalent dans ton modèle). S'il ne le trouve pas, il remplit `ocr_raw_company_type` et `ocr_raw_matricule_fiscal` sur la police.

**2. Ajustement du Wizard (`insurance.ocr.wizard`) :**
- Ajoute les champs `ocr_raw_company_type` et `ocr_raw_matricule_fiscal` au Wizard (en Readonly).
- **Logique de création (`action_confirm`) :** Si `create_new_partner` est coché, le code de création du `res.partner` doit s'adapter dynamiquement :
  - Si `ocr_raw_company_type == 'company'`, il crée le partenaire avec `is_company=True` et injecte le matricule fiscal.
  - Si `ocr_raw_company_type == 'person'`, il crée avec `is_company=False` et injecte le CIN.

Fais ces ajustements uniquement dans le code Python (les 3 fichiers concernés). Ne fournis pas encore les vues XML, nous validerons d'abord cette logique métier B2B.
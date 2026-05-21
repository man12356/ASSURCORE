lancer la tache exprimer dans le fichier EVO01-PROMPT01.md


Exécuté 2 commandes, lu un fichier
Exécuté 2 commandes, lu un fichier
Je note que le projet a évolué (nouveaux fichiers insurance_branch.py, insurance_mouvement_report.py, fleet_vehicle.py). Je lis l'état du modèle insurance.policy pour m'assurer que mon extension draft_ocr s'intègre proprement :


Exécuté 2 commandes
Exécuté 2 commandes
Parfait. Je génère maintenant le fichier complet :


Fichier créé, a exécuté une commande
Fichier créé, a exécuté une commande
✅ EVO01 — Étape 1 livrée. Voici le code produit et les décisions techniques :

insurance_document_parser.py — 643 lignes
Voir le fichier

Deux classes dans un seul fichier
InsurancePolicyOCRState (_inherit = 'insurance.policy')

Ajoute ('draft_ocr', 'Brouillon OCR (à valider)') via selection_add — sans écraser les états existants
ondelete={'draft_ocr': 'set default'} — safe si le module est désinstallé
Ajoute document_parser_id Many2one vers le parser source
Méthode action_validate_ocr_draft() pour la transition manuelle vers draft
InsuranceDocumentParser (_name = 'insurance.document.parser')

message_new() — intercepte l'email, détecte les PDF, gère les formats tuple/dict d'Odoo 17, crée ir.attachment, appelle _mock_ocr_extract()
_mock_ocr_extract(attachment_id) — bouchon Phase 1, persiste les données brutes en JSON pour auditabilité, appelle le normalisateur
_normalize_ocr_data(raw_data, company_code) — retourne exactement le dictionnaire demandé : {'compagnie': 'MAGHREBIA', 'num_police': 'J54554', 'nom_client': 'ABIDI ANOUAR', 'cin': '08422621', 'immatriculation': 'RS294328', 'prime_totale': 2858.781, 'date_effet': '2026-05-15', 'date_echeance': '2027-05-14'} — avec le routing multi-compagnies commenté prêt pour la Phase 2
_create_policy_from_ocr() — ORM complet : résout insurance.company par nom (crée si absent), résout res.partner par CIN puis nom (crée si inconnu), idempotence sur num_police + company_ins_id, lie le PDF au Chatter de la police
action_test_ocr() — bouton de test manuel sans email (pour recette QA)
Mise à jour Odoo
powershell
docker exec assurcore_web odoo --config=/etc/odoo/odoo.conf -d assurcore_db -u assurcore --stop-after-init
docker compose -p assurcore start web
lancer la tache decrit dans le fichier "EVO01-PROMPT02.md"


Lu un fichier
Lu un fichier
Je lis d'abord l'état actuel de insurance_document_parser.py pour faire des éditions ciblées sans réécrire inutilement :


Exécuté 2 commandes
Exécuté 2 commandes
Maintenant j'ai tout ce qu'il faut. Je fais les deux livrables en parallèle :

Livrable 1 — Correction ciblée dans insurance_document_parser.py (suppression création auto-partenaire + ajout champs ocr_raw_* sur la police)

Livrable 2 — Nouveau fichier insurance_ocr_wizard.py


3 fichiers modifiés
3 fichiers modifiés
Maintenant le Wizard :


Exécuté 3 commandes, fichier créé
Exécuté 3 commandes, fichier créé
Le fichier est tronqué à la ligne 635. Je récupère la fin manquante et complète :


Exécuté 4 commandes
Exécuté 4 commandes
Les 2 "X" sont de faux positifs — les espaces supplémentaires dans le code trompent la recherche exacte. Les lignes 281-284 confirment que le code est correct. Je synchronise :


A exécuté une commande
A exécuté une commande
✅ EVO01 — Étape 2 livrée. Voici le détail des modifications :

Correction dans insurance_document_parser.py
InsurancePolicyOCRState — 2 nouveaux champs sur insurance.policy :

python
ocr_raw_partner_name = fields.Char(copy=False)  # nom brut OCR si client non trouvé
ocr_raw_cin          = fields.Char(copy=False)  # CIN brut OCR idem
_create_policy_from_ocr — Règle métier respectée :

La recherche par CIN est conservée (= exact, pas ilike)
Le repli par nom passe de ilike à = exact (moins risqué en production)
Plus aucune création automatique de res.partner
Si client non trouvé → ocr_raw_partner_name et ocr_raw_cin alimentés + log WARNING → Wizard requis
Nouveau fichier insurance_ocr_wizard.py — insurance.ocr.wizard (323 lignes)
TransientModel avec :

default_get() — pré-charge les données OCR brutes depuis la police via le contexte
ocr_raw_partner_name / ocr_raw_cin (readonly) — affichés pour guider l'opérateur
partner_id — recherche manuelle parmi les partenaires existants
create_new_partner (Boolean) — déclenche la création manuelle
Exclusivité mutuelle : _onchange_partner_id décoche create_new_partner, et inversement
_check_partner_choice() — ValidationError si aucun choix cohérent
action_confirm() : crée le partenaire si demandé → lie à la police → efface ocr_raw_* → state='draft' → rouvre la fiche police
lancer la tache decrit dans le fichier "EVO01-PROMPT025.md"


Lu un fichier
Lu un fichier
Je lis les sections clés des 2 fichiers à modifier pour faire des éditions chirurgicales :


A exécuté une commande
A exécuté une commande
J'ai les coordonnées exactes de chaque section. Je fais les 3 séries d'éditions :

Fichier 1 — insurance_document_parser.py : 3 éditions


Exécuté 16 commandes, 3 fichiers modifiés
Exécuté 16 commandes, 3 fichiers modifiés
insurance_document_parser.py est propre (750 lignes). Je passe maintenant aux modifications du wizard :

Fichier 2 — insurance_ocr_wizard.py : 4 éditions ciblées


6 fichiers modifiés
6 fichiers modifiés
Validation finale et synchronisation :


Exécuté 8 commandes
Exécuté 8 commandes
Le fichier est tronqué une nouvelle fois. Je complète avec Python direct (évite les problèmes heredoc) :


Exécuté 3 commandes, fichier modifié
Exécuté 3 commandes, fichier modifié
✅ EVO01 — Étape 2.5 livrée. Voici le détail précis de chaque modification :

insurance_document_parser.py — InsurancePolicyOCRState
2 nouveaux champs temporaires sur insurance.policy :

python
ocr_raw_company_type      = fields.Selection([('person','Personne physique'),('company','Entreprise')])
ocr_raw_matricule_fiscal  = fields.Char()
_normalize_ocr_data — Le dictionnaire normalisé intègre maintenant company_type + matricule_fiscal dans sa convention, avec le mock B2C actuel :

python
{'company_type': 'person', 'cin': '08422621', 'matricule_fiscal': '', ...}
Pour tester B2B, il suffit de décommenter l'exemple {'company_type': 'company', 'matricule_fiscal': '1234567/A/B/M/000', ...}.

_create_policy_from_ocr — Branche B2B/B2C complète :

company_type='company' → priorité matricule_fiscal + is_company=True, repli raison_sociale exacte
company_type='person' → priorité cin, repli nom exact
Si non trouvé : alimente ocr_raw_company_type et ocr_raw_matricule_fiscal (ou ocr_raw_cin) selon le type
insurance_ocr_wizard.py
2 champs readonly ajoutés : ocr_raw_company_type, ocr_raw_matricule_fiscal

1 champ de saisie ajouté : new_partner_matricule_fiscal

default_get : charge les 2 nouveaux champs depuis la police, pré-sélectionne new_partner_type = 'E'/'P' selon l'OCR

_onchange_create_new_partner : si company_type='company' → pré-remplit new_partner_matricule_fiscal + force type='E' ; sinon → pré-remplit new_partner_cin + force type='P'

action_confirm — Création adaptée dynamiquement :

python
if is_company:  # Entreprise
    create_vals['matricule_fiscal'] = mf
    create_vals['assujetti_tva'] = True
else:           # Personne physique
    create_vals['cin'] = cin
Les 4 champs ocr_raw_* sont effacés sur la police après confirmation.

lancer la tache decrit dans le fichier "EVO01-PROMPT03.md"


Lu un fichier, a exécuté une commande, fichier créé
Lu un fichier, a exécuté une commande, fichier créé
Maintenant mettre à jour la vue police pour ajouter draft_ocr et les boutons OCR :


Fichier modifié
Fichier modifié
Ajouter un ruban visuel pour l'état draft_ocr et la section OCR dans la fiche police :


Fichier modifié
Fichier modifié
Ajouter la section des données OCR brutes dans le notebook de la police (visible si draft_ocr) :


Fichier modifié
Fichier modifié
Maintenant mettre à jour le manifest, les droits, valider et synchroniser :


Exécuté 7 commandes
Exécuté 7 commandes
Le seul "faux X" est un problème de pattern de recherche dans mon script ('target>new<' vs >new<). La valeur target = "new" est bien présente à la ligne 112. Toutes les vérifications réelles sont vertes.


A exécuté une commande
A exécuté une commande
✅ EVO01 — Étape 3 livrée et validée. Voici le récapitulatif complet de ce qui a été produit :

views/insurance_ocr_wizard_views.xml — 5 composants
Vue Form du Wizard (popup) — Structure en deux sous-groupes côte-à-côte :

"Données lues par l'IA" : ocr_raw_company_type (badge coloré), ocr_raw_partner_name, ocr_raw_cin (visible si person), ocr_raw_matricule_fiscal (visible si company)
"Action (Liaison Client)" : partner_id (recherche libre) + create_new_partner (booléen)
Zone de création conditionnelle (visible si create_new_partner) avec champs adaptés B2C/B2B
Footer : Confirmer et valider (oe_highlight) + Annuler (special="cancel")
Action target="new" — Force l'affichage en pop-up.

Vue Form du Parseur OCR (insurance.document.parser) — Avec statusbar, bouton "Simuler OCR", résumé des données extraites, onglet JSON audit.

Vue Liste du Parseur — Avec badges colorés par état, colonnes clés.

Menu "Importation OCR" → sous menu_assurcore_root.

views/insurance_policy_views.xml — 3 modifications
Statusbar : draft_ocr ajouté → statusbar_visible="draft_ocr,draft,active,unpaid"

Header (visible uniquement si state='draft_ocr') :

Bouton "Valider les données OCR" (oe_highlight btn-warning) → ouvre le wizard en popup
Bouton "Simuler Réception OCR" (btn-secondary) → test direct sans email
Ruban violet "Brouillon OCR" + onglet "Données OCR brutes" dans le notebook avec les champs ocr_raw_* en lecture seule et un bandeau d'avertissement.

Mise à jour Odoo
powershell
docker exec assurcore_web odoo --config=/etc/odoo/odoo.conf -d assurcore_db -u assurcore --stop-after-init
docker compose -p assurcore start web





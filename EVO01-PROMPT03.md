**Contexte : Évolution AssurCore — Étape 3 (L'Interface Utilisateur / Vues XML)**

Le backend (Python) pour le workflow OCR (avec la gestion B2B/B2C) est parfait. Nous passons maintenant à la dernière étape : la création des interfaces graphiques (Vues XML).

**Objectifs de l'Étape 3 :**

**1. Action et Vue du Wizard (`views/insurance_ocr_wizard_views.xml`) :**
- Crée l'action de fenêtre (`ir.actions.act_window`) pour le modèle `insurance.ocr.wizard` avec `target="new"` pour forcer l'affichage en Pop-up.
- Crée la vue Form du Wizard.
- Structure la vue avec un `<group>` divisé en deux colonnes (ou deux sous-groupes) :
  - **Sous-groupe "Données lues par l'IA" :** Affiche `ocr_raw_company_type` et `ocr_raw_partner_name`. Utilise l'attribut `invisible` pour n'afficher `ocr_raw_cin` que si type = 'person', et `ocr_raw_matricule_fiscal` que si type = 'company'.
  - **Sous-groupe "Action (Liaison Client)" :** Affiche le champ `partner_id` et le booléen `create_new_partner`.
- **Pied de page (Footer) :** Ajoute un `<button name="action_confirm" string="Confirmer" type="object" class="oe_highlight"/>` et un bouton d'annulation standard (`special="cancel"`).

**2. Mise à jour de la vue Police (`views/insurance_policy_views.xml`) :**
- Modifie la vue form existante de `insurance.policy` via un héritage (ou une mise à jour directe si tu as le fichier complet).
- Ajoute le statut `draft_ocr` dans le champ `state` (widget statusbar).
- Dans le `<header>`, ajoute un bouton "Valider les données OCR" (classe `btn-warning` ou `oe_highlight`, type `action`) pointant vers l'action du Wizard. Ce bouton doit utiliser `invisible="state != 'draft_ocr'"`.

**3. Bouton de Test (Optionnel mais recommandé pour les tests) :**
- Ajoute temporairement un bouton "Simuler Réception OCR" dans le header de la vue liste (tree) ou formulaire de la police pour appeler ta méthode `action_test_ocr()`.

Fournis le code XML complet pour ces vues.
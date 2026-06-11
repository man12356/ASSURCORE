#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validateur sémantique EVO02 : simule les contrôles d'installation Odoo.
- champs référencés dans les vues EVO02 vs champs définis (AST des modèles)
- cibles xpath/field des héritages présentes dans les vues parentes
- inherit_id / action / menu / ref existants
- ACL : model_ids cohérents
- manifest : fichiers présents, ordre données
"""
import ast, os, re, sys
import xml.etree.ElementTree as ET

BASE = '/sessions/loving-great-lovelace/mnt/ASSURPROD/assurcore'
errors, warns = [], []

# ── 1. AST : modèles et champs Python ────────────────────────────────────────
model_fields = {}   # model -> set(fields)
model_defs = {}     # model -> [classes]
inherits_map = {}   # model -> set(parents)

COMMON = {'id', 'display_name', 'create_uid', 'create_date', 'write_uid',
          'write_date', '__last_update', 'activity_ids', 'message_ids',
          'message_follower_ids', 'activity_state'}

def class_models(node):
    name = inherit = None
    inherit_list = []
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == '_name':
                    if isinstance(stmt.value, ast.Constant):
                        name = stmt.value.value
                if isinstance(t, ast.Name) and t.id == '_inherit':
                    v = stmt.value
                    if isinstance(v, ast.Constant):
                        inherit = v.value
                    elif isinstance(v, (ast.List, ast.Tuple)):
                        inherit_list = [e.value for e in v.elts
                                        if isinstance(e, ast.Constant)]
    return name, inherit, inherit_list

def class_fields(node):
    out = set()
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            f = stmt.value.func
            if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                    and f.value.id == 'fields'):
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        out.add(t.id)
    return out

for root_dir, _, files in os.walk(os.path.join(BASE, 'models')):
    for fn in files:
        if not fn.endswith('.py'):
            continue
        src = open(os.path.join(root_dir, fn), encoding='utf-8').read()
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            errors.append(f'PY SYNTAXE {fn}: {e}')
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                name, inherit, ilist = class_models(node)
                model = name or inherit or (ilist[0] if ilist else None)
                if not model:
                    continue
                flds = class_fields(node)
                model_fields.setdefault(model, set()).update(flds)
                if inherit and name and inherit != name:
                    inherits_map.setdefault(name, set()).add(inherit)
                for p in ilist:
                    if p != model:
                        inherits_map.setdefault(model, set()).add(p)

# fusion des champs hérités (mixins du module)
def all_fields(model, seen=None):
    seen = seen or set()
    if model in seen:
        return set()
    seen.add(model)
    out = set(model_fields.get(model, set()))
    for p in inherits_map.get(model, ()):  # mixins
        out |= all_fields(p, seen)
    return out

# ── 2. Vues existantes : index des view-id -> (model, arch xml) ─────────────
views = {}
for root_dir, _, files in os.walk(os.path.join(BASE, 'views')):
    for fn in files:
        if not fn.endswith('.xml'):
            continue
        path = os.path.join(root_dir, fn)
        try:
            t = ET.parse(path)
        except ET.ParseError as e:
            errors.append(f'XML PARSE {fn}: {e}')
            continue
        for rec in t.iter('record'):
            if rec.get('model') != 'ir.ui.view':
                continue
            vid = rec.get('id')
            model = arch = inh = None
            for f in rec.findall('field'):
                if f.get('name') == 'model':
                    model = (f.text or '').strip()
                elif f.get('name') == 'arch':
                    arch = f
                elif f.get('name') == 'inherit_id':
                    inh = f.get('ref')
            views[vid] = {'model': model, 'arch': arch, 'inherit': inh,
                          'file': fn}

# ── 3. Contrôles sur les fichiers EVO02 ──────────────────────────────────────
EVO_FILES = [f for f in os.listdir(os.path.join(BASE, 'views'))
             if f.startswith('evo02')]

def fields_in_arch(arch):
    return [(el.get('name'), el) for el in arch.iter('field')
            if el.get('name')]

def check_view(vid, info):
    model = info['model']
    arch = info['arch']
    if arch is None or not model:
        return
    known = all_fields(model) | COMMON
    if not model_fields.get(model) and model not in inherits_map:
        warns.append(f"{info['file']}::{vid}: modèle {model} non trouvé en AST "
                     f"(modèle standard Odoo ?) — champs non vérifiés")
        return
    # champs du modèle référencés (hors sous-tree de champs o2m)
    def walk(el, ctx_model, depth=0):
        ctx_known = all_fields(ctx_model) | COMMON
        for child in el:
            if child.tag == 'field':
                fname = child.get('name')
                if fname and fname not in ctx_known and ctx_known - COMMON:
                    errors.append(
                        f"{info['file']}::{vid}: champ « {fname} » absent du "
                        f"modèle {ctx_model}")
                # sous-vue o2m : on ne connaît pas le comodel via AST simple →
                # vérif limitée aux modèles evo02 connus
                sub = {'allocation_ids': 'insurance.settlement.imputation',
                       'imputation_ids': 'insurance.settlement.imputation',
                       'anomaly_ids': 'insurance.anomaly'}.get(fname)
                if len(child) and sub:
                    for tre in child:
                        walk(tre, sub, depth + 1)
                elif len(child):
                    pass  # comodel inconnu : ignoré
            else:
                walk(child, ctx_model, depth)
    walk(arch, model)
    # héritage : cible xpath / field
    if info['inherit']:
        ref = info['inherit'].split('.')[-1]
        parent = views.get(ref)
        if not parent:
            errors.append(f"{info['file']}::{vid}: inherit_id introuvable : "
                          f"{info['inherit']}")
            return
        parch = parent['arch']
        ptext = ET.tostring(parch, encoding='unicode') if parch is not None else ''
        for el in arch.iter():
            if el.tag == 'xpath':
                expr = el.get('expr', '')
                m = re.findall(r"@name='([^']+)'", expr)
                tag = re.findall(r"//(\w+)", expr)
                ok = True
                for nm in m:
                    if f"name=\"{nm}\"" not in ptext and f"name='{nm}'" not in ptext:
                        ok = False
                if tag and not m:
                    ok = f'<{tag[0]}' in ptext
                if not ok:
                    errors.append(f"{info['file']}::{vid}: cible xpath "
                                  f"« {expr} » introuvable dans {ref}")
            elif el.tag in ('field', 'tree', 'search', 'sheet', 'footer',
                            'header', 'form') and el.get('position'):
                nm = el.get('name')
                if el.tag == 'field' and nm:
                    if (f"name=\"{nm}\"" not in ptext
                            and f"name='{nm}'" not in ptext):
                        errors.append(f"{info['file']}::{vid}: ancre field "
                                      f"« {nm} » absente de {ref}")
                elif el.tag in ('sheet', 'footer', 'header', 'tree', 'search'):
                    if f'<{el.tag}' not in ptext:
                        errors.append(f"{info['file']}::{vid}: ancre "
                                      f"<{el.tag}> absente de {ref}")

for vid, info in views.items():
    if info['file'] in EVO_FILES:
        check_view(vid, info)

# menus / actions ref dans les fichiers evo02
all_ids = set(views)
for root_dir, _, files in os.walk(BASE):
    for fn in files:
        if fn.endswith('.xml'):
            try:
                t = ET.parse(os.path.join(root_dir, fn))
            except ET.ParseError:
                continue
            for rec in t.iter('record'):
                if rec.get('id'):
                    all_ids.add(rec.get('id'))
            for mi in t.iter('menuitem'):
                if mi.get('id'):
                    all_ids.add(mi.get('id'))

for fn in EVO_FILES + ['evo02_anomaly_types.xml', 'evo02_sequences.xml']:
    for sub in ('views', 'data'):
        path = os.path.join(BASE, sub, fn)
        if not os.path.exists(path):
            continue
        t = ET.parse(path)
        for mi in t.iter('menuitem'):
            for attr in ('parent', 'action'):
                ref = mi.get(attr)
                if ref:
                    rid = ref.split('.')[-1]
                    if rid not in all_ids:
                        errors.append(f'{fn}: menuitem {mi.get("id")} → '
                                      f'{attr} introuvable : {ref}')

# ── 4. ACL ────────────────────────────────────────────────────────────────────
new_models = {'insurance.anomaly', 'insurance.anomaly.type'}
csv_path = os.path.join(BASE, 'security', 'ir.model.access.csv')
csv = open(csv_path, encoding='utf-8').read()
for m in new_models:
    token = 'model_' + m.replace('.', '_')
    if token not in csv:
        errors.append(f'ACL manquante pour {m} ({token})')

# ── 5. Manifest ───────────────────────────────────────────────────────────────
man = open(os.path.join(BASE, '__manifest__.py'), encoding='utf-8').read()
data_files = re.findall(r"'((?:data|views|security)/[^']+)'", man)
for f in data_files:
    if not os.path.exists(os.path.join(BASE, f)):
        errors.append(f'Manifest : fichier manquant {f}')
for f in ('static/src/js/evo02_graph_explorer.js',
          'static/src/xml/evo02_graph_explorer.xml'):
    if f"'assurcore/{f}'" not in man:
        errors.append(f'Manifest assets : {f} non déclaré')
    if not os.path.exists(os.path.join(BASE, f)):
        errors.append(f'Asset manquant : {f}')
# l'XML de data anomalies doit être chargé AVANT les vues qui s'y réfèrent
order = [f for f in data_files]
def pos(name):
    return next((i for i, f in enumerate(order) if name in f), -1)
if pos('evo02_anomaly_types') > pos('evo02_health_views') >= 0:
    errors.append('Manifest : evo02_anomaly_types.xml doit précéder les vues')

# ── Résultat ──────────────────────────────────────────────────────────────────
print(f'Modèles analysés : {len(model_fields)} | Vues indexées : {len(views)}')
for w in warns:
    print('WARN :', w)
if errors:
    print(f'\n{len(errors)} ERREUR(S) :')
    for e in errors:
        print(' ✗', e)
    sys.exit(1)
print('\n✔ AUCUNE ERREUR — vues/champs/ancres/ACL/manifest cohérents')

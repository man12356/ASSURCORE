/* global React, NavBar, Sidebar, ControlPanel, Icon, I */
/*
  Fiche Client Famille/Payeur — Vue Form Odoo.
  res.partner étendu avec is_family / is_payer, lignes res.partner.member,
  insurance.policy, account.move (quittances).
*/

const { useState: useStateForm } = React;

function tndF(n) { return n.toLocaleString("fr-FR", { minimumFractionDigits: 3, maximumFractionDigits: 3 }) + " TND"; }
function tndFShort(n) { return n.toLocaleString("fr-FR", { minimumFractionDigits: 0, maximumFractionDigits: 0 }); }

const MEMBERS = [
  { name: "Mohamed Ben Salem",   role: "Chef de famille · Payeur", age: 48, cin: "09234567",  init: "MB", contracts: 2, paid: 4520.500, due:  0,        primary: true },
  { name: "Leïla Ben Salem-Triki",role: "Conjoint",                age: 45, cin: "08891234",  init: "LB", contracts: 1, paid: 1980.000, due:  0,        primary: false },
  { name: "Yassine Ben Salem",   role: "Enfant",                   age: 18, cin: "12567890",  init: "YB", contracts: 1, paid:  650.000, due: 1245.750,  primary: false },
  { name: "Sarra Ben Salem",     role: "Enfant",                   age: 14, cin: "—",         init: "SB", contracts: 0, paid:    0,    due:  0,        primary: false },
];

const POLICIES = [
  { ico: "car",   num: "AUTO-2024-0142", title: "Peugeot 208 GT — 183 TU 4521",   sub: "Membre · Yassine Ben Salem",   cie: "comar", branch: "Auto",  prime: 1245.750, exp: "02/04/27", status: "unpaid",  retard: "43j" },
  { ico: "car",   num: "AUTO-2024-0287", title: "Renault Clio V — 219 TU 7833",   sub: "Membre · Leïla Ben Salem",     cie: "gat",   branch: "Auto",  prime: 1180.500, exp: "14/06/27", status: "paid",    retard: null },
  { ico: "heart", num: "SAN-2023-0089",  title: "Santé Famille Premium",          sub: "4 bénéficiaires · Plafond 50k",cie: "comar", branch: "Santé", prime: 3450.000, exp: "01/09/26", status: "paid",    retard: null },
  { ico: "home",  num: "MRH-2022-1547",  title: "Appartement La Marsa",           sub: "Surface 145 m² · 4 pièces",    cie: "star",  branch: "MRH",   prime:  920.000, exp: "12/11/26", status: "pending", retard: "À échoir 14j" },
  { ico: "plane", num: "VOY-2026-0012",  title: "Voyage Schengen 30j",            sub: "Mohamed + Leïla",              cie: "astree",branch: "Voyage",prime:  185.000, exp: "30/06/26", status: "paid",    retard: null },
];

function PolicyIcon({ k }) {
  return <span className="icn"><Icon d={I[k]} size={14} /></span>;
}

function CompagnieTag2({ k }) {
  const label = { star: "STAR", gat: "GAT", lloyd: "LLOYD", comar: "COMAR", astree: "ASTREE" }[k];
  return (<span className={"cie " + k}><span className="swatch" />{label}</span>);
}

function Form({ persona = "courtier", variant = "shadow" }) {
  const isAgent = persona === "agent";
  const filteredPolicies = isAgent ? POLICIES.filter(p => p.cie === "star") : POLICIES;

  const [activeTab, setActiveTab] = useStateForm("polices");

  const totalPaid   = MEMBERS.reduce((s, m) => s + m.paid, 0);
  const totalDue    = MEMBERS.reduce((s, m) => s + m.due,  0);
  const balance     = totalDue;   // solde dû global

  return (
    <div className={"o_action_manager cards-" + variant}>
      <NavBar activeSection="Clients" />
      <div className="o_app_body">
        <Sidebar active="clients" />
        <div className="o_content_wrap">

          <ControlPanel
            breadcrumb={["Clients", "Familles & Payeurs", "Ben Salem, Mohamed"]}
            searchPlaceholder="Rechercher un client…"
            primaryAction="Nouveau client"
            filters={[
              { label: "Mes clients", active: true, icon: I.users, count: 184 },
              { label: "Familles",    count: 76 },
              { label: "Entreprises", count: 108 },
              { label: "Avec impayés", icon: I.warn, count: 23 },
            ]}
            views={[{ label: "Form", active: true }, { label: "Liste" }, { label: "Kanban" }]}
            pager="42 / 184"
          />

          <div className="o_content" style={{ padding: '20px 20px 0' }}>

            <div className="o_form_view">

              {/* Toolbar above sheet (Odoo statusbar buttons + breadcrumb actions row) */}
              <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', maxWidth:1100, margin:'0 auto', width:'100%'}}>
                <div style={{display:'flex', gap:6}}>
                  <button className="btn btn-primary"><Icon d={I.edit} size={12} /> Modifier</button>
                  <button className="btn btn-secondary">Créer</button>
                  <button className="btn btn-ghost">Action ▾</button>
                </div>
                <div style={{display:'flex', alignItems:'center', gap:8, fontSize:11, color:'var(--ac-ink-500)', fontFamily:'var(--font-mono)'}}>
                  <span>res.partner · is_family=True</span>
                  <span style={{padding:'2px 6px', background:'var(--ac-ink-50)', borderRadius:4}}>ID #4127</span>
                </div>
              </div>

              <div className="o_form_sheet">

                {/* Ribbon (oe_ribbon) */}
                <div className="oe_ribbon">Client VIP</div>

                {/* Statusbar */}
                <div className="o_form_statusbar">
                  <div className="o_statusbar_status">
                    <span className="o_arrow_button done">Prospect</span>
                    <span className="o_arrow_button done">Actif</span>
                    <span className="o_arrow_button btn_active">Fidèle (5+ ans)</span>
                    <span className="o_arrow_button">VIP</span>
                    <span className="o_arrow_button">Résilié</span>
                  </div>
                  <div className="o_statusbar_buttons">
                    <button className="btn btn-secondary btn-sm">Lancer relance</button>
                    <button className="btn btn-secondary btn-sm">Promouvoir VIP</button>
                  </div>
                </div>

                {/* Smart buttons (oe_button_box) */}
                <div className="oe_button_box">
                  <button className="oe_stat_button">
                    <span className="icon"><Icon d={I.receipt} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">47</span>
                      <span className="o_stat_text">Quittances</span>
                    </span>
                  </button>
                  <button className={"oe_stat_button" + (totalDue > 0 ? " danger" : "")}>
                    <span className="icon"><Icon d={I.warn} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">{totalDue > 0 ? "1" : "0"}</span>
                      <span className="o_stat_text">Impayé{totalDue > 0 ? "" : ""} ({tndFShort(totalDue)} TND)</span>
                    </span>
                  </button>
                  <button className="oe_stat_button">
                    <span className="icon"><Icon d={I.shield} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">{filteredPolicies.length}</span>
                      <span className="o_stat_text">Polices actives</span>
                    </span>
                  </button>
                  <button className="oe_stat_button warning">
                    <span className="icon"><Icon d={I.warn} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">2</span>
                      <span className="o_stat_text">Sinistres ouverts</span>
                    </span>
                  </button>
                  <button className="oe_stat_button">
                    <span className="icon"><Icon d={I.doc} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">28</span>
                      <span className="o_stat_text">Documents</span>
                    </span>
                  </button>
                  <button className="oe_stat_button success">
                    <span className="icon"><Icon d={I.euro} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">{tndFShort(totalPaid)}</span>
                      <span className="o_stat_text">Encaissé YTD (TND)</span>
                    </span>
                  </button>
                  <button className="oe_stat_button">
                    <span className="icon"><Icon d={I.chat} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">12</span>
                      <span className="o_stat_text">Communications</span>
                    </span>
                  </button>
                  <button className="oe_stat_button">
                    <span className="icon"><Icon d={I.chart} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">12,4 %</span>
                      <span className="o_stat_text">Score fidélité</span>
                    </span>
                  </button>
                </div>

                {/* Title (oe_title) + Highlight balance */}
                <div className="oe_title">
                  <div className="avatar">BS</div>
                  <div className="title_main">
                    <h1 className="h1">
                      Famille Ben Salem
                      <span className="sub">· Mohamed Ben Salem (payeur principal)</span>
                    </h1>
                    <div className="tags">
                      <span className="badge info"><span className="d" />Famille</span>
                      <span className="badge neutral"><span className="d" />4 membres</span>
                      <span className="badge neutral"><span className="d" />Client depuis 2018</span>
                      <span className="badge paid"><span className="d" />Bon payeur · DSO 12j</span>
                      {!isAgent && <span className="badge info"><span className="d" />3 compagnies</span>}
                    </div>
                  </div>
                  <div className={"balance" + (balance > 0 ? " danger" : "")}>
                    <div className="lbl">Solde global · famille</div>
                    <div className="v">{balance > 0 ? "−" : ""}{tndF(Math.abs(balance))}</div>
                    <div style={{fontSize:11, opacity:.8, marginTop:2}}>
                      {balance > 0
                        ? "1 quittance en souffrance · 43j de retard"
                        : "Toutes quittances soldées"}
                    </div>
                  </div>
                </div>

                {/* Group fields */}
                <div className="o_inner_group">
                  <h4>Identité du payeur</h4>

                  <label className="o_field_label">Nom complet</label>
                  <div className="o_field edit">Mohamed Ben Salem</div>
                  <label className="o_field_label">CIN</label>
                  <div className="o_field edit" style={{fontFamily:'var(--font-mono)'}}>09 234 567</div>

                  <label className="o_field_label">Date de naissance</label>
                  <div className="o_field edit">14/03/1977 <span className="muted">(48 ans)</span></div>
                  <label className="o_field_label">Matricule Fiscal</label>
                  <div className="o_field edit" style={{fontFamily:'var(--font-mono)'}}>1284571/N/A/M/000</div>

                  <label className="o_field_label">Profession</label>
                  <div className="o_field edit">Ingénieur Télécom — Tunisie Telecom</div>
                  <label className="o_field_label">CSP</label>
                  <div className="o_field edit">CSP+ <span className="muted">(catégorie 4)</span></div>

                  <h4>Contact</h4>

                  <label className="o_field_label">Adresse</label>
                  <div className="o_field edit">Résidence Les Jasmins, Bloc B — La Marsa 2078, Tunis</div>
                  <label className="o_field_label">Téléphone</label>
                  <div className="o_field edit"><a href="#">+216 22 184 720</a></div>

                  <label className="o_field_label">E-mail</label>
                  <div className="o_field edit"><a href="#">m.bensalem@gmail.com</a></div>
                  <label className="o_field_label">Canal préféré</label>
                  <div className="o_field edit">WhatsApp</div>

                  <h4>Paramètres financiers</h4>

                  <label className="o_field_label">Mode de règlement</label>
                  <div className="o_field edit">Prélèvement RIB · 11 002 040 21458736 31</div>
                  <label className="o_field_label">Échéance préférée</label>
                  <div className="o_field edit">Le 5 du mois</div>

                  <label className="o_field_label">Limite crédit</label>
                  <div className="o_field edit">{tndF(15000)}</div>
                  <label className="o_field_label">DSO famille</label>
                  <div className="o_field edit">12 jours <span className="muted">(vs. moy. portefeuille 38j)</span></div>
                </div>

                {/* Notebook */}
                <div className="o_notebook">
                  <div className="o_notebook_headers">
                    {[
                      { k: "membres",   l: "Membres",    n: MEMBERS.length },
                      { k: "polices",   l: "Polices",    n: filteredPolicies.length },
                      { k: "quittances",l: "Quittances", n: 47 },
                      { k: "sinistres", l: "Sinistres",  n: 2 },
                      { k: "documents", l: "Documents",  n: 28 },
                      { k: "historique",l: "Historique", n: null },
                    ].map(t => (
                      <div key={t.k} className={"nav" + (t.k === activeTab ? " active" : "")}
                           onClick={() => setActiveTab(t.k)}>
                        <span>{t.l}</span>
                        {t.n != null && (
                          <span style={{
                            background: t.k === activeTab ? 'var(--ac-blue-100)' : 'var(--ac-ink-50)',
                            color: t.k === activeTab ? 'var(--ac-blue-700)' : 'var(--ac-ink-500)',
                            borderRadius: 4, padding: '0 6px', fontSize: 11,
                          }}>
                            {t.n}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>

                  <div className="o_notebook_content">
                    {activeTab === "membres" && (
                      <div className="members">
                        {MEMBERS.map((m, i) => (
                          <div key={i} className="member">
                            <div className="top">
                              <div className="av">{m.init}</div>
                              <div>
                                <div className="name">{m.name}</div>
                                <div className="role">{m.role} · {m.age} ans</div>
                              </div>
                            </div>
                            <div style={{fontSize:11, color:'var(--ac-ink-500)', fontFamily:'var(--font-mono)'}}>CIN {m.cin}</div>
                            <div className="meta">
                              <span className="badge neutral"><span className="d" />{m.contracts} polic{m.contracts === 1 ? "e" : "es"}</span>
                              {m.due > 0
                                ? <span className="badge unpaid"><span className="d" />{tndFShort(m.due)} TND dû</span>
                                : <span className="badge paid"><span className="d" />À jour</span>
                              }
                              {m.primary && <span className="badge info"><span className="d" />Payeur</span>}
                            </div>
                            <div className="row"><span>Encaissé YTD</span><strong>{tndFShort(m.paid)} TND</strong></div>
                          </div>
                        ))}
                        <div className="member" style={{
                          alignItems:'center', justifyContent:'center', textAlign:'center',
                          border:'1px dashed var(--ac-ink-100)', background:'transparent', cursor:'pointer',
                          color:'var(--ac-ink-500)'
                        }}>
                          <Icon d={I.plus} size={18} stroke={1.8} />
                          <div style={{fontWeight:500}}>Ajouter un membre</div>
                        </div>
                      </div>
                    )}

                    {activeTab === "polices" && (
                      <>
                        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8}}>
                          <div style={{fontSize:11, color:'var(--ac-ink-500)', fontFamily:'var(--font-mono)'}}>
                            insurance.policy WHERE family_id = #4127 {isAgent && "AND company_id = STAR"}
                          </div>
                          <button className="btn btn-secondary btn-sm">+ Ajouter une police</button>
                        </div>
                        <div className="policies" style={{borderTop:'1px solid var(--ac-ink-100)'}}>
                          {filteredPolicies.map((p, i) => (
                            <div key={i} className="policy">
                              <PolicyIcon k={p.ico} />
                              <div className="ttl">
                                {p.title}
                                <span className="sub">{p.sub}</span>
                              </div>
                              <div style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ac-ink-500)'}}>{p.num}</div>
                              <CompagnieTag2 k={p.cie} />
                              <span className="muted">{p.branch}</span>
                              <div className="num">{tndFShort(p.prime)} TND</div>
                              <span className="muted" style={{fontSize:11}}>Exp. {p.exp}</span>
                              <span className={"badge " + p.status}>
                                <span className="d" />
                                {p.status === "paid" ? "Payée" : p.status === "unpaid" ? p.retard : p.retard}
                              </span>
                            </div>
                          ))}
                        </div>
                      </>
                    )}

                    {activeTab !== "membres" && activeTab !== "polices" && (
                      <div style={{
                        padding:'40px 0', textAlign:'center', color:'var(--ac-ink-500)',
                        fontFamily:'var(--font-mono)', fontSize:12, border:'1px dashed var(--ac-ink-100)',
                        borderRadius: 'var(--radius)', background:'var(--ac-paper)'
                      }}>
                        — Vue {activeTab} — list / kanban embarqué Odoo —
                      </div>
                    )}
                  </div>
                </div>

                {/* Chatter */}
                <div className="o_chatter">
                  <div className="o_chatter_topbar">
                    <button className="btn btn-sm"><Icon d={I.chat} size={12} /> Envoyer un message</button>
                    <button className="btn btn-sm"><Icon d={I.edit} size={12} /> Journaliser une note</button>
                    <button className="btn btn-sm"><Icon d={I.bell} size={12} /> Planifier une activité</button>
                    <button className="btn btn-sm"><Icon d={I.attach} size={12} /> Joindre</button>
                    <div className="o_followers">
                      <span>4 abonnés</span>
                      <div className="avs">
                        <div className="av">SH</div>
                        <div className="av" style={{background:'var(--ac-blue-700)'}}>MA</div>
                        <div className="av" style={{background:'var(--ac-success)'}}>RB</div>
                        <div className="av" style={{background:'var(--ac-warning)'}}>+1</div>
                      </div>
                    </div>
                  </div>

                  <div className="o_thread">
                    <div className="o_msg">
                      <div className="av">SH</div>
                      <div className="body">
                        <div className="head">
                          <span className="name">Salim Hammami</span>
                          <span>· Note interne</span>
                          <span>· il y a 2h</span>
                        </div>
                        <div className="content">
                          Relance WhatsApp envoyée à Mohamed pour la quittance <span className="ref">AUTO-2024-0142</span> (Peugeot 208 de Yassine). Réponse attendue avant vendredi sinon escalade en contentieux.
                        </div>
                      </div>
                    </div>
                    <div className="o_msg log">
                      <div className="av">⚙</div>
                      <div className="body">
                        <div className="head">
                          <span className="name">Système</span>
                          <span>· Activité planifiée</span>
                          <span>· hier 09:14</span>
                        </div>
                        <div className="content">
                          <strong>Appel de relance</strong> planifié pour <strong>17/05/26 — 10:00</strong> · assigné à Rim Ben Hadj.
                        </div>
                      </div>
                    </div>
                    <div className="o_msg">
                      <div className="av" style={{background:'var(--ac-blue-700)', color:'#fff'}}>MA</div>
                      <div className="body">
                        <div className="head">
                          <span className="name">Mehdi Aloui</span>
                          <span>· Message</span>
                          <span>· 12 mai</span>
                        </div>
                        <div className="content">
                          Renouvellement MRH Marsa <span className="ref">MRH-2022-1547</span> validé par <CompagnieTag2 k="star" />. Avenant à signer côté client — pièce jointe générée.
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.Form = Form;

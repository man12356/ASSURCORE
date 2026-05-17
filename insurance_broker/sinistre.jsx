/* global React, NavBar, Sidebar, ControlPanel, Icon, I */
/*
  Vue Sinistre — Form Odoo avec chronologie (timeline) latérale.
  Modèle: insurance.claim · état_sinistre statusbar
*/

function tndS(n) { return n.toLocaleString("fr-FR", { minimumFractionDigits: 3, maximumFractionDigits: 3 }); }

const TIMELINE = [
  { state: "done",   icon: "✓", when: "02/04/26 · 14h22", title: "Déclaration reçue",
    body: "Déclaré par téléphone — agent saisi : Rim Ben Hadj.",
    who: "M. Mohamed Ben Salem · WhatsApp +216 22 184 720",
    attached: ["constat-amiable.pdf"] },
  { state: "done",   icon: "→", when: "03/04/26 · 09h05", title: "Transmis à la compagnie",
    body: "Dossier transmis à COMAR — référence interne assignée : SIN-COMAR-26-0814.",
    who: "Salim Hammami · Email automatique" },
  { state: "done",   icon: "👁", when: "08/04/26 · 11h30", title: "Expertise sur place",
    body: "Expert mandaté par COMAR. Véhicule examiné au garage SAGEM Mégrine.",
    who: "Tarek Mansouri — Expert agréé n° 247",
    attached: ["rapport-expert.pdf", "photos-vehicule.zip"] },
  { state: "active", icon: "€", when: "12/05/26 · 10h12", title: "Proposition d'indemnisation",
    body: <>Indemnité proposée : <span className="amt">8 240,500 TND</span> · franchise 350,000 TND · délai règlement 15 jours.<br />
      <span style={{color: 'var(--ac-warning)', fontWeight: 600}}>⚠ En attente d'accord client.</span></>,
    who: "COMAR · service indemnisation",
    attached: ["offre-indemnisation.pdf"] },
  { state: "",       icon: "✎", when: "—", title: "Accord client", body: "Étape suivante — relancer le client avant 18/05/26." },
  { state: "",       icon: "$", when: "—", title: "Règlement & clôture", body: "Versement attendu sur RIB BIAT 08 002 040 21458736 31." },
];

function Sinistre({ persona = "courtier", variant = "shadow" }) {
  return (
    <div className={"o_action_manager cards-" + variant}>
      <NavBar activeSection="Sinistres" />
      <div className="o_app_body">
        <Sidebar active="claims" />
        <div className="o_content_wrap">

          <ControlPanel
            breadcrumb={["Sinistres", "Ouverts", "SIN-2026-0421"]}
            searchPlaceholder="Rechercher un sinistre…"
            primaryAction="Nouveau sinistre"
            filters={[
              { label: "Mes sinistres", active: true, icon: I.users, count: 34 },
              { label: "En cours", count: 17 },
              { label: "En attente client", icon: I.warn, count: 4 },
              { label: "Filtres", icon: I.filter },
            ]}
            views={[{ label: "Form", active: true }, { label: "Kanban" }, { label: "Liste" }]}
            pager="14 / 34"
          />

          <div className="o_content" style={{padding:'20px 20px 0'}}>
            <div className="o_form_view">
              <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', maxWidth:1100, margin:'0 auto', width:'100%'}}>
                <div style={{display:'flex', gap:6}}>
                  <button className="btn btn-primary"><Icon d={I.edit} size={12} /> Modifier</button>
                  <button className="btn btn-secondary">Créer</button>
                  <button className="btn btn-ghost">Action ▾</button>
                </div>
                <div style={{display:'flex', alignItems:'center', gap:8, fontSize:11, color:'var(--ac-ink-500)', fontFamily:'var(--font-mono)'}}>
                  <span>insurance.claim · #SIN-2026-0421</span>
                </div>
              </div>

              <div className="o_form_sheet">
                <div className="oe_ribbon warning">En attente client</div>

                {/* Statusbar — cycle de vie du sinistre */}
                <div className="o_form_statusbar">
                  <div className="o_statusbar_status">
                    <span className="o_arrow_button done">Déclaré</span>
                    <span className="o_arrow_button done">Transmis</span>
                    <span className="o_arrow_button done">Expertise</span>
                    <span className="o_arrow_button btn_active">Indemnisation</span>
                    <span className="o_arrow_button">Réglé</span>
                    <span className="o_arrow_button">Clos</span>
                  </div>
                  <div className="o_statusbar_buttons">
                    <button className="btn btn-secondary btn-sm">Relancer client</button>
                    <button className="btn btn-secondary btn-sm">Joindre pièce</button>
                  </div>
                </div>

                {/* Smart buttons */}
                <div className="oe_button_box" style={{gridTemplateColumns:'repeat(5, 1fr)'}}>
                  <button className="oe_stat_button">
                    <span className="icon"><Icon d={I.doc} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">12</span>
                      <span className="o_stat_text">Pièces jointes</span>
                    </span>
                  </button>
                  <button className="oe_stat_button success">
                    <span className="icon"><Icon d={I.euro} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">8 240</span>
                      <span className="o_stat_text">Indemnité (TND)</span>
                    </span>
                  </button>
                  <button className="oe_stat_button warning">
                    <span className="icon"><Icon d={I.warn} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">43j</span>
                      <span className="o_stat_text">Délai traitement</span>
                    </span>
                  </button>
                  <button className="oe_stat_button">
                    <span className="icon"><Icon d={I.shield} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">1</span>
                      <span className="o_stat_text">Police liée</span>
                    </span>
                  </button>
                  <button className="oe_stat_button">
                    <span className="icon"><Icon d={I.chat} size={16} /></span>
                    <span className="stat">
                      <span className="o_stat_value">18</span>
                      <span className="o_stat_text">Échanges</span>
                    </span>
                  </button>
                </div>

                <div className="oe_title">
                  <div className="avatar" style={{background:'linear-gradient(135deg,#F87171,#B91C1C)'}}>
                    <Icon d={I.car} size={26} stroke={2} />
                  </div>
                  <div className="title_main">
                    <h1 className="h1">
                      Collision Av. Habib Bourguiba
                      <span className="sub">· SIN-2026-0421 · Peugeot 208 · 183 TU 4521</span>
                    </h1>
                    <div className="tags">
                      <span className="badge info"><span className="d" />Auto · Collision</span>
                      <span className="cie comar"><span className="swatch" />COMAR</span>
                      <span className="badge neutral"><span className="d" />Tiers responsable</span>
                      <span className="badge pending"><span className="d" />Indemnisation phase 2</span>
                    </div>
                  </div>
                  <div className="balance">
                    <div className="lbl">Indemnité proposée</div>
                    <div className="v">8 240,500</div>
                    <div style={{fontSize:11, opacity:.8, marginTop:2}}>TND · franchise 350,000</div>
                  </div>
                </div>

                <div className="sinistre_grid">
                  {/* Left col — fields */}
                  <div>
                    <div style={{
                      background:'var(--ac-paper)', borderRadius:'var(--radius-lg)',
                      padding:16, marginBottom:14
                    }}>
                      <div style={{display:'grid', gridTemplateColumns:'120px 1fr 120px 1fr', gap:'8px 14px', alignItems:'baseline'}}>
                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Client</label>
                        <div style={{fontSize:13, fontWeight:600}}><a href="#" style={{color:'var(--ac-blue-700)', textDecoration:'none'}}>Famille Ben Salem</a></div>
                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Police</label>
                        <div style={{fontFamily:'var(--font-mono)', fontSize:12}}>AUTO-2024-0142</div>

                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Conducteur</label>
                        <div style={{fontSize:13, fontWeight:500}}>Yassine Ben Salem (18 ans)</div>
                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Permis</label>
                        <div style={{fontSize:13, fontWeight:500}}>B · depuis 2025 <span style={{color:'var(--ac-warning)', fontSize:11}}>(novice)</span></div>

                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Véhicule</label>
                        <div style={{fontSize:13, fontWeight:500}}>Peugeot 208 GT — 183 TU 4521</div>
                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Compagnie</label>
                        <div><span className="cie comar"><span className="swatch" />COMAR</span></div>

                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Date sinistre</label>
                        <div style={{fontFamily:'var(--font-mono)', fontSize:12}}>02/04/26 · 18h40</div>
                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Lieu</label>
                        <div style={{fontSize:13}}>Av. Habib Bourguiba, Tunis</div>

                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Tiers</label>
                        <div style={{fontSize:13, fontWeight:500}}>BMW 318 — 092 TU 5419 <br /><span style={{fontSize:11, color:'var(--ac-ink-500)'}}>Responsable selon constat (50/50 contesté)</span></div>
                        <label style={{fontSize:11, color:'var(--ac-ink-500)'}}>Référence Cie</label>
                        <div style={{fontFamily:'var(--font-mono)', fontSize:12, color:'var(--ac-blue-700)'}}>SIN-COMAR-26-0814</div>
                      </div>
                    </div>

                    <div style={{
                      display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:10, marginBottom:14
                    }}>
                      <div style={{background:'var(--ac-white)', border:'1px solid var(--ac-ink-100)', borderRadius:'var(--radius)', padding:12}}>
                        <div style={{fontSize:10, color:'var(--ac-ink-500)', textTransform:'uppercase', letterSpacing:'.05em', fontWeight:600}}>Montant réclamé</div>
                        <div style={{fontSize:18, fontWeight:700, fontVariantNumeric:'tabular-nums', marginTop:2}}>{tndS(9500.000)}</div>
                        <div style={{fontSize:11, color:'var(--ac-ink-500)', marginTop:2}}>Devis garage · 14/04/26</div>
                      </div>
                      <div style={{background:'var(--ac-white)', border:'1px solid var(--ac-ink-100)', borderRadius:'var(--radius)', padding:12}}>
                        <div style={{fontSize:10, color:'var(--ac-ink-500)', textTransform:'uppercase', letterSpacing:'.05em', fontWeight:600}}>Expertise</div>
                        <div style={{fontSize:18, fontWeight:700, fontVariantNumeric:'tabular-nums', marginTop:2}}>{tndS(8590.500)}</div>
                        <div style={{fontSize:11, color:'var(--ac-ink-500)', marginTop:2}}>Expert COMAR · 08/04/26</div>
                      </div>
                      <div style={{background:'var(--ac-success-bg)', border:'1px solid #C4E6CF', borderRadius:'var(--radius)', padding:12}}>
                        <div style={{fontSize:10, color:'var(--ac-success)', textTransform:'uppercase', letterSpacing:'.05em', fontWeight:600}}>Indemnité finale</div>
                        <div style={{fontSize:18, fontWeight:700, fontVariantNumeric:'tabular-nums', marginTop:2, color:'var(--ac-success)'}}>{tndS(8240.500)}</div>
                        <div style={{fontSize:11, color:'var(--ac-success)', marginTop:2}}>Après franchise 350,000</div>
                      </div>
                    </div>

                    <div style={{
                      background:'var(--ac-white)', border:'1px solid var(--ac-ink-100)',
                      borderRadius:'var(--radius)', padding:14
                    }}>
                      <div style={{fontSize:11, color:'var(--ac-ink-500)', textTransform:'uppercase', letterSpacing:'.05em', fontWeight:600, marginBottom:8}}>Narratif & circonstances</div>
                      <div style={{fontSize:13, lineHeight:1.55, color:'var(--ac-ink-700)'}}>
                        Collision arrière en stationnement, av. Habib Bourguiba face au n° 47. Le tiers (BMW 318) recule sans visibilité et heurte l'avant droit du véhicule assuré. Pas de blessé. Constat amiable signé sur place, contesté ultérieurement par le tiers (allégation de stationnement irrégulier).
                      </div>
                      <div style={{display:'flex', gap:6, marginTop:10, flexWrap:'wrap'}}>
                        <span style={{padding:'3px 8px', background:'var(--ac-ink-50)', borderRadius:4, fontSize:11, fontWeight:500}}>#collision-arriere</span>
                        <span style={{padding:'3px 8px', background:'var(--ac-ink-50)', borderRadius:4, fontSize:11, fontWeight:500}}>#materiel-uniquement</span>
                        <span style={{padding:'3px 8px', background:'var(--ac-warning-bg)', color:'var(--ac-warning)', borderRadius:4, fontSize:11, fontWeight:600}}>#constat-conteste</span>
                      </div>
                    </div>
                  </div>

                  {/* Right col — timeline */}
                  <div>
                    <div style={{
                      background:'var(--ac-white)', border:'1px solid var(--ac-ink-100)',
                      borderRadius:'var(--radius-lg)', padding:16
                    }}>
                      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14}}>
                        <h3 style={{margin:0, fontSize:14, fontWeight:600}}>Chronologie</h3>
                        <span style={{fontSize:11, fontFamily:'var(--font-mono)', color:'var(--ac-ink-500)'}}>insurance.claim.event</span>
                      </div>

                      <div className="timeline">
                        {TIMELINE.map((e, i) => (
                          <div key={i} className={"tl_event" + (e.state ? " " + e.state : "")}>
                            <div className="dot">{e.icon}</div>
                            <div className="when">{e.when}</div>
                            <div className="ttl">{e.title}</div>
                            <div className="body">
                              {e.body}
                              {e.who && <div className="who">— {e.who}</div>}
                              {e.attached && e.attached.map((a, j) => (
                                <span key={j} className="attached"><Icon d={I.attach} size={10} />{a}</span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>

                      <div style={{
                        marginTop:14, paddingTop:12, borderTop:'1px dashed var(--ac-ink-100)',
                        display:'flex', gap:6
                      }}>
                        <button className="btn btn-secondary btn-sm" style={{flex:1}}><Icon d={I.plus} size={12} /> Étape</button>
                        <button className="btn btn-secondary btn-sm" style={{flex:1}}><Icon d={I.bell} size={12} /> Rappel</button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Chatter compact */}
                <div className="o_chatter">
                  <div className="o_chatter_topbar">
                    <button className="btn btn-sm"><Icon d={I.chat} size={12} /> Message</button>
                    <button className="btn btn-sm"><Icon d={I.edit} size={12} /> Note</button>
                    <button className="btn btn-sm"><Icon d={I.bell} size={12} /> Activité</button>
                    <div className="o_followers">
                      <span>3 abonnés</span>
                      <div className="avs">
                        <div className="av">SH</div>
                        <div className="av" style={{background:'var(--ac-blue-700)'}}>RB</div>
                        <div className="av" style={{background:'var(--ac-warning)'}}>MA</div>
                      </div>
                    </div>
                  </div>
                  <div className="o_thread">
                    <div className="o_msg">
                      <div className="av">SH</div>
                      <div className="body">
                        <div className="head">
                          <span className="name">Salim Hammami</span>
                          <span>· il y a 1h</span>
                        </div>
                        <div className="content">
                          Client recontacté : besoin de 48h pour valider l'offre. <strong>À relancer 16/05/26</strong>.
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

window.Sinistre = Sinistre;

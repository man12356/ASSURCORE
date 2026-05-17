/* global React, NavBar, Sidebar, ControlPanel, Icon, I, Sparkline */
/*
  Dashboard Trésorerie — Vue Dashboard/Kanban Odoo.
  Données Tunisie : compagnies STAR / GAT / LLOYD / COMAR / ASTREE, montants TND.
*/

// Format TND (3 décimales, séparateurs FR)
function tnd(n, opts = {}) {
  const s = n.toLocaleString("fr-FR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  return opts.short ? s : `${s} TND`;
}
function tndShort(n) {
  if (Math.abs(n) >= 1000) return (n / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 }) + "k";
  return n.toLocaleString("fr-FR");
}

const TOP_IMPAYES = [
  { client: "SARL TEXMODE",       branch: "MRH",   policy: "MRH-2023-0871",  cie: "star",  due: "15/04/26", days: 30, amount: 4820.500 },
  { client: "Ben Salem, Mohamed", branch: "Auto",  policy: "AUTO-2024-0142", cie: "comar", due: "02/04/26", days: 43, amount: 1245.750 },
  { client: "Trabelsi, Karim",    branch: "Santé", policy: "SAN-2024-0312",  cie: "gat",   due: "18/03/26", days: 58, amount: 2160.000 },
  { client: "SOCOMENA",           branch: "Flotte",policy: "FLT-2023-0044",  cie: "lloyd", due: "10/03/26", days: 66, amount: 8975.250 },
  { client: "Mestiri, Houda",     branch: "Vie",   policy: "VIE-2022-0998",  cie: "astree",due: "28/02/26", days: 76, amount: 980.000 },
  { client: "Hôtel Marsa Plaza",  branch: "MRH",   policy: "MRH-2021-0445",  cie: "star",  due: "12/02/26", days: 92, amount: 6420.000 },
];

const RENEWALS = [
  { col: "À 7 jours",  items: [
    { c: "Khalil, Amina",     p: "Auto · Clio IV",        cie: "gat",   v: 1180.500, exp: "22/05/26" },
    { c: "Ben Slimane, R.",   p: "MRH · Villa Soukra",    cie: "star",  v: 2340.000, exp: "20/05/26" },
  ]},
  { col: "À 14 jours", items: [
    { c: "Pharmacie Centrale",p: "Multirisque Pro",       cie: "comar", v: 3450.750, exp: "27/05/26" },
    { c: "Mejri, Sonia",      p: "Santé Famille",         cie: "gat",   v: 1980.000, exp: "26/05/26" },
    { c: "Triki, Walid",      p: "Auto · 208",            cie: "star",  v: 1145.250, exp: "25/05/26" },
  ]},
  { col: "À 21 jours", items: [
    { c: "Société NACEUR",    p: "Flotte 12 véh.",        cie: "lloyd", v: 14820.000, exp: "03/06/26" },
    { c: "Bouzaiene, Y.",     p: "Vie épargne",           cie: "astree",v: 600.000,  exp: "01/06/26" },
  ]},
  { col: "À 30 jours", items: [
    { c: "EcoBat SARL",       p: "MRP · Atelier",         cie: "star",  v: 5670.000, exp: "12/06/26" },
    { c: "Hamdi, Leïla",      p: "Auto · Tucson",         cie: "comar", v: 1875.500, exp: "10/06/26" },
    { c: "Café Sidi Bou",     p: "MRH commerce",          cie: "gat",   v: 920.000,  exp: "08/06/26" },
  ]},
];

const PROD_BY_CIE = [
  { name: "STAR",   v: 184_650, share: 0.32 },
  { name: "COMAR",  v: 142_300, share: 0.25 },
  { name: "GAT",    v: 118_540, share: 0.21 },
  { name: "LLOYD",  v:  74_220, share: 0.13 },
  { name: "ASTREE", v:  52_890, share: 0.09 },
];

function CompagnieTag({ k }) {
  const label = { star: "STAR", gat: "GAT", lloyd: "LLOYD", comar: "COMAR", astree: "ASTREE" }[k];
  return (
    <span className={"cie " + k}>
      <span className="swatch" />{label}
    </span>
  );
}

function Dashboard({ persona = "courtier", variant = "shadow" }) {
  // Persona switch tweaks several KPIs and filters.
  const isAgent = persona === "agent";
  const kpis = isAgent
    ? [
        { tone: "primary", lbl: "Solde Caisse",        val: 38420.500, suf: "TND", delta: { dir: "up",   v: "+4,2 %" }, foot: "Compte STAR · réconcilié 14h22", spark: [12,14,13,16,18,17,19,21,20,23,22,24] },
        { tone: "danger",  lbl: "Impayés (Agence)",    val: 89640.250, suf: "TND", delta: { dir: "up",   v: "+9,1 %" }, foot: "23 quittances · STAR uniquement",  spark: [8,9,8,10,11,12,11,13,14,15,16,18] },
        { tone: "warning", lbl: "Renouvellements 30j", val: 142, suf: "polices",   delta: { dir: "down", v: "−2,4 %" }, foot: "94 % STAR · 6 % co-courtage",      spark: [20,18,19,21,19,22,20,21,19,20,18,17] },
        { tone: "success", lbl: "Production MTD",      val: 184650.000,suf: "TND", delta: { dir: "up",   v: "+12,6 %" },foot: "Objectif mensuel : 78 %",         spark: [4,6,8,7,10,12,14,16,18,17,20,22] },
      ]
    : [
        { tone: "primary", lbl: "Solde Caisse Consolidé", val: 412840.750, suf: "TND", delta: { dir: "up",   v: "+6,8 %" }, foot: "5 comptes compagnies · réconcilié 14h22", spark: [12,14,13,16,18,17,19,21,20,23,22,24] },
        { tone: "danger",  lbl: "Top Impayés > 30j",       val: 89640.250, suf: "TND", delta: { dir: "up",   v: "+9,1 %" }, foot: "47 quittances · 6 compagnies",            spark: [8,9,8,10,11,12,11,13,14,15,16,18] },
        { tone: "warning", lbl: "Renouvellements 30j",     val: 342, suf: "polices",   delta: { dir: "down", v: "−2,4 %" }, foot: "Toutes compagnies · 89 % traité",         spark: [20,18,19,21,19,22,20,21,19,20,18,17] },
        { tone: "success", lbl: "Production MTD",          val: 572600.000,suf: "TND", delta: { dir: "up",   v: "+14,3 %" },foot: "Objectif mensuel : 81 %",                spark: [4,6,8,7,10,12,14,16,18,17,20,22] },
      ];

  return (
    <div className={"o_action_manager cards-" + variant}>
      <NavBar activeSection="Tableau de bord" />
      <div className="o_app_body">
        <Sidebar active="dashboard" />
        <div className="o_content_wrap">

          <ControlPanel
            breadcrumb={["Tableau de bord", "Trésorerie"]}
            title={isAgent ? "Trésorerie Agence — STAR" : "Trésorerie Cabinet — Multi-compagnies"}
            searchPills={[
              { label: "Période", value: "Mai 2026" },
              ...(isAgent ? [{ label: "Compagnie", value: "STAR" }] : []),
            ]}
            primaryAction="Nouvelle quittance"
            filters={[
              { label: "Mes éléments", active: true, icon: I.users, count: isAgent ? 142 : 412 },
              { label: "À encaisser", count: isAgent ? 23 : 47, icon: I.warn },
              { label: "À échoir 30j", count: isAgent ? 142 : 342 },
              { label: "Cette semaine" },
              { label: "Filtres", icon: I.filter },
              { label: "Groupé par : Compagnie", icon: I.briefcase },
            ]}
            views={[
              { label: "Dashboard", active: true },
              { label: "Kanban" },
              { label: "Liste" },
              { label: "Pivot" },
              { label: "Graph" },
            ]}
            pager="1–6 / 412"
          />

          <div className="o_content">
            {/* KPI tiles */}
            <div className="kpi-grid">
              {kpis.map((k, i) => (
                <div key={i} className={"kpi " + k.tone}>
                  <Sparkline data={k.spark}
                    color={k.tone === "danger" ? "var(--ac-danger)" :
                           k.tone === "success" ? "var(--ac-success)" :
                           k.tone === "warning" ? "var(--ac-warning)" : "var(--ac-blue-600)"} />
                  <div className="label">
                    <span className="dot" />
                    <span>{k.lbl}</span>
                  </div>
                  <div className="value">
                    {typeof k.val === "number" && k.val > 1000
                      ? k.val.toLocaleString("fr-FR", { minimumFractionDigits: k.suf === "TND" ? 3 : 0, maximumFractionDigits: k.suf === "TND" ? 3 : 0 })
                      : k.val}
                    <span className="unit">{k.suf}</span>
                  </div>
                  <span className={"delta " + k.delta.dir}>
                    <Icon d={k.delta.dir === "up" ? I.arrowU : I.arrowD} size={10} stroke={2.4} />
                    {k.delta.v}
                  </span>
                  <div className="foot">
                    <span>{k.foot}</span>
                    <a href="#">Détail →</a>
                  </div>
                </div>
              ))}
            </div>

            {/* Pipeline strip — quittance lifecycle */}
            <div className="o_section_title">
              <h2>Pipeline — Cycle de la quittance</h2>
              <span style={{fontSize:11, color:'var(--ac-ink-500)', fontFamily:'var(--font-mono)'}}>account.move.line · état_quittance</span>
            </div>
            <div className="pipeline">
              {[
                { l: "Émise",         v: isAgent ?  87 : 218 },
                { l: "Notifiée",      v: isAgent ?  62 : 174 },
                { l: "Partielle",     v: isAgent ?  14 :  41, active: true },
                { l: "Encaissée",     v: isAgent ? 312 : 894 },
                { l: "Reversée Cie",  v: isAgent ? 298 : 856 },
                { l: "Contentieux",   v: isAgent ?   8 :  19 },
              ].map((s, i) => (
                <div key={i} className={"stage" + (s.active ? " active" : "")}>
                  {s.l}<strong>{s.v}</strong>
                </div>
              ))}
            </div>

            {/* Top Impayés + Production par compagnie */}
            <div className="o_section_title">
              <h2>Top Impayés &amp; Production</h2>
            </div>
            <div className="summary_band">
              <div className="o_widget">
                <div className="o_widget_head">
                  <div>
                    <h3>Top Impayés</h3>
                    <span className="sub">> 30 jours · {isAgent ? "STAR" : "toutes compagnies"}</span>
                  </div>
                  <div className="tools">
                    <button className="btn btn-ghost btn-sm">Relancer en masse</button>
                    <button className="btn btn-secondary btn-sm">Export</button>
                  </div>
                </div>
                <div className="o_widget_body dense">
                  <table className="o_list_view">
                    <thead>
                      <tr>
                        <th>Client</th>
                        <th>Branche</th>
                        <th>N° Police</th>
                        {!isAgent && <th>Compagnie</th>}
                        <th>Échéance</th>
                        <th style={{textAlign:'right'}}>Retard</th>
                        <th style={{textAlign:'right'}}>Montant</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {(isAgent ? TOP_IMPAYES.filter(r => r.cie === "star") : TOP_IMPAYES).map((r, i) => (
                        <tr key={i}>
                          <td><strong>{r.client}</strong></td>
                          <td className="muted">{r.branch}</td>
                          <td style={{fontFamily:'var(--font-mono)', fontSize:11}}>{r.policy}</td>
                          {!isAgent && <td><CompagnieTag k={r.cie} /></td>}
                          <td className="muted">{r.due}</td>
                          <td className="num">
                            <span className="badge unpaid"><span className="d" />{r.days}j</span>
                          </td>
                          <td className="num"><strong>{tnd(r.amount, { short: true })}</strong></td>
                          <td>
                            <button className="btn btn-ghost btn-sm">Relancer</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="o_widget">
                <div className="o_widget_head">
                  <div>
                    <h3>{isAgent ? "Production STAR" : "Production par compagnie"}</h3>
                    <span className="sub">MTD · Mai 2026</span>
                  </div>
                  <div className="tools">
                    <button className="btn btn-ghost btn-sm">YTD</button>
                  </div>
                </div>
                <div className="o_widget_body">
                  <div className="bars">
                    {(isAgent ? PROD_BY_CIE.filter(c => c.name === "STAR").map(c => ({...c, v: 184_650}))
                              : PROD_BY_CIE
                    ).map((c, i) => (
                      <div key={i} className="row">
                        <span className="name">{c.name}</span>
                        <div className="track">
                          <div className="fill" style={{ width: (c.v / 200000 * 100) + "%" }} />
                        </div>
                        <span className="val">{tndShort(c.v)} TND</span>
                      </div>
                    ))}
                  </div>

                  <div style={{
                    marginTop: 14, paddingTop: 12, borderTop: '1px dashed var(--ac-ink-100)',
                    display:'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 12,
                  }}>
                    <div>
                      <div style={{color:'var(--ac-ink-500)', fontSize:11, textTransform:'uppercase', letterSpacing:'.05em', fontWeight:600}}>Commissions MTD</div>
                      <div style={{fontSize:18, fontWeight:700, fontVariantNumeric:'tabular-nums'}}>{tnd(isAgent ? 18465.000 : 57260.000, {short:true})}</div>
                    </div>
                    <div>
                      <div style={{color:'var(--ac-ink-500)', fontSize:11, textTransform:'uppercase', letterSpacing:'.05em', fontWeight:600}}>Taux moyen</div>
                      <div style={{fontSize:18, fontWeight:700, fontVariantNumeric:'tabular-nums'}}>10,0 %</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Renouvellements Kanban */}
            <div className="o_section_title">
              <h2>Renouvellements à 30 jours</h2>
              <div style={{display:'flex', gap:6}}>
                <button className="btn btn-secondary btn-sm">Calendrier</button>
                <button className="btn btn-secondary btn-sm">Affecter</button>
              </div>
            </div>
            <div className="o_widget">
              <div className="o_kanban_view">
                {RENEWALS.map((col, i) => (
                  <div key={i} className="o_kanban_col">
                    <div className="o_kanban_col_head">
                      <span>{col.col}</span>
                      <span className="count">{col.items.length}</span>
                    </div>
                    {col.items
                      .filter(it => !isAgent || it.cie === "star")
                      .map((it, j) => (
                      <div key={j} className="o_kanban_record">
                        <div className="kr_top">
                          <div className="kr_title">{it.c}</div>
                          <CompagnieTag k={it.cie} />
                        </div>
                        <div className="kr_meta">
                          <span>{it.p}</span>
                        </div>
                        <div className="kr_foot">
                          <span style={{fontSize:11, color:'var(--ac-ink-500)'}}>Exp. {it.exp}</span>
                          <span className="kr_amount">{tndShort(it.v)} TND</span>
                        </div>
                      </div>
                    ))}
                    {col.items.filter(it => !isAgent || it.cie === "star").length === 0 && (
                      <div style={{padding:'18px 8px', textAlign:'center', fontSize:11, color:'var(--ac-ink-300)', fontFamily:'var(--font-mono)'}}>
                        — vide —
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}

window.Dashboard = Dashboard;

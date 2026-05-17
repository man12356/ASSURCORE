/* global React, NavBar, Sidebar, ControlPanel, Icon, I */
/*
  Liste des Quittances — vue list/tree Odoo dense avec totalisation.
  Group_by Compagnie · sticky header · row de footer "total"
*/

function tndC(n) { return n.toLocaleString("fr-FR", { minimumFractionDigits: 3, maximumFractionDigits: 3 }); }

const QUITTANCES_ROWS = [
  // STAR
  { cie: "star", num: "QT-26-04812", date: "12/05/26", client: "SARL TEXMODE",         policy: "MRH-2023-0871",  branch: "MRH",   exp: "15/04/26",  ht: 4500.000, taxes: 320.500, ttc: 4820.500, com: 482.050, state: "unpaid",  retard: "30j" },
  { cie: "star", num: "QT-26-04798", date: "10/05/26", client: "Ben Salem, Mohamed",   policy: "MRH-2022-1547",  branch: "MRH",   exp: "12/06/26",  ht:  860.000, taxes:  60.000, ttc:  920.000, com:  92.000, state: "pending", retard: null },
  { cie: "star", num: "QT-26-04701", date: "04/05/26", client: "Hôtel Marsa Plaza",    policy: "MRH-2021-0445",  branch: "MRH",   exp: "12/02/26",  ht: 6000.000, taxes: 420.000, ttc: 6420.000, com: 642.000, state: "unpaid",  retard: "92j" },
  { cie: "star", num: "QT-26-04654", date: "02/05/26", client: "Triki, Walid",         policy: "AUTO-2024-0033", branch: "Auto",  exp: "25/05/26",  ht: 1070.000, taxes:  75.250, ttc: 1145.250, com: 114.525, state: "paid",    retard: null, sel: true },
  { cie: "star", num: "QT-26-04612", date: "29/04/26", client: "EcoBat SARL",          policy: "MRP-2023-0089",  branch: "MRP",   exp: "12/06/26",  ht: 5300.000, taxes: 370.000, ttc: 5670.000, com: 567.000, state: "paid",    retard: null },
  // COMAR
  { cie: "comar", num: "QT-26-04588", date: "28/04/26", client: "Ben Salem, Mohamed",  policy: "AUTO-2024-0142", branch: "Auto",  exp: "02/04/26",  ht: 1165.000, taxes:  80.750, ttc: 1245.750, com: 124.575, state: "unpaid",  retard: "43j" },
  { cie: "comar", num: "QT-26-04571", date: "26/04/26", client: "Pharmacie Centrale",  policy: "MRP-2023-0991",  branch: "MRP",   exp: "27/05/26",  ht: 3220.000, taxes: 230.750, ttc: 3450.750, com: 345.075, state: "paid",    retard: null },
  { cie: "comar", num: "QT-26-04550", date: "22/04/26", client: "Hamdi, Leïla",        policy: "AUTO-2024-0207", branch: "Auto",  exp: "10/06/26",  ht: 1755.000, taxes: 120.500, ttc: 1875.500, com: 187.550, state: "pending", retard: null },
  { cie: "comar", num: "QT-26-04510", date: "20/04/26", client: "Famille Ben Salem",   policy: "SAN-2023-0089",  branch: "Santé", exp: "01/09/26",  ht: 3215.000, taxes: 235.000, ttc: 3450.000, com: 345.000, state: "paid",    retard: null },
  // GAT
  { cie: "gat", num: "QT-26-04492", date: "19/04/26", client: "Trabelsi, Karim",       policy: "SAN-2024-0312",  branch: "Santé", exp: "18/03/26",  ht: 2020.000, taxes: 140.000, ttc: 2160.000, com: 216.000, state: "unpaid",  retard: "58j" },
  { cie: "gat", num: "QT-26-04476", date: "17/04/26", client: "Khalil, Amina",         policy: "AUTO-2024-0287", branch: "Auto",  exp: "22/05/26",  ht: 1100.500, taxes:  80.000, ttc: 1180.500, com: 118.050, state: "paid",    retard: null },
  { cie: "gat", num: "QT-26-04465", date: "16/04/26", client: "Mejri, Sonia",          policy: "SAN-2023-0167",  branch: "Santé", exp: "26/05/26",  ht: 1850.000, taxes: 130.000, ttc: 1980.000, com: 198.000, state: "pending", retard: null },
  { cie: "gat", num: "QT-26-04443", date: "14/04/26", client: "Café Sidi Bou",         policy: "MRH-2024-0099",  branch: "MRH",   exp: "08/06/26",  ht:  860.000, taxes:  60.000, ttc:  920.000, com:  92.000, state: "pending", retard: null },
  // LLOYD
  { cie: "lloyd", num: "QT-26-04401", date: "11/04/26", client: "SOCOMENA",            policy: "FLT-2023-0044",  branch: "Flotte",exp: "10/03/26",  ht: 8400.000, taxes: 575.250, ttc: 8975.250, com: 897.525, state: "unpaid",  retard: "66j" },
  { cie: "lloyd", num: "QT-26-04388", date: "09/04/26", client: "Société NACEUR",      policy: "FLT-2023-0098",  branch: "Flotte",exp: "03/06/26",  ht:13850.000, taxes: 970.000, ttc:14820.000, com:1482.000, state: "pending", retard: null },
  // ASTREE
  { cie: "astree", num: "QT-26-04340", date: "06/04/26", client: "Mestiri, Houda",     policy: "VIE-2022-0998",  branch: "Vie",   exp: "28/02/26",  ht:  920.000, taxes:  60.000, ttc:  980.000, com:  98.000, state: "unpaid",  retard: "76j" },
  { cie: "astree", num: "QT-26-04298", date: "03/04/26", client: "Bouzaiene, Y.",      policy: "VIE-2024-0042",  branch: "Vie",   exp: "01/06/26",  ht:  560.000, taxes:  40.000, ttc:  600.000, com:  60.000, state: "paid",    retard: null },
];

const CIE_LABEL = { star: "STAR", gat: "GAT", lloyd: "LLOYD", comar: "COMAR", astree: "ASTREE" };

function CompagnieTag3({ k }) {
  return (<span className={"cie " + k}><span className="swatch" />{CIE_LABEL[k]}</span>);
}

function StateBadge({ s, retard }) {
  if (s === "paid")    return <span className="badge paid"><span className="d" />Encaissée</span>;
  if (s === "pending") return <span className="badge pending"><span className="d" />À échoir</span>;
  return <span className="badge unpaid"><span className="d" />Impayée · {retard}</span>;
}

function Quittances({ persona = "courtier", variant = "shadow" }) {
  const rows = persona === "agent"
    ? QUITTANCES_ROWS.filter(r => r.cie === "star")
    : QUITTANCES_ROWS;

  // Group by compagnie
  const groups = {};
  rows.forEach(r => { (groups[r.cie] ||= []).push(r); });

  const totals = (rs) => rs.reduce((a, r) => ({
    ht: a.ht + r.ht, taxes: a.taxes + r.taxes, ttc: a.ttc + r.ttc, com: a.com + r.com,
    paidTtc: a.paidTtc + (r.state === "paid" ? r.ttc : 0),
    unpaidTtc: a.unpaidTtc + (r.state === "unpaid" ? r.ttc : 0),
  }), { ht: 0, taxes: 0, ttc: 0, com: 0, paidTtc: 0, unpaidTtc: 0 });

  const grand = totals(rows);
  const selected = rows.filter(r => r.sel).length;

  return (
    <div className={"o_action_manager cards-" + variant}>
      <NavBar activeSection="Quittances" />
      <div className="o_app_body">
        <Sidebar active="receipts" />
        <div className="o_content_wrap">

          <ControlPanel
            breadcrumb={["Quittances", "Toutes"]}
            title={persona === "agent" ? "Quittances — STAR" : "Quittances — Toutes compagnies"}
            searchPills={[
              { label: "État", value: "Toutes" },
              { label: "Période", value: "Mai 2026" },
            ]}
            primaryAction="Émettre quittance"
            filters={[
              { label: "Mes éléments", active: true, icon: I.users, count: rows.length },
              { label: "À encaisser", icon: I.warn, count: rows.filter(r => r.state === "unpaid").length },
              { label: "À échoir", count: rows.filter(r => r.state === "pending").length },
              { label: "Encaissées", count: rows.filter(r => r.state === "paid").length },
              { label: "Filtres", icon: I.filter },
              { label: "Groupé par : Compagnie", icon: I.briefcase },
            ]}
            views={[
              { label: "Liste", active: true },
              { label: "Kanban" },
              { label: "Pivot" },
              { label: "Graph" },
              { label: "Calendrier" },
            ]}
            pager={`1–${rows.length} / ${rows.length}`}
          />

          <div className="o_content">
            <div className="quittances_tree">
              {selected > 0 && (
                <div className="qtt_selection_bar">
                  <span className="chk on" />
                  <span><strong>{selected}</strong> ligne{selected > 1 ? "s" : ""} sélectionnée{selected > 1 ? "s" : ""} · {tndC(rows.filter(r => r.sel).reduce((a, r) => a + r.ttc, 0))} TND TTC</span>
                  <div className="spacer" />
                  <button className="btn btn-secondary btn-sm">Encaisser</button>
                  <button className="btn btn-secondary btn-sm">Relancer</button>
                  <button className="btn btn-secondary btn-sm">Exporter</button>
                  <button className="btn btn-danger-ghost btn-sm">Annuler</button>
                </div>
              )}

              <table className="o_tree">
                <thead>
                  <tr>
                    <th style={{width: 36}}><span className="chk" /></th>
                    <th><span className="sortable">N° Quittance <span className="arr">↓</span></span></th>
                    <th>Date</th>
                    <th>Client</th>
                    <th>Police</th>
                    <th>Branche</th>
                    {persona !== "agent" && <th>Compagnie</th>}
                    <th>Échéance</th>
                    <th className="num">HT</th>
                    <th className="num">Taxes</th>
                    <th className="num">TTC</th>
                    <th className="num">Commission</th>
                    <th>État</th>
                  </tr>
                </thead>

                <tbody>
                  {Object.entries(groups).map(([cie, gs]) => {
                    const gt = totals(gs);
                    const cols = persona !== "agent" ? 13 : 12;
                    return (
                      <React.Fragment key={cie}>
                        <tr className="group">
                          <td><span className="caret">▾</span></td>
                          <td colSpan={persona !== "agent" ? 6 : 5}>
                            <span style={{display:'inline-flex', alignItems:'center', gap:8}}>
                              <CompagnieTag3 k={cie} />
                              <span style={{color:'var(--ac-ink-500)', fontWeight:500, fontSize:11}}>{gs.length} quittances</span>
                            </span>
                          </td>
                          <td className="num muted" style={{fontWeight:500, color:'var(--ac-ink-500)'}}>Sous-total</td>
                          <td className="num">{tndC(gt.ht)}</td>
                          <td className="num">{tndC(gt.taxes)}</td>
                          <td className="num">{tndC(gt.ttc)}</td>
                          <td className="num">{tndC(gt.com)}</td>
                          <td style={{fontSize:11}}>
                            <span style={{color:'var(--ac-success)'}}>● {tndC(gt.paidTtc)}</span>
                            {gt.unpaidTtc > 0 && <><br /><span style={{color:'var(--ac-danger)'}}>● {tndC(gt.unpaidTtc)}</span></>}
                          </td>
                        </tr>
                        {gs.map((r, i) => (
                          <tr key={i} className={"row" + (r.sel ? " selected" : "")}>
                            <td><span className={"chk" + (r.sel ? " on" : "")} /></td>
                            <td style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ac-blue-700)', fontWeight:600}}>{r.num}</td>
                            <td className="muted" style={{fontFamily:'var(--font-mono)', fontSize:11}}>{r.date}</td>
                            <td><strong>{r.client}</strong></td>
                            <td style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ac-ink-500)'}}>{r.policy}</td>
                            <td className="muted">{r.branch}</td>
                            {persona !== "agent" && <td><CompagnieTag3 k={r.cie} /></td>}
                            <td className="muted">{r.exp}</td>
                            <td className="num">{tndC(r.ht)}</td>
                            <td className="num muted">{tndC(r.taxes)}</td>
                            <td className="num"><strong>{tndC(r.ttc)}</strong></td>
                            <td className="num" style={{color:'var(--ac-blue-700)'}}>{tndC(r.com)}</td>
                            <td><StateBadge s={r.state} retard={r.retard} /></td>
                          </tr>
                        ))}
                      </React.Fragment>
                    );
                  })}
                </tbody>

                <tfoot>
                  <tr>
                    <td colSpan={persona !== "agent" ? 7 : 6}>
                      <span className="lbl-x">TOTAL</span>
                      {rows.length} quittances · {Object.keys(groups).length} compagnie{Object.keys(groups).length > 1 ? "s" : ""}
                    </td>
                    <td className="num">
                      <span className="lbl-x">TTC dû</span>
                      <span style={{color:'var(--ac-danger)'}}>{tndC(grand.unpaidTtc)}</span>
                    </td>
                    <td className="num">{tndC(grand.ht)}</td>
                    <td className="num">{tndC(grand.taxes)}</td>
                    <td className="num" style={{fontSize:14}}>{tndC(grand.ttc)} <span style={{fontWeight:500, color:'var(--ac-ink-500)', fontSize:11}}>TND</span></td>
                    <td className="num" style={{color:'var(--ac-blue-700)'}}>{tndC(grand.com)}</td>
                    <td>
                      <span style={{display:'flex', flexDirection:'column', gap:2, fontSize:11}}>
                        <span style={{color:'var(--ac-success)'}}>● Encaissé {tndC(grand.paidTtc)}</span>
                        <span style={{color:'var(--ac-danger)'}}>● Impayé {tndC(grand.unpaidTtc)}</span>
                      </span>
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.Quittances = Quittances;

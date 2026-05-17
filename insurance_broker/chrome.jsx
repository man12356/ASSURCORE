/* global React */
/*
  AssurCourtage — App chrome (NavBar + Sidebar + ControlPanel).
  Class names follow Odoo 16/17 backend conventions.
*/

const { useState } = React;

// ── Icons (inline SVG, no external dep) ─────────────────────────────────────
function Icon({ d, size = 16, stroke = 1.6 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
      {Array.isArray(d) ? d.map((p, i) => <path key={i} d={p} />) : <path d={d} />}
    </svg>
  );
}
const I = {
  dashboard: "M3 12h7V3H3v9zm0 9h7v-7H3v7zm11 0h7V11h-7v10zm0-18v7h7V3h-7z",
  users:     ["M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8", "M22 21v-2a4 4 0 0 0-3-3.87", "M16 3.13a4 4 0 0 1 0 7.75"],
  family:    ["M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z", "M17 13a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z", "M3 21v-1a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v1", "M15 21v-1a4 4 0 0 1 4-4h0a3 3 0 0 1 3 3v2"],
  receipt:   ["M14 2H6a2 2 0 0 0-2 2v16l3-2 3 2 3-2 3 2V8z", "M14 2v6h6", "M8 13h6", "M8 17h4"],
  briefcase: ["M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2", "M2 13a20 20 0 0 0 20 0", "M4 7h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z"],
  chart:     ["M3 3v18h18", "M7 14l4-4 4 4 5-5"],
  shield:    "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  warn:      ["M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z", "M12 9v4", "M12 17h.01"],
  car:       ["M14 16H9m10 0h3v-3.15a1 1 0 0 0-.84-.99L16 11l-2.7-3.6a1 1 0 0 0-.8-.4H5.24a2 2 0 0 0-1.8 1.1l-.8 1.63A6 6 0 0 0 2 12.42V16h2", "M16.5 18a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z", "M6.5 18a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z"],
  home:      ["M3 9l9-7 9 7v11a2 2 0 0 1-2 2h-4v-7h-6v7H5a2 2 0 0 1-2-2z"],
  heart:     "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 1 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z",
  plane:     "M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.2.6-.6.5-1.1z",
  search:    ["M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z", "M21 21l-4.35-4.35"],
  filter:    "M22 3H2l8 9.46V19l4 2v-8.54L22 3z",
  bell:      ["M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9", "M13.73 21a2 2 0 0 1-3.46 0"],
  plus:      ["M12 5v14", "M5 12h14"],
  more:      ["M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z", "M19 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z", "M5 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z"],
  chevL:     "M15 18l-6-6 6-6",
  chevR:     "M9 18l6-6-6-6",
  chevD:     "M6 9l6 6 6-6",
  cog:       ["M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z", "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.36.18.66.46.85.79"],
  doc:       ["M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z", "M14 2v6h6", "M8 13h8", "M8 17h6"],
  chat:      "M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z",
  attach:    "M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48",
  edit:      ["M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7", "M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"],
  arrowU:    ["M12 19V5", "M5 12l7-7 7 7"],
  arrowD:    ["M12 5v14", "M5 12l7 7 7-7"],
  euro:      ["M4 10h12", "M4 14h9", "M19 6.41A8 8 0 0 0 13 4a8 8 0 0 0 0 16 8 8 0 0 0 6-2.41"],
  caisse:    ["M3 6h18l-2 13H5L3 6z", "M3 6l1-3h16l1 3", "M9 10v3", "M12 10v3", "M15 10v3"],
  building:  ["M3 21h18", "M5 21V7l8-4v18", "M19 21V11l-6-4", "M9 9v.01", "M9 12v.01", "M9 15v.01", "M9 18v.01"],
};

// ── Top navbar ──────────────────────────────────────────────────────────────
function NavBar({ activeSection = "Comptabilité" }) {
  return (
    <div className="o_main_navbar">
      <div className="o_menu_brand">
        <div className="mono">A</div>
        <div>AssurCourtage</div>
      </div>
      <div className="o_menu_sections">
        {["Tableau de bord","Clients","Polices","Quittances","Sinistres","Comptabilité","Reporting"].map(s => (
          <a key={s} className={s === activeSection ? "active" : ""} href="#">{s}</a>
        ))}
      </div>
      <div className="o_menu_systray">
        <a className="o_user_chip" href="#" style={{textDecoration:'none', color:'inherit'}}>
          <Icon d={I.bell} size={14} />
          <span style={{background:'var(--ac-danger)', color:'#fff', borderRadius:999, padding:'1px 6px', fontSize:10, fontWeight:700}}>7</span>
        </a>
        <div className="o_user_chip">
          <div className="av">SH</div>
          <span>Salim H.</span>
          <Icon d={I.chevD} size={12} />
        </div>
      </div>
    </div>
  );
}

// ── Apps sidebar ────────────────────────────────────────────────────────────
function Sidebar({ active = "dashboard" }) {
  const items = [
    { key: "dashboard", icon: I.dashboard, label: "DASH" },
    { key: "clients",   icon: I.family,    label: "CLI"  },
    { key: "policies",  icon: I.shield,    label: "POL"  },
    { key: "receipts",  icon: I.receipt,   label: "QTC"  },
    { key: "claims",    icon: I.warn,      label: "SIN"  },
  ];
  const tools = [
    { key: "reports", icon: I.chart, label: "RPT" },
    { key: "cfg",     icon: I.cog,   label: "CFG" },
  ];
  return (
    <div className="o_apps_sidebar">
      {items.map(it => (
        <div key={it.key} className={"o_app" + (it.key === active ? " active" : "")} title={it.label}>
          <Icon d={it.icon} size={18} />
        </div>
      ))}
      <div className="divider" />
      {tools.map(it => (
        <div key={it.key} className="o_app" title={it.label}>
          <Icon d={it.icon} size={18} />
        </div>
      ))}
    </div>
  );
}

// ── Control Panel ───────────────────────────────────────────────────────────
function ControlPanel({
  breadcrumb = [],
  title,
  searchPills = [],
  searchPlaceholder = "Rechercher…",
  primaryAction,
  filters = [],
  views = [],
  pager,
}) {
  return (
    <div className="o_control_panel">
      <div className="o_cp_top">
        <div>
          <div className="o_breadcrumb">
            {breadcrumb.slice(0, -1).map((b, i) => (
              <React.Fragment key={i}>
                <span>{b}</span><span className="sep">›</span>
              </React.Fragment>
            ))}
            <span className="current">{breadcrumb[breadcrumb.length - 1]}</span>
          </div>
          {title && <h1 className="o_cp_title">{title}</h1>}
        </div>

        <div className="o_cp_actions">
          <div className="o_searchview">
            <Icon d={I.search} size={14} />
            {searchPills.map((p, i) => (
              <span key={i} className="pill">{p.label}: {p.value} <span className="x">×</span></span>
            ))}
            <span style={{flex:1}}>{searchPills.length ? "" : searchPlaceholder}</span>
            <span style={{fontSize:11, color:'var(--ac-ink-300)', fontFamily:'var(--font-mono)'}}>⌘K</span>
          </div>
          {primaryAction && (
            <button className="btn btn-primary">
              <Icon d={I.plus} size={12} stroke={2.2} />
              {primaryAction}
            </button>
          )}
          <button className="btn btn-secondary"><Icon d={I.more} size={14} /></button>
        </div>
      </div>

      <div className="o_cp_bottom">
        <div className="o_cp_filters">
          {filters.map((f, i) => (
            <div key={i} className={"o_cp_filter" + (f.active ? " active" : "")}>
              {f.icon && <Icon d={f.icon} size={13} />}
              <span>{f.label}</span>
              {f.count != null && (
                <span style={{background:'var(--ac-blue-100)', color:'var(--ac-blue-700)', borderRadius:4, padding:'0 6px', fontSize:11, fontWeight:600}}>
                  {f.count}
                </span>
              )}
            </div>
          ))}
        </div>

        <div style={{display:'flex', gap:12, alignItems:'center'}}>
          {pager && (
            <div className="o_pager">
              <span>{pager}</span>
              <div className="nav"><Icon d={I.chevL} size={12} /></div>
              <div className="nav"><Icon d={I.chevR} size={12} /></div>
            </div>
          )}
          {views.length > 0 && (
            <div className="o_cp_views">
              {views.map((v, i) => (
                <div key={i} className={"o_cp_view" + (v.active ? " active" : "")}>{v.label}</div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Tiny inline sparkline
function Sparkline({ data, color = "var(--ac-blue-600)", w = 56, h = 28 }) {
  const max = Math.max(...data), min = Math.min(...data);
  const dx = w / (data.length - 1);
  const pts = data.map((v, i) => [i * dx, h - ((v - min) / (max - min || 1)) * h]);
  const line = pts.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(" ");
  const area = line + ` L${w},${h} L0,${h} Z`;
  return (
    <svg className="spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <path className="area" d={area} fill={color} />
      <path d={line} stroke={color} />
    </svg>
  );
}

window.NavBar = NavBar;
window.Sidebar = Sidebar;
window.ControlPanel = ControlPanel;
window.Icon = Icon;
window.I = I;
window.Sparkline = Sparkline;

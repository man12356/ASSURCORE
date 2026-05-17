/* global React, ReactDOM, DesignCanvas, DCSection, DCArtboard,
          TweaksPanel, useTweaks, TweakRadio, TweakToggle, TweakSection,
          Dashboard, Form, Quittances, Sinistre, MobileChatter, MobileActivity */

const { useEffect } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "persona": "courtier",
  "theme": "light",
  "density": "compact"
}/*EDITMODE-END*/;

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const { persona, theme, density } = tweaks;

  // wrapper class applied to every artboard's screen content
  const themeClass = (theme === "dark" ? "theme-dark " : "")
                   + (density === "comfortable" ? "density-comfortable " : "");

  const VARIANTS = [
    { id: "shadow",   label: "A · Soft Shadow",  note: "$o-kanban-record-shadow + .o_form_sheet box-shadow" },
    { id: "flat",     label: "B · Flat Border",  note: "$o-main-border-color outlines · zero box-shadow" },
    { id: "bordered", label: "C · Accent Border",note: "left-stripe per status · sober card body" },
  ];

  // Helper to wrap any screen in the theme+density class so all variants pick it up
  const wrap = (children) => <div className={themeClass} style={{width:'100%', height:'100%'}}>{children}</div>;

  return (
    <>
      <DesignCanvas>

        <DCSection
          id="dashboard"
          title="Dashboard Trésorerie"
          subtitle={`Vue Dashboard/Kanban · ${persona === "agent" ? "Persona AGENT GÉNÉRAL (mono-compagnie STAR)" : "Persona COURTIER (multi-compagnies)"} · ${theme === "dark" ? "Dark · " : ""}${density === "comfortable" ? "Confortable · " : "Compact · "}3 styles de cards`}>
          {VARIANTS.map(v => (
            <DCArtboard key={v.id} id={"dash-" + v.id} label={v.label} width={1280} height={density === "comfortable" ? 1900 : 1700}>
              {wrap(<Dashboard persona={persona} variant={v.id} />)}
            </DCArtboard>
          ))}
        </DCSection>

        <DCSection
          id="form"
          title="Fiche Client — Famille / Payeur"
          subtitle="Vue Form Odoo · Statusbar + Smart Buttons + Notebook + Chatter · 3 styles de cards">
          {VARIANTS.map(v => (
            <DCArtboard key={v.id} id={"form-" + v.id} label={v.label} width={1280} height={density === "comfortable" ? 2400 : 2200}>
              {wrap(<Form persona={persona} variant={v.id} />)}
            </DCArtboard>
          ))}
        </DCSection>

        <DCSection
          id="quittances"
          title="Liste des Quittances"
          subtitle="Vue tree dense · group_by Compagnie · sous-totaux + ligne de totalisation · sélection multiple">
          {VARIANTS.map(v => (
            <DCArtboard key={v.id} id={"qtt-" + v.id} label={v.label} width={1480} height={density === "comfortable" ? 1500 : 1320}>
              {wrap(<Quittances persona={persona} variant={v.id} />)}
            </DCArtboard>
          ))}
        </DCSection>

        <DCSection
          id="sinistre"
          title="Vue Sinistre — Form + Chronologie"
          subtitle="Form Odoo avec timeline latérale · états déclaration → expertise → indemnisation → règlement">
          {VARIANTS.map(v => (
            <DCArtboard key={v.id} id={"sin-" + v.id} label={v.label} width={1280} height={density === "comfortable" ? 1700 : 1550}>
              {wrap(<Sinistre persona={persona} variant={v.id} />)}
            </DCArtboard>
          ))}
        </DCSection>

        <DCSection
          id="mobile"
          title="Mobile — Chatter & Activités"
          subtitle="Responsive · même thread Odoo adapté au mobile · onglets Chatter / Activités / Pièces">
          <DCArtboard id="mob-chatter" label="Chatter (mobile)" width={420} height={820}>
            {wrap(<MobileChatter />)}
          </DCArtboard>
          <DCArtboard id="mob-activity" label="Activités (mobile)" width={420} height={820}>
            {wrap(<MobileActivity />)}
          </DCArtboard>
        </DCSection>

        <DCSection
          id="tokens"
          title="SCSS Variables — assurcourtage.scss"
          subtitle="Surcharge thème Odoo · à charger en prepend de web._assets_primary_variables">
          <DCArtboard id="tokens-palette" label="Palette" width={620} height={520}>
            <TokensPalette />
          </DCArtboard>
          <DCArtboard id="tokens-type" label="Typographie & Radius" width={620} height={520}>
            <TokensType />
          </DCArtboard>
          <DCArtboard id="tokens-overrides" label="Hooks Odoo surchargés" width={780} height={520}>
            <TokensOverrides />
          </DCArtboard>
        </DCSection>

      </DesignCanvas>

      <TweaksPanel>
        <TweakSection label="Persona">
          <TweakRadio
            label="Profil"
            value={persona}
            options={[
              { value: "courtier", label: "Courtier" },
              { value: "agent",    label: "Agent G." },
            ]}
            onChange={(v) => setTweak("persona", v)}
          />
        </TweakSection>

        <TweakSection label="Apparence">
          <TweakRadio
            label="Thème"
            value={theme}
            options={[
              { value: "light", label: "Clair" },
              { value: "dark",  label: "Sombre" },
            ]}
            onChange={(v) => setTweak("theme", v)}
          />
          <TweakRadio
            label="Densité"
            value={density}
            options={[
              { value: "compact",     label: "Compact" },
              { value: "comfortable", label: "Confort." },
            ]}
            onChange={(v) => setTweak("density", v)}
          />
        </TweakSection>

        <div style={{fontSize:11, color:'#888', marginTop:10, lineHeight:1.45, padding: '0 4px'}}>
          Les bascules cascadent depuis les <em>tokens CSS</em>, miroirs des SCSS overrides Odoo. Un dev Odoo obtient le même résultat en ajoutant un mode <code>color-mode-toggle</code> et en swappant les variables.
        </div>
      </TweaksPanel>
    </>
  );
}

// ── Token cards (unchanged) ─────────────────────────────────────────────────
function Swatch({ name, hex, value }) {
  return (
    <div style={{display:'flex', alignItems:'center', gap:10}}>
      <div style={{width:32, height:32, borderRadius:8, background:hex, border:'1px solid rgba(0,0,0,.06)', flex:'0 0 32px'}} />
      <div style={{flex:1, minWidth:0}}>
        <div style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ac-ink-700)'}}>{name}</div>
        <div style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ac-ink-500)'}}>{hex}</div>
      </div>
      {value && <div style={{fontSize:11, color:'var(--ac-ink-500)', fontFamily:'var(--font-mono)'}}>{value}</div>}
    </div>
  );
}

function TokensPalette() {
  return (
    <div style={{background:'#fff', height:'100%', padding:24, fontFamily:'var(--font-sans)', overflow:'auto'}}>
      <div style={{fontSize:11, color:'var(--ac-ink-500)', textTransform:'uppercase', letterSpacing:'.06em', fontWeight:600, marginBottom:6}}>1. Brand</div>
      <h2 style={{margin:'0 0 16px', fontSize:18, letterSpacing:'-.01em'}}>Bleu Assurance + Statuts</h2>

      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'12px 24px'}}>
        <Swatch name="$ac-blue-600 / $primary" hex="#1E40AF" value="Primary" />
        <Swatch name="$ac-blue-500" hex="#2D5BD6" />
        <Swatch name="$ac-blue-100" hex="#DBE6FF" />
        <Swatch name="$ac-blue-50"  hex="#EFF4FF" />

        <Swatch name="$ac-success / $success" hex="#15803D" value="Payé" />
        <Swatch name="$ac-success-bg" hex="#E6F4EC" />
        <Swatch name="$ac-danger / $danger" hex="#B91C1C" value="Impayé" />
        <Swatch name="$ac-danger-bg" hex="#FCEAEA" />
        <Swatch name="$ac-warning / $warning" hex="#B45309" value="À échoir" />
        <Swatch name="$ac-warning-bg" hex="#FEF1DC" />

        <Swatch name="$ac-ink-900 / $dark" hex="#0B1220" value="Texte" />
        <Swatch name="$ac-ink-500" hex="#5A6276" value="Muted" />
        <Swatch name="$ac-ink-100" hex="#E5E8EF" value="Border" />
        <Swatch name="$ac-paper / $body-bg" hex="#F7F8FB" value="Body" />
      </div>
    </div>
  );
}

function TokensType() {
  return (
    <div style={{background:'#fff', height:'100%', padding:24, fontFamily:'var(--font-sans)', overflow:'auto'}}>
      <div style={{fontSize:11, color:'var(--ac-ink-500)', textTransform:'uppercase', letterSpacing:'.06em', fontWeight:600, marginBottom:6}}>2. Type + 3. Surfaces</div>
      <h2 style={{margin:'0 0 16px', fontSize:18, letterSpacing:'-.01em'}}>Inter · 13px base · Radius 8/12</h2>

      <div style={{display:'flex', flexDirection:'column', gap:8, marginBottom:20}}>
        <div style={{fontSize:32, fontWeight:700, letterSpacing:'-.02em'}}>Famille Ben Salem</div>
        <div style={{fontSize:24, fontWeight:700, letterSpacing:'-.015em'}}>$h1 · Solde global</div>
        <div style={{fontSize:17, fontWeight:600, letterSpacing:'-.005em'}}>$h3 · Top Impayés</div>
        <div style={{fontSize:13, fontWeight:400}}>$font-size-base — texte courant du formulaire Odoo, dense et lisible (13/19 px). Variant en <strong>500</strong> pour les libellés clés, en <strong>600</strong> pour les titres.</div>
        <div style={{fontSize:11, color:'var(--ac-ink-500)', textTransform:'uppercase', letterSpacing:'.06em', fontWeight:600}}>$fs-xs · libellé champ</div>
        <div style={{fontFamily:'var(--font-mono)', fontSize:12, color:'var(--ac-ink-700)'}}>$font-family-monospace — 1 245,750 TND · 183 TU 4521</div>
      </div>

      <div style={{display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:10}}>
        {[
          { r:6,  l:"$border-radius-sm · 6px",  s:"badges, btn-sm" },
          { r:8,  l:"$border-radius · 8px",     s:"inputs, smart btns" },
          { r:12, l:"$border-radius-lg · 12px", s:"cards, sheet" },
        ].map(b => (
          <div key={b.r} style={{
            background:'var(--ac-paper)', border:'1px solid var(--ac-ink-100)',
            borderRadius: b.r, padding:14, textAlign:'center'
          }}>
            <div style={{fontSize:24, fontWeight:700}}>{b.r}px</div>
            <div style={{fontFamily:'var(--font-mono)', fontSize:10, color:'var(--ac-ink-500)'}}>{b.l}</div>
            <div style={{fontSize:11, color:'var(--ac-ink-500)', marginTop:2}}>{b.s}</div>
          </div>
        ))}
      </div>

      <div style={{marginTop:16, display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:10}}>
        {[
          { l:"$box-shadow-sm", s: "0 1px 2px rgba(11,18,32,.04)" },
          { l:"$box-shadow",    s: "0 4px 12px rgba(11,18,32,.06)" },
          { l:"$box-shadow-lg", s: "0 18px 36px rgba(11,18,32,.12)" },
        ].map((b, i) => (
          <div key={i} style={{
            background:'#fff', borderRadius:12, padding:14, height:64,
            boxShadow: b.s, display:'flex', flexDirection:'column', justifyContent:'space-between'
          }}>
            <div style={{fontFamily:'var(--font-mono)', fontSize:10, color:'var(--ac-ink-700)'}}>{b.l}</div>
            <div style={{fontSize:10, color:'var(--ac-ink-300)', fontFamily:'var(--font-mono)'}}>{b.s}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TokensOverrides() {
  const rows = [
    ["$o-brand-primary",       "$ac-blue-600", "Sidebar, links, primary buttons"],
    ["$o-action",              "$ac-blue-600", "Action menu highlights"],
    ["$o-view-background-color","$ac-paper",   "Backdrop of every view"],
    ["$o-form-sheet-bg",       "$ac-white",     "Inner sheet of o_form_view"],
    ["$o-form-sheet-radius",   ".75rem",        "12px — premium SaaS softness"],
    ["$o-control-panel-bg",    "$ac-white",     "Top control panel"],
    ["$o-control-panel-height","52px",          "Taller than native 44px"],
    ["$o-statusbar-active-bg", "$ac-blue-600",  "Active stage in pipeline"],
    ["$o-kanban-record-radius",".75rem",        "Rounded kanban cards"],
    ["$o-kanban-record-shadow","$box-shadow-sm","Soft elevation"],
    ["$o-button-box-radius",   ".75rem",        "oe_button_box smart-btn radius"],
    ["$o-chatter-background",  "$ac-paper",     "Differentiate chatter from form"],
  ];
  return (
    <div style={{background:'#fff', height:'100%', padding:24, fontFamily:'var(--font-sans)', overflow:'auto'}}>
      <div style={{fontSize:11, color:'var(--ac-ink-500)', textTransform:'uppercase', letterSpacing:'.06em', fontWeight:600, marginBottom:6}}>4. Odoo SCSS map hooks</div>
      <h2 style={{margin:'0 0 4px', fontSize:18, letterSpacing:'-.01em'}}>Surcharge des variables natives</h2>
      <div style={{fontSize:12, color:'var(--ac-ink-500)', marginBottom:14}}>
        Aucune règle CSS custom. Chaque visuel cascade depuis ces tokens — un développeur Odoo n'écrit que du XML.
      </div>

      <table style={{width:'100%', borderCollapse:'collapse', fontSize:12}}>
        <thead>
          <tr>
            <th style={{textAlign:'left', padding:'8px 10px', borderBottom:'1px solid var(--ac-ink-100)', fontSize:10, textTransform:'uppercase', letterSpacing:'.05em', color:'var(--ac-ink-500)'}}>Variable Odoo</th>
            <th style={{textAlign:'left', padding:'8px 10px', borderBottom:'1px solid var(--ac-ink-100)', fontSize:10, textTransform:'uppercase', letterSpacing:'.05em', color:'var(--ac-ink-500)'}}>Valeur</th>
            <th style={{textAlign:'left', padding:'8px 10px', borderBottom:'1px solid var(--ac-ink-100)', fontSize:10, textTransform:'uppercase', letterSpacing:'.05em', color:'var(--ac-ink-500)'}}>Effet</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{borderBottom:'1px solid var(--ac-ink-100)'}}>
              <td style={{padding:'7px 10px', fontFamily:'var(--font-mono)', color:'var(--ac-blue-700)'}}>{r[0]}</td>
              <td style={{padding:'7px 10px', fontFamily:'var(--font-mono)', color:'var(--ac-ink-900)'}}>{r[1]}</td>
              <td style={{padding:'7px 10px', color:'var(--ac-ink-700)'}}>{r[2]}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{marginTop:16, background:'var(--ac-paper)', padding:12, borderRadius:8, fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ac-ink-700)', lineHeight:1.6}}>
        <div style={{color:'var(--ac-ink-500)'}}>// __manifest__.py</div>
        'assets': {'{'}<br />
        &nbsp;&nbsp;'web._assets_primary_variables': [<br />
        &nbsp;&nbsp;&nbsp;&nbsp;('prepend', 'assurcourtage/static/src/scss/_variables.scss'),<br />
        &nbsp;&nbsp;],<br />
        {'}'}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

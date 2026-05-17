/* global React, Icon, I */
/*
  Mobile Chatter — vue mobile responsive du chatter Odoo.
  Format ~iPhone, 340x720, à coller dans un artboard de design canvas.
*/

function MobileChatter({ variant = "thread" }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'linear-gradient(135deg, #EFF4FF, #DBE6FF)',
      display: 'grid', placeItems: 'center',
      padding: '20px',
      fontFamily: 'var(--font-sans)',
    }}>
      <div className="phone">
        <div className="notch" />
        <div className="screen">
          <div className="statusbar">
            <span>9:41</span>
            <span className="right">
              <span>●●●</span>
              <span>⌃</span>
              <span className="bat"><span className="lvl" /></span>
            </span>
          </div>

          <div className="mobile_header">
            <span className="back">‹</span>
            <div className="av">BS</div>
            <div className="ttl">
              <div className="n">Famille Ben Salem</div>
              <div className="s">Mohamed · payeur · 3 polices</div>
            </div>
            <span style={{color:'var(--ac-blue-600)'}}><Icon d={I.more} size={20} /></span>
          </div>

          <div className="tabs">
            <div className="tab active">Chatter <span className="b">3</span></div>
            <div className="tab">Activités <span className="b">1</span></div>
            <div className="tab">Pièces <span className="b">28</span></div>
          </div>

          <div className="thread">
            <div className="day_sep">Aujourd'hui · 14 mai</div>

            <div className="msg log">
              <div className="head">
                <div className="av">⚙</div>
                <span className="nm">Système</span>
                <span className="tm">09:14</span>
              </div>
              <div className="bd">
                <strong>Appel de relance</strong> planifié pour <strong>17/05 — 10:00</strong>, assigné à Rim Ben Hadj.
              </div>
            </div>

            <div className="msg">
              <div className="head">
                <div className="av">SH</div>
                <span className="nm">Salim Hammami</span>
                <span className="tm">12:02</span>
              </div>
              <div className="bd">
                Relance WhatsApp envoyée à Mohamed pour la quittance <span className="ref">AUTO-2024-0142</span> (Peugeot 208 de Yassine). Réponse attendue avant vendredi.
              </div>
              <span className="att"><Icon d={I.attach} size={9} />relance-whatsapp.png</span>
            </div>

            <div className="day_sep">Hier · 13 mai</div>

            <div className="msg">
              <div className="head">
                <div className="av" style={{background:'var(--ac-blue-700)'}}>MA</div>
                <span className="nm">Mehdi Aloui</span>
                <span className="tm">16:48</span>
              </div>
              <div className="bd">
                Renouvellement MRH Marsa <span className="ref">MRH-2022-1547</span> validé par STAR. Avenant prêt à signer côté client.
              </div>
              <span className="att"><Icon d={I.attach} size={9} />avenant-2026.pdf</span>
            </div>

            <div className="msg log">
              <div className="head">
                <div className="av">✓</div>
                <span className="nm">Système</span>
                <span className="tm">15:12</span>
              </div>
              <div className="bd">
                État passé de <strong>Actif</strong> à <strong>Fidèle (5+ ans)</strong>.
              </div>
            </div>

            <div className="msg">
              <div className="head">
                <div className="av" style={{background:'var(--ac-success)'}}>RB</div>
                <span className="nm">Rim Ben Hadj</span>
                <span className="tm">10:34</span>
              </div>
              <div className="bd">
                Le client a confirmé par téléphone qu'il règle la quittance impayée vendredi matin (virement instantané).
              </div>
            </div>
          </div>

          <div className="composer">
            <div className="seg">
              <span className="opt on">Msg</span>
              <span className="opt">Note</span>
            </div>
            <input placeholder="Répondre…" />
            <div className="send"><Icon d="M2 12l20-9-9 20-2-9-9-2z" size={14} stroke={1.8} /></div>
          </div>
        </div>
        <div className="home_indicator" />
      </div>
    </div>
  );
}

function MobileActivity() {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'linear-gradient(135deg, #F0FDF4, #DCFCE7)',
      display: 'grid', placeItems: 'center',
      padding: '20px',
      fontFamily: 'var(--font-sans)',
    }}>
      <div className="phone">
        <div className="notch" />
        <div className="screen">
          <div className="statusbar">
            <span>9:41</span>
            <span className="right">
              <span>●●●</span>
              <span>⌃</span>
              <span className="bat"><span className="lvl" /></span>
            </span>
          </div>

          <div className="mobile_header">
            <span className="back">‹</span>
            <div className="av">BS</div>
            <div className="ttl">
              <div className="n">Famille Ben Salem</div>
              <div className="s">Mohamed · payeur · 3 polices</div>
            </div>
            <span style={{color:'var(--ac-blue-600)'}}><Icon d={I.more} size={20} /></span>
          </div>

          <div className="tabs">
            <div className="tab">Chatter <span className="b">3</span></div>
            <div className="tab active">Activités <span className="b">1</span></div>
            <div className="tab">Pièces <span className="b">28</span></div>
          </div>

          <div className="thread">
            <div style={{
              background:'var(--ac-warning-bg)',
              border:'1px solid #F5D8A6',
              borderRadius:12,
              padding:'12px 14px',
              marginBottom: 12,
            }}>
              <div style={{fontSize:10, color:'var(--ac-warning)', textTransform:'uppercase', letterSpacing:'.06em', fontWeight:700}}>En retard · 2 jours</div>
              <div style={{fontWeight:700, fontSize:14, marginTop:4, color:'var(--ac-ink-900)'}}>Relancer impayé AUTO-2024-0142</div>
              <div style={{fontSize:12, color:'var(--ac-ink-700)', marginTop:4}}>Quittance 1 245,750 TND — Peugeot 208 Yassine.</div>
              <div style={{display:'flex', gap:6, marginTop:10}}>
                <button className="btn btn-primary btn-sm" style={{flex:1}}>Appeler</button>
                <button className="btn btn-secondary btn-sm" style={{flex:1, background:'#fff'}}>Reporter</button>
              </div>
            </div>

            <div className="day_sep">À venir</div>

            <div className="msg">
              <div className="head">
                <div className="av">RB</div>
                <span className="nm">Appel de relance</span>
                <span className="tm">17/05 · 10:00</span>
              </div>
              <div className="bd" style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                <span>Assigné à Rim Ben Hadj</span>
                <span style={{
                  background:'var(--ac-blue-50)', color:'var(--ac-blue-700)',
                  padding:'2px 8px', borderRadius:999, fontSize:10, fontWeight:600
                }}>+3j</span>
              </div>
            </div>

            <div className="msg">
              <div className="head">
                <div className="av" style={{background:'var(--ac-blue-700)'}}>MA</div>
                <span className="nm">Signer avenant MRH</span>
                <span className="tm">22/05 · —</span>
              </div>
              <div className="bd" style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                <span>Assigné à Mehdi Aloui</span>
                <span style={{
                  background:'var(--ac-blue-50)', color:'var(--ac-blue-700)',
                  padding:'2px 8px', borderRadius:999, fontSize:10, fontWeight:600
                }}>+8j</span>
              </div>
            </div>

            <div className="msg">
              <div className="head">
                <div className="av" style={{background:'var(--ac-success)'}}>SH</div>
                <span className="nm">Renouvellement Santé</span>
                <span className="tm">25/08 · —</span>
              </div>
              <div className="bd" style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                <span>SAN-2023-0089 · Famille</span>
                <span style={{
                  background:'var(--ac-ink-50)', color:'var(--ac-ink-500)',
                  padding:'2px 8px', borderRadius:999, fontSize:10, fontWeight:600
                }}>+100j</span>
              </div>
            </div>

            <div style={{
              marginTop:14, padding:14, textAlign:'center',
              border:'1px dashed var(--ac-ink-100)', borderRadius:12,
              color:'var(--ac-blue-600)', fontWeight:600, fontSize:13
            }}>
              + Planifier une activité
            </div>
          </div>

          <div className="composer">
            <div style={{flex:1, fontSize:11, color:'var(--ac-ink-500)', textAlign:'center'}}>
              3 activités · 1 en retard
            </div>
            <button className="btn btn-primary btn-sm">Tout voir</button>
          </div>
        </div>
        <div className="home_indicator" />
      </div>
    </div>
  );
}

window.MobileChatter = MobileChatter;
window.MobileActivity = MobileActivity;

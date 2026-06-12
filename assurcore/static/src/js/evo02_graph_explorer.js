/** @odoo-module **/
// =============================================================================
//  EVO02 — Lot 3 : GraphExplorer (client action "assurcore_graph")
//  Navigation : clic = le nœud devient racine (breadcrumb Odoo natif),
//  double-clic = ouvrir la fiche, survol = info-bulle détaillée.
//  RG-1 (exclusion du type racine) est appliquée côté serveur.
// =============================================================================

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, useRef, markup } from "@odoo/owl";

const NODE_W = 132;
const ROOT_W = 168;
const NODE_H = 46;
const LEVEL_H = 122;
const SVG_W = 1180;

const TYPE_LABEL = {
    operation: "opération",
    receipt: "quittance",
    settlement: "règlement",
    partner: "client",
};

const TYPE_COLOR = {
    operation:  { fill: "#F1EFE8", stroke: "#5F5E5A", text: "#444441" },
    receipt:    { fill: "#EEEDFE", stroke: "#534AB7", text: "#3C3489" },
    settlement: { fill: "#FAECE7", stroke: "#993C1D", text: "#712B13" },
    partner:    { fill: "#E1F5EE", stroke: "#0F6E56", text: "#085041" },
};
const STATE_COLOR = {
    partielle:  { fill: "#FAEEDA", stroke: "#854F0B", text: "#633806" },
    non_reglee: { fill: "#FAEEDA", stroke: "#854F0B", text: "#633806" },
};

export class GraphExplorer extends Component {
    static template = "assurcore.GraphExplorer";
    static props = { "*": true };

    setup() {
        this.action = useService("action");
        this.rpc = useService("rpc");
        this.containerRef = useRef("container");
        this.tooltipRef = useRef("tooltip");
        const p = this.props.action?.params || this.props.action?.context?.params || {};
        // Retour navigateur : les params ne survivent pas dans l'URL ->
        // on restaure le dernier contexte depuis sessionStorage.
        let model = p.model, resId = p.res_id;
        if (!resId) {
            try {
                const saved = JSON.parse(sessionStorage.getItem("assurcore_graph_ctx") || "null");
                if (saved) { model = saved.model; resId = saved.resId; }
            } catch (e) { /* ignore */ }
        }
        if (resId) {
            sessionStorage.setItem("assurcore_graph_ctx",
                JSON.stringify({ model: model || "operation", resId }));
        }
        this.state = useState({
            model: model || "operation",
            resId: resId,
            svg: "",
            error: "",
            rootLabel: "",
            truncatedMsg: "",
        });
        onWillStart(() => this.load());
    }

    async load() {
        if (!this.state.resId) {
            this.state.error = "Contexte du graphe perdu. Rouvrez le graphe " +
                "depuis la fiche d'un enregistrement (bouton Graphe).";
            return;
        }
        try {
            const data = await this.rpc("/assurcore/graph/node", {
                model: this.state.model,
                res_id: this.state.resId,
                limit_per_level: 25,
            });
            if (data.error) {
                this.state.error = data.error;
                return;
            }
            this.graph = data;
            this.nodesByKey = Object.fromEntries(data.nodes.map((n) => [n.key, n]));
            const root = this.nodesByKey[data.root.key];
            this.state.rootLabel = `${root.label} (${TYPE_LABEL[root.type]})`;
            const trunc = Object.entries(data.truncated || {})
                .filter(([, v]) => v.truncated)
                .map(([k, v]) => `${k} : +${v.remaining} non affichés`);
            this.state.truncatedMsg = trunc.join(" · ");
            this.state.svg = markup(this.renderSvg(data));
        } catch (e) {
            this.state.error = e.message || String(e);
        }
    }

    // ── Layout en couches (BFS depuis la racine) ─────────────────────────────
    computeLevels(data) {
        const adj = {};
        for (const e of data.edges) {
            (adj[e.from] = adj[e.from] || []).push(e.to);
            (adj[e.to] = adj[e.to] || []).push(e.from);
        }
        const level = { [data.root.key]: 0 };
        const order = [[data.root.key]];
        let frontier = [data.root.key];
        while (frontier.length) {
            const next = [];
            for (const k of frontier) {
                for (const n of adj[k] || []) {
                    if (level[n] === undefined && this.nodesByKey[n]) {
                        level[n] = level[k] + 1;
                        (order[level[n]] = order[level[n]] || []).push(n);
                        next.push(n);
                    }
                }
            }
            frontier = next;
        }
        return order;
    }

    renderSvg(data) {
        const order = this.computeLevels(data);
        const pos = {};
        order.forEach((row, i) => {
            const step = SVG_W / (row.length + 1);
            row.forEach((key, j) => {
                pos[key] = { x: step * (j + 1), y: 64 + i * LEVEL_H };
            });
        });
        const H = 64 + (order.length - 1) * LEVEL_H + 70;
        let s = "";

        for (const e of data.edges) {
            const a0 = pos[e.from], b0 = pos[e.to];
            if (!a0 || !b0) continue;
            let a = a0, b = b0;
            if (a.y > b.y) { a = b0; b = a0; }
            const dash = e.kind === "structure" ? 'stroke-dasharray="4 4"' : "";
            const color = e.reconstructed ? "#BA7517" : "#A9A7A0";
            if (a.y === b.y) {
                const my = a.y - 52;
                s += `<path d="M${a.x} ${a.y - NODE_H / 2} C ${a.x} ${my}, ${b.x} ${my}, ${b.x} ${b.y - NODE_H / 2}" fill="none" stroke="${color}" stroke-width="1" ${dash}/>`;
            } else {
                s += `<line x1="${a.x}" y1="${a.y + NODE_H / 2}" x2="${b.x}" y2="${b.y - NODE_H / 2}" stroke="${color}" stroke-width="${e.kind === "allocation" ? 1.5 : 1}" ${dash}/>`;
            }
            if (e.amount !== undefined) {
                const mx = (a.x + b.x) / 2, my = a.y === b.y ? a.y - 56 : (a.y + b.y) / 2;
                const extra = e.third_party ? " (tiers)" : "";
                s += `<text x="${mx + 6}" y="${my}" font-size="11" fill="#5F5E5A">${this.fmt(e.amount)}${extra}</text>`;
            }
        }

        for (const key of Object.keys(pos)) {
            const n = this.nodesByKey[key];
            const p = pos[key];
            const w = n.is_root ? ROOT_W : NODE_W;
            let c = TYPE_COLOR[n.type] || TYPE_COLOR.operation;
            if (n.type === "operation" && STATE_COLOR[n.state]) {
                c = STATE_COLOR[n.state];
            }
            const danger = n.health === "anomalie"
                ? `stroke="#A32D2D" stroke-width="2.5"`
                : `stroke="${c.stroke}" stroke-width="${n.is_root ? 1.8 : 0.8}"`;
            const label = this.trim(n.label, n.is_root ? 24 : 17);
            const sub = this.trim(n.subtitle || TYPE_LABEL[n.type], n.is_root ? 26 : 19);
            const bx = p.x + w / 2 - 11, by = p.y - NODE_H / 2 + 11;
            s += `<g data-key="${key}" style="cursor:pointer">
                <rect x="${p.x - w / 2}" y="${p.y - NODE_H / 2}" width="${w}" height="${NODE_H}" rx="6" fill="${c.fill}" ${danger}/>
                <text x="${p.x}" y="${p.y - 3}" text-anchor="middle" font-size="12.5" font-weight="600" fill="${c.text}">${this.esc(label)}${n.is_root ? " · sommet" : ""}</text>
                <text x="${p.x}" y="${p.y + 13}" text-anchor="middle" font-size="11" fill="${c.stroke}">${this.esc(sub)}</text>
                <g data-open="${key}" style="cursor:pointer"><title>Ouvrir la fiche</title>
                    <circle cx="${bx}" cy="${by}" r="8" fill="#ffffff" stroke="${c.stroke}" stroke-width="0.8"/>
                    <text x="${bx}" y="${by + 3.5}" text-anchor="middle" font-size="10" fill="${c.stroke}">&#8599;</text>
                </g>
            </g>`;
        }
        return `<svg width="100%" viewBox="0 0 ${SVG_W} ${H}" xmlns="http://www.w3.org/2000/svg">${s}</svg>`;
    }

    fmt(v) {
        return Number(v).toLocaleString("fr-FR", { minimumFractionDigits: 3 });
    }
    trim(s, n) {
        return (s || "").length > n ? s.slice(0, n - 1) + "…" : (s || "");
    }
    esc(s) {
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // ── Interactions ─────────────────────────────────────────────────────────
    nodeFromEvent(ev) {
        const g = ev.target.closest("[data-key]");
        return g ? this.nodesByKey[g.dataset.key] : null;
    }

    onClick(ev) {
        const openBtn = ev.target.closest("[data-open]");
        if (openBtn) {
            const node = this.nodesByKey[openBtn.dataset.open];
            if (node) this.openForm(node);
            return;
        }
        const n = this.nodeFromEvent(ev);
        if (!n || n.is_root) return;
        sessionStorage.setItem("assurcore_graph_ctx",
            JSON.stringify({ model: n.type, resId: n.action.res_id }));
        this.action.doAction({
            type: "ir.actions.client",
            tag: "assurcore_graph",
            name: `Graphe — ${n.label}`,
            params: { model: n.type, res_id: n.action.res_id },
        });
    }

    openForm(n) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: n.action.res_model,
            res_id: n.action.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onDblClick(ev) {
        const n = this.nodeFromEvent(ev);
        if (n) this.openForm(n);
    }

    onMouseMove(ev) {
        const tip = this.tooltipRef.el;
        if (!tip) return;
        const n = this.nodeFromEvent(ev);
        if (!n) {
            tip.style.display = "none";
            return;
        }
        const rows = Object.entries(n.tooltip || {})
            .filter(([, v]) => v !== "" && v !== false)
            .map(([k, v]) => `<b>${this.esc(k)}</b> : ${this.esc(v)}`);
        tip.innerHTML = rows.join("<br/>");
        tip.style.display = "block";
        const rect = this.containerRef.el.getBoundingClientRect();
        let x = ev.clientX - rect.left + 14;
        const y = ev.clientY - rect.top + 14;
        if (x > rect.width - 280) x -= 300;
        tip.style.left = x + "px";
        tip.style.top = y + "px";
    }

    onMouseLeave() {
        if (this.tooltipRef.el) this.tooltipRef.el.style.display = "none";
    }
}

registry.category("actions").add("assurcore_graph", GraphExplorer);

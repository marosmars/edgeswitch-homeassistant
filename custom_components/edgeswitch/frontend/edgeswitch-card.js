// EdgeSwitch front panel with port and PoE control. Bundled with the edgeswitch integration, which serves it at
// /edgeswitch/edgeswitch-card.js and loads it on every dashboard, so no Lovelace resource is needed. Config (all optional):
//   type: custom:edgeswitch-card
//   prefix: es16_maros         entity id prefix after the domain; auto-detected when there is one switch
//   poe_budget: 150            W, for the budget bar; default from the model name (ES-16-150W → 150)
//   sfp: [17, 18]              SFP ports (drawn as cages, no PoE); default: ports above the model's RJ45 count
//   protect: [1, 2]            ports that can't be turned off or restarted from the card (uplink / path to HA:
//                              turning those off would cut HA off the switch, so it could never turn them back on)
//   vlan_colors: {40: '#42a5f5'}  per-VLAN colors (default: a built-in palette; VLAN 1 stays uncolored)
//   cycle_seconds: 5           off time for PoE/port restart (service edgeswitch.cycle_port, runs inside HA)
//   cycle_script: script.x     fallback for restarts when the integration has no edgeswitch.cycle_port service (older versions)
// Tap a port to show its details and controls in the panel right of the ports. Every action that cuts power or link needs a second tap within 4 s.
// UI language follows the HA language (English and Slovak built in).
const STRINGS = {
  en: {
    temp: 'Temp', links: 'Links', of: 'of', confirm: 'Sure?', off: 'Off', on: 'On', restart: 'Restart',
    hint: 'Tap a port for details and controls (PoE, port, restart).',
    protected: 'Protected port (uplink / path to HA) – turning it off could not be undone from here',
    noName: 'no name', noLink: 'no link', portOff: 'port disabled', poeOff: 'off', link: 'link',
    noEntities: 'No EdgeSwitch entities found. Set prefix: in the card config.', port: 'Port',
    poeOffAct: 'Turn PoE off', poeOnAct: 'Turn PoE on', poeCycle: 'Restart PoE', portOffAct: 'Disable port', portOnAct: 'Enable port', portCycle: 'Restart port', again: 'Sure?', pick: 'Tap a port for details and controls.', lgLink: 'link 1G', lgSlow: 'link < 1G', lgDis: 'port disabled', lgPoe: 'PoE draws power', lgTrunk: 'trunk', lgUntag: 'untagged (port outline)', lgTag: 'tagged (dot)', vlans: 'VLANs',
  },
  sk: {
    temp: 'Teplota', links: 'Linky', of: 'z', confirm: 'Naozaj?', off: 'Vypnúť', on: 'Zapnúť', restart: 'Reštart',
    hint: 'Ťukni na port pre detail a ovládanie (PoE, port, reštart).',
    protected: 'Chránený port (uplink / cesta k HA) – vypnutie by sa nedalo vrátiť',
    noName: 'bez názvu', noLink: 'bez linky', portOff: 'port vypnutý', poeOff: 'vyp', link: 'link',
    noEntities: 'Nenašli sa entity EdgeSwitch. Nastav prefix: v konfigurácii karty.', port: 'Port',
    poeOffAct: 'Vypnúť PoE', poeOnAct: 'Zapnúť PoE', poeCycle: 'Reštartovať PoE', portOffAct: 'Vypnúť port', portOnAct: 'Zapnúť port', portCycle: 'Reštartovať port', again: 'Naozaj?', pick: 'Ťukni na port pre detail a ovládanie.', lgLink: 'link 1G', lgSlow: 'link < 1G', lgDis: 'port vypnutý', lgPoe: 'PoE odber', lgTrunk: 'trunk', lgUntag: 'untagged (obrys portu)', lgTag: 'tagged (bodka)', vlans: 'VLANy',
  },
};
const VLAN_PALETTE = ['#42a5f5', '#ab47bc', '#26a69a', '#ef6c00', '#ec407a', '#7cb342', '#8d6e63', '#5c6bc0'];
const SPEED = { '1000-full': '1G', '100-full': '100M', '100-half': '100M½', '10-full': '10M', '10-half': '10M½' };

class EdgeSwitchCard extends HTMLElement {
  setConfig(config) {
    this._config = { protect: [], cycle_seconds: 5, ...config };
    this._sel = null; // selected port number
    this._armed = null; // action key waiting for the second tap
    this._busy = {}; // action key -> { until, done(port) }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    this._t = STRINGS[(hass.locale?.language || hass.language || 'en').split('-')[0]] || STRINGS.en;
    this._resolve();
    this._tick();
  }

  connectedCallback() {
    this._key = (ev) => ev.key === 'Escape' && this._sel !== null && this._close();
    document.addEventListener('keydown', this._key);
  }

  disconnectedCallback() {
    document.removeEventListener('keydown', this._key);
  }

  _close() {
    this._sel = null;
    this._armed = null;
    this._tick();
  }

  static getStubConfig() {
    return {};
  }

  // Fill prefix, sfp and poe_budget from the live entities when the config leaves them out.
  _resolve() {
    const c = this._config;
    if (!c.prefix) {
      const prefixes = new Set();
      for (const [id, st] of Object.entries(this._hass.states)) {
        const m = id.match(/^switch\.(.+)_port_\d+_poe$/);
        const reg = this._hass.entities?.[id];
        if (m && (reg ? reg.platform === 'edgeswitch' : st.attributes.poe_mode !== undefined)) prefixes.add(m[1]);
      }
      this._prefix = [...prefixes].sort()[0];
    } else this._prefix = c.prefix;
    const model = this._st(`sensor.${this._prefix}_firmware`)?.attributes.model || '';
    const m = model.match(/^ES-(\d+)-(\d+)W/i);
    this._sfp = c.sfp || (m ? Array.from({ length: 4 }, (_, i) => +m[1] + 1 + i) : []);
    const vlist = this._st(`sensor.${this._prefix}_vlan_count`)?.attributes.vlans || [];
    this._vlans = vlist.filter((v) => v.id !== 1).map((v, i) => ({ ...v, color: c.vlan_colors?.[v.id] || VLAN_PALETTE[i % VLAN_PALETTE.length] }));
    this._vlanColor = Object.fromEntries(this._vlans.map((v) => [v.id, v.color]));
    this._budget = c.poe_budget || (m ? +m[2] : 0);
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return { columns: 'full', rows: 'auto' };
  }

  _st(id) {
    return this._hass.states[id];
  }

  _num(id) {
    const v = parseFloat(this._st(id)?.state);
    return Number.isFinite(v) ? v : null;
  }

  // Rate sensor state in bit/s, whatever unit the entity displays in.
  _bps(id) {
    const st = this._st(id);
    const v = parseFloat(st?.state);
    if (!Number.isFinite(v)) return null;
    const mul = { 'bit/s': 1, 'kbit/s': 1e3, 'Mbit/s': 1e6, 'Gbit/s': 1e9, 'B/s': 8, 'kB/s': 8e3, 'MB/s': 8e6, 'GB/s': 8e9 };
    return v * (mul[st.attributes.unit_of_measurement] ?? 1);
  }

  _fmtRate(bps, long = false) {
    if (bps === null) return '–';
    const [div, unit] = bps >= 1e9 ? [1e9, 'G'] : bps >= 1e6 ? [1e6, 'M'] : bps >= 1e3 ? [1e3, 'k'] : [1, ''];
    const v = bps / div;
    return `${v >= 100 || div === 1 ? Math.round(v) : v.toFixed(1)}${long ? ` ${unit}bit/s` : unit}`;
  }

  _ports() {
    const p = this._prefix;
    const re = new RegExp(`^switch\\.${p}_port_(\\d+)$`);
    const ports = [];
    for (const id of Object.keys(this._hass.states)) {
      const m = id.match(re);
      if (!m) continue;
      const n = +m[1];
      const sw = this._st(id);
      const a = sw.attributes;
      const sfp = this._sfp.includes(n);
      const poe = sfp ? null : this._st(`switch.${p}_port_${n}_poe`);
      ports.push({
        n, sfp,
        name: a.port_name || '',
        short: (a.port_name || '').replace(/\s*\[[^\]]*\]\s*/g, ' ').trim(),
        enabled: sw.state === 'on',
        up: a.link_status === 'up',
        speed: SPEED[a.speed] || (a.link_status === 'up' ? a.speed : ''),
        rawSpeed: a.speed,
        slow: a.link_status === 'up' && a.speed !== '1000-full',
        stp: a.stp_state,
        trunk: a.is_trunk,
        nativeId: a.native_vlan_id,
        native: a.native_vlan_name,
        tagged: a.tagged_vlans || [],
        taggedIds: (a.tagged_vlans || []).map((v) => parseInt(v, 10)).filter(Number.isFinite),
        poe: poe ? poe.state : null,
        poeMode: poe?.attributes.poe_mode,
        watts: this._num(`sensor.${p}_port_${n}_poe_power`) || 0,
        // rx = received by the switch = the device's upload; tx = the device's download
        upBps: this._bps(`sensor.${p}_port_${n}_rx_rate`),
        downBps: this._bps(`sensor.${p}_port_${n}_tx_rate`),
      });
    }
    return ports.sort((a, b) => a.n - b.n);
  }

  // Re-render, dropping busy markers whose target state arrived or whose time ran out.
  _tick() {
    const ports = this._ports();
    const now = Date.now();
    for (const [k, b] of Object.entries(this._busy)) {
      const port = ports.find((x) => x.n === b.n);
      if (now > b.until || (port && b.done(port))) delete this._busy[k];
    }
    this._render(ports);
  }

  _notify(message) {
    this.dispatchEvent(new CustomEvent('hass-notification', { bubbles: true, composed: true, detail: { message } }));
  }

  _onClick(ev) {
    const path = ev.composedPath();
    const cell = path.find((el) => el.dataset?.port);
    if (cell) {
      const n = +cell.dataset.port;
      this._sel = this._sel === n ? null : n;
      this._armed = null;
      return this._tick();
    }
    if (path.some((el) => el.dataset?.close)) return this._close();
    const btn = path.find((el) => el.dataset?.act);
    if (!btn || btn.disabled) return;
    const [act, nStr] = btn.dataset.act.split(':');
    const n = +nStr;
    const key = btn.dataset.act;
    if (this._busy[key]) return;
    if (btn.dataset.confirm && this._armed !== key) {
      this._armed = key;
      clearTimeout(this._armTimer);
      this._armTimer = setTimeout(() => { this._armed = null; this._tick(); }, 4000);
      return this._tick();
    }
    this._armed = null;
    this._run(act, n, key);
  }

  _run(act, n, key) {
    const p = this._prefix;
    const portId = `switch.${p}_port_${n}`;
    const poeId = `switch.${p}_port_${n}_poe`;
    const cycleMs = this._config.cycle_seconds * 1000;
    const cycle = this._hass.services?.edgeswitch?.cycle_port || !this._config.cycle_script
      ? ['edgeswitch', 'cycle_port'] : this._config.cycle_script.split('.');
    const plan = {
      poe_off: ['switch', 'turn_off', { entity_id: poeId }, (x) => x.poe === 'off', 45000],
      poe_on: ['switch', 'turn_on', { entity_id: poeId }, (x) => x.poe === 'on', 45000],
      port_off: ['switch', 'turn_off', { entity_id: portId }, (x) => !x.enabled, 45000],
      port_on: ['switch', 'turn_on', { entity_id: portId }, (x) => x.enabled, 45000],
      poe_cycle: [...cycle, { entity_id: poeId, off_seconds: this._config.cycle_seconds }, () => false, cycleMs + 8000],
      port_cycle: [...cycle, { entity_id: portId, off_seconds: this._config.cycle_seconds }, () => false, cycleMs + 8000],
    }[act];
    if (!plan) return;
    const [domain, service, data, done, ms] = plan;
    this._busy[key] = { n, done, until: Date.now() + ms };
    setTimeout(() => this._tick(), ms + 100);
    this._tick();
    this._hass.callService(domain, service, data).catch((err) => {
      delete this._busy[key];
      this._tick();
      this._notify(`Port ${n}: ${err.message || err}`);
    });
  }

  _header(ports) {
    const p = this._prefix;
    const fw = this._st(`sensor.${p}_firmware`);
    const host = this._st(`text.${p}_hostname`)?.state || 'EdgeSwitch';
    const ip = this._st(`sensor.${p}_management_ip`)?.state || '';
    const up = this._st(`sensor.${p}_uptime`)?.attributes.formatted || '';
    const temps = Object.keys(this._hass.states).filter((id) => id.startsWith(`sensor.${p}_temperature_`)).map((id) => this._num(id)).filter((v) => v !== null);
    const poe = this._num(`sensor.${p}_total_poe_power`) || 0;
    const pct = this._budget ? Math.min(100, (poe / this._budget) * 100) : 0;
    const gauge = (label, v, unit, warn, crit) => {
      const cls = v === null ? '' : v >= crit ? 'crit' : v >= warn ? 'warn' : 'ok';
      return `<div class="stat ${cls}"><span class="v">${v === null ? '–' : Math.round(v)}<small>${unit}</small></span><span class="l">${label}</span></div>`;
    };
    return `
      <div class="top">
        <div class="id">
          <ha-icon icon="mdi:switch"></ha-icon>
          <div><div class="host">${host}</div>
          <div class="meta">${fw?.attributes.model || ''} · ${ip} · fw ${fw?.state || ''} · up ${up}</div></div>
        </div>
        <div class="stats">
          ${gauge('CPU', this._num(`sensor.${p}_cpu_usage`), '%', 70, 90)}
          ${gauge('RAM', this._num(`sensor.${p}_memory_usage`), '%', 75, 90)}
          ${gauge(this._t.temp, temps.length ? Math.max(...temps) : null, '°C', 70, 80)}
          <div class="stat"><span class="v">${ports.filter((x) => x.up).length}<small>/${ports.length}</small></span><span class="l">${this._t.links}</span></div>
          <div class="stat poe" title="PoE ${poe.toFixed(1)} W ${this._t.of} ${this._budget} W">
            <span class="v">${poe.toFixed(1)}<small>${this._budget ? `/${this._budget}` : ''} W</small></span>
            <span class="pbar"><i style="width:${pct}%"></i></span>
          </div>
        </div>
      </div>`;
  }

  _cell(x, bottom) {
    const busy = Object.values(this._busy).some((b) => b.n === x.n);
    const cls = [
      'cell', bottom ? 'bot' : 'upr', x.sfp ? 'sfp' : 'rj',
      x.up ? (x.slow ? 'slow' : 'up') : 'down',
      x.enabled ? '' : 'dis', x.watts > 0 ? 'pw' : '', x.poe === 'off' ? 'poeoff' : '',
      this._sel === x.n ? 'sel' : '', busy ? 'busy' : '',
    ].filter(Boolean).join(' ');
    const dots = x.taggedIds.map((id) => `<i class="vd" style="background:${this._vlanColor[id] || 'var(--fp-dim)'}"></i>`).join('');
    const nativeColor = x.nativeId !== 1 ? this._vlanColor[x.nativeId] : null;
    // 1G is the norm, so only a slower link shows its speed (inside the jack). A disabled port is hatched with a red LED.
    const rates = x.up && x.downBps !== null
      ? `<span class="dn-r${x.downBps ? '' : ' zero'}">↓${this._fmtRate(x.downBps)}</span><span class="up-r${x.upBps ? '' : ' zero'}">↑${this._fmtRate(x.upBps)}</span>` : '';
    const label = `
      <div class="lbl">
        <div class="nm${x.short ? '' : ' empty'}">${x.trunk ? '<ha-icon class="trk" icon="mdi:swap-vertical-bold"></ha-icon>' : ''}<span>${x.short || '—'}</span></div>
        <div class="rates">${rates}</div>
      </div>`;
    const jack = `
      <div class="jackrow">
        <span class="no">${x.n}</span>
        <div class="jack">${x.watts > 0 ? `<span class="w">${x.watts.toFixed(1)}W</span>` : ''}${dots ? `<span class="dots">${dots}</span>` : ''}${x.slow ? `<span class="jspd">${x.speed}</span>` : ''}${busy ? '<ha-icon icon="mdi:loading" class="spin"></ha-icon>' : ''}</div>
        <span class="leds"><i class="l1"></i><i class="l2"></i></span>
      </div>`;
    return `<div class="${cls}${nativeColor ? ' nv' : ''}"${nativeColor ? ` style="--vc:${nativeColor}"` : ''} data-port="${x.n}" title="${x.n}: ${x.name || '—'}">${bottom ? jack + label : label + jack}</div>`;
  }

  _chassis(ports) {
    const rj = ports.filter((x) => !x.sfp);
    const sfp = ports.filter((x) => x.sfp);
    const odd = rj.filter((x) => x.n % 2).map((x) => this._cell(x, false)).join('');
    const even = rj.filter((x) => !(x.n % 2)).map((x) => this._cell(x, true)).join('');
    const cols = Math.ceil(rj.length / 2);
    return `
      <div class="chassis-wrap"><div class="chassis">
        <div class="ports">
          <div class="rjgrid" style="--cols:${cols}">${odd}${even}</div>
          ${sfp.length ? `<div class="sfpgrid">${sfp.map((x, i) => this._cell(x, i % 2 === 1)).join('')}</div>` : ''}
        </div>
        <div class="side"><div class="sidein">${this._panel(ports.find((x) => x.n === this._sel))}</div></div>
      </div></div>`;
  }

  _btn(act, n, icon, text, { confirm = false, disabled = false, kind = '' } = {}) {
    const key = `${act}:${n}`;
    const busy = !!this._busy[key];
    const armed = this._armed === key;
    const cls = ['act', kind, armed ? 'armed' : '', busy ? 'busy' : ''].filter(Boolean).join(' ');
    return `<button class="${cls}" data-act="${key}"${confirm ? ' data-confirm="1"' : ''}${disabled ? ' disabled' : ''}>
      <ha-icon icon="${busy ? 'mdi:loading' : icon}"${busy ? ' class="spin"' : ''}></ha-icon><span>${armed ? this._t.again : text}</span></button>`;
  }

  _panel(x) {
    const t = this._t;
    if (!x) {
      return `
        <div class="pick"><ha-icon icon="mdi:gesture-tap"></ha-icon>${t.pick}</div>
        <div class="legend">
          <span><i class="lg g"></i>${t.lgLink}</span><span><i class="lg a"></i>${t.lgSlow}</span>
          <span><i class="lg r"></i>${t.lgDis}</span><span><i class="lg a2"></i>${t.lgPoe}</span>
          <span><ha-icon class="trk" icon="mdi:swap-vertical-bold"></ha-icon>${t.lgTrunk}</span>
        </div>
        ${this._vlans.length ? `
        <div class="vlegend">
          <div class="vlh">${t.vlans}<span>${t.lgUntag} · ${t.lgTag}</span></div>
          ${this._vlans.map((v) => `<span title="VLAN ${v.id}"><i class="vsw" style="--vc:${v.color}"></i>${v.name === `VLAN ${v.id}` ? v.name : `${v.id} ${v.name}`}</span>`).join('')}
        </div>` : ''}`;
    }
    const prot = this._config.protect.includes(x.n);
    const secs = `${this._config.cycle_seconds}s`;
    const vdot = (id) => `<i class="vd" style="background:${this._vlanColor[id] || 'var(--fp-dim)'}"></i>`;
    const vlans = [
      ...(x.native ? [`${vdot(x.nativeId)}<b>${x.native}</b>`] : []),
      ...x.tagged.map((v) => `${vdot(parseInt(v, 10))}${v.replace(/^\d+ \((.*)\)$/, '$1')}`),
    ].join(' ');
    const poe = x.poe === null ? '' : `
      <div class="prow"><span class="gl">PoE${x.poe === 'on' ? `<small>${x.watts.toFixed(1)}W</small>` : ''}</span>
        ${x.poe === 'on'
          ? this._btn('poe_off', x.n, 'mdi:flash-off', t.off, { confirm: true, kind: 'danger' })
          : this._btn('poe_on', x.n, 'mdi:flash', t.on, { kind: 'good' })}
        ${this._btn('poe_cycle', x.n, 'mdi:restart', `${t.restart} ${secs}`, { confirm: true, disabled: x.poe !== 'on' })}
      </div>`;
    return `
      <div class="pinfo">
      <div class="ptitle"><span class="dn">${x.n}</span><span class="pname">${x.name || `<i>${t.noName}</i>`}</span>${prot ? `<ha-icon class="shield" icon="mdi:shield-lock" title="${t.protected}"></ha-icon>` : ''}
        <button class="x" data-close="1" title="Esc"><ha-icon icon="mdi:close"></ha-icon></button></div>
      <div class="pmeta prate">${x.enabled ? (x.up ? x.rawSpeed : t.noLink) : `<b class="bad">${t.portOff}</b>`} · STP ${x.stp || '–'}${x.up ? `<span class="dn-r">↓${this._fmtRate(x.downBps, true)}</span><span class="up-r">↑${this._fmtRate(x.upBps, true)}</span>` : ''}</div>
      ${vlans ? `<div class="pmeta one pvl">${vlans}</div>` : ''}
      </div>
      <div class="pacts">
        ${poe}
        <div class="prow"><span class="gl">${t.port}</span>
          ${x.enabled
            ? this._btn('port_off', x.n, 'mdi:lan-disconnect', t.off, { confirm: true, kind: 'danger', disabled: prot })
            : this._btn('port_on', x.n, 'mdi:lan-connect', t.on, { kind: 'good' })}
          ${this._btn('port_cycle', x.n, 'mdi:restart', `${t.restart} ${secs}`, { confirm: true, disabled: prot || !x.enabled })}
        </div>
      </div>`;
  }

  _render(ports) {
    if (!this._hass) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
      this.shadowRoot.addEventListener('click', (ev) => this._onClick(ev));
    }
    if (!ports.length) {
      this.shadowRoot.innerHTML = `<ha-card><div style="padding:16px">${this._t.noEntities}</div></ha-card>`;
      return;
    }
    const scroll = this.shadowRoot.querySelector('.chassis-wrap')?.scrollLeft || 0;
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 10px 12px 12px; box-shadow: 0 1px 2px rgba(0,0,0,.08), 0 4px 14px rgba(0,0,0,.07); --ok: #4caf50; --slow: #ffa000; --pw: #f9a825; --bad: var(--error-color, #db4437); }
        .top { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px;
                margin: -10px -12px 0; padding: 8px 12px; border-radius: var(--ha-card-border-radius, 12px) var(--ha-card-border-radius, 12px) 0 0;
                background: color-mix(in srgb, var(--primary-color) 7%, transparent); border-bottom: 1px solid var(--divider-color); }
        .id { display: flex; align-items: center; gap: 10px; min-width: 0; }
        .id ha-icon { --mdc-icon-size: 34px; color: var(--primary-color); }
        .host { font-size: 18px; font-weight: 600; line-height: 1.2; }
        .meta { font-size: 12px; color: var(--secondary-text-color); }
        .stats { display: flex; gap: 8px; }
        .stat { display: flex; flex-direction: column; align-items: center; min-width: 58px; padding: 6px 8px;
                border-radius: 10px; background: var(--secondary-background-color); }
        .stat .v { font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.1; }
        .stat small { font-size: 11px; font-weight: 400; color: var(--secondary-text-color); margin-left: 1px; }
        .stat .l { font-size: 10px; text-transform: uppercase; letter-spacing: .06em; color: var(--secondary-text-color); }
        .stat { transition: background .3s; }
        .stat.ok { background: color-mix(in srgb, var(--ok) 14%, var(--secondary-background-color)); }
        .stat.ok .v { color: var(--ok); }
        .stat.warn { background: color-mix(in srgb, var(--slow) 22%, var(--secondary-background-color)); }
        .stat.warn .v, .stat.warn .l { color: var(--slow); }
        .stat.crit { background: var(--bad); }
        .stat.crit .v, .stat.crit .l, .stat.crit small { color: #fff; }
        .stat.poe { min-width: 92px; }
        .stat.poe .v { color: var(--pw); }
        .pbar { display: block; width: 100%; height: 4px; margin-top: 3px; border-radius: 2px; background: rgba(127,127,127,.25); overflow: hidden; }
        .pbar i { display: block; height: 100%; background: linear-gradient(90deg, #fbc02d, #fb8c00); }

        /* front panel */
        /* front panel palette: light by default, dark when the HA theme is dark */
        ha-card { --fp-bg: linear-gradient(#f7f8fa, #e6e8ec); --fp-edge: inset 0 1px 0 #fff, inset 0 -2px 0 rgba(0,0,0,.08), 0 0 0 1px var(--divider-color);
                  --fp-text: #3c4043; --fp-name: #1f2124; --fp-dim: #9aa0a6; --fp-sep: #c9ccd1; --fp-tag: rgba(0,0,0,.06);
                  --fp-hover: rgba(0,0,0,.04); --fp-sel: rgba(0,0,0,.05); --fp-jack: #2b2d31; --fp-jack-edge: #8d9299; --fp-jack-up: #5f646b;
                  --fp-led-off: #c9ccd1; --fp-panel: rgba(255,255,255,.7); --fp-down: #1565c0; --fp-upl: #6a1b9a; --fp-up: #2e7d32; --fp-slow: #b26a00; --fp-trunk: #1565c0; --fp-vlan: #8e24aa; }
        ha-card.dark { --fp-bg: linear-gradient(#45484e, #2c2e33 55%, #26282c); --fp-edge: inset 0 1px 0 rgba(255,255,255,.1), inset 0 -2px 0 rgba(0,0,0,.4);
                  --fp-text: #c9ccd1; --fp-name: #eceef1; --fp-dim: #6f737a; --fp-sep: #55585e; --fp-tag: rgba(255,255,255,.08);
                  --fp-hover: rgba(255,255,255,.05); --fp-sel: rgba(255,255,255,.08); --fp-jack: #101113; --fp-jack-edge: #5a5d63; --fp-jack-up: #6d7178;
                  --fp-led-off: #3a3c40; --fp-panel: rgba(0,0,0,.25); --fp-down: #64b5f6; --fp-upl: #ce93d8; --fp-up: #8fe08f; --fp-slow: #ffc95c; --fp-trunk: #64b5f6; --fp-vlan: #ce93d8; }
        .chassis-wrap { overflow-x: auto; border-radius: 12px; background: var(--fp-bg); box-shadow: var(--fp-edge); }
        .chassis-wrap { container-type: inline-size; margin-top: 10px; }
        .chassis { display: flex; align-items: stretch; gap: 14px; padding: 8px 10px; color: var(--fp-text); }
        .ports { display: flex; gap: 12px; margin: 0 auto; min-width: 0; }
        .side { position: relative; flex: 0 0 300px; border-radius: 10px; background: var(--fp-panel); box-shadow: inset 0 1px 3px rgba(0,0,0,.15); }
        .sidein { position: absolute; inset: 0; box-sizing: border-box; padding: 10px 12px; overflow: hidden;
                  display: flex; flex-direction: column; gap: 3px; }
        .rjgrid { display: grid; grid-template-columns: repeat(var(--cols), minmax(92px, 120px)); grid-template-rows: auto auto; gap: 4px 8px; }
        .sfpgrid { display: grid; grid-template-rows: auto auto; gap: 2px; padding-left: 8px; border-left: 1px solid var(--fp-sep); }
        .cell { display: flex; flex-direction: column; gap: 4px; padding: 5px 6px; border-radius: 8px; cursor: pointer;
                border: 1px solid transparent; transition: background .15s, border-color .15s; min-width: 0; }
        .cell.sfp { width: 76px; padding-left: 3px; padding-right: 3px; }
        .sfp .jackrow { gap: 4px; }
        .cell { position: relative; }
        .lbl { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
        .bot .lbl { flex-direction: column-reverse; }
        .nm { height: 16px; display: flex; align-items: center; min-width: 0; padding-right: 2px; }
        
        .nm span { font-size: 12.5px; line-height: 16px; font-weight: 600; color: var(--fp-name); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .nm.empty span { color: var(--fp-dim); font-weight: 400; }
        .t { font-size: 10.5px; font-weight: 700; letter-spacing: .02em; overflow: hidden; text-overflow: ellipsis; }
        .t.trunk { color: var(--fp-trunk); } .t.vlan { color: var(--fp-vlan); } .t.slowt { color: var(--fp-slow); }
        .t.off { color: #fff; background: var(--bad); padding: 0 4px; border-radius: 3px; line-height: 14px; }
                .rates { display: flex; justify-content: space-between; gap: 8px; width: 100%; height: 16px;
                 font-size: 12px; letter-spacing: -.01em; font-variant-numeric: tabular-nums; white-space: nowrap; }
        .rates .zero { opacity: .45; }
        .trk { --mdc-icon-size: 13px; color: var(--fp-trunk); flex: none; margin-right: 2px; }
        
        
        .dots { position: absolute; left: 4px; top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; gap: 2px; }
        .dots .vd { width: 6px; height: 6px; }
        .jspd { position: absolute; right: 3px; top: 1px; font-size: 9px; font-weight: 700; color: var(--slow); }
        .gl small { display: block; font-size: 10px; letter-spacing: 0; color: var(--pw); text-transform: none; }
        .vd { display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex: none; }
        .nv .jack, .nv .jack::before { border-color: var(--vc) !important; }
        .nv .jack { box-shadow: inset 0 2px 4px rgba(0,0,0,.8), 0 0 0 1px var(--vc); }
        .vlegend { display: flex; flex-wrap: wrap; gap: 3px 10px; margin-top: 6px; font-size: 11px; }
        .vlh { width: 100%; display: flex; justify-content: space-between; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--fp-dim); }
        .vlh span { text-transform: none; letter-spacing: 0; font-weight: 400; }
        .vlegend > span { display: flex; align-items: center; gap: 5px; white-space: nowrap; }
        .vsw { width: 10px; height: 10px; border-radius: 2px; background: var(--vc); flex: none; }
        .pvl { display: flex; align-items: center; gap: 4px; }
        .pvl b { font-weight: 600; margin-right: 6px; }
        .pvl .vd + b, .pvl .vd { margin-left: 0; }
        .cell:hover { background: var(--fp-hover); }
        .cell.sel { border-color: var(--primary-color); background: var(--fp-sel); }
        .jackrow { display: flex; align-items: center; gap: 5px; }
        .no { width: 17px; font-size: 12.5px; font-weight: 700; color: var(--fp-dim); text-align: right; font-variant-numeric: tabular-nums; }
        .up .no { color: var(--fp-up); } .slow .no { color: var(--fp-slow); }
        .jack { position: relative; flex: 1 1 64px; max-width: 84px; height: 28px; border-radius: 3px; background: var(--fp-jack); border: 1px solid var(--fp-jack-edge);
                box-shadow: inset 0 2px 4px rgba(0,0,0,.8); display: flex; align-items: center; justify-content: center; }
        .rj .jack::before { content: ''; position: absolute; left: 50%; width: 34%; height: 5px; transform: translateX(-50%);
                            background: var(--fp-jack); border: 1px solid var(--fp-jack-edge); }
        .rj.upr .jack::before { bottom: -6px; border-top: none; border-radius: 0 0 2px 2px; }
        .rj.bot .jack::before { top: -6px; border-bottom: none; border-radius: 2px 2px 0 0; }
        .sfp .jack { height: 16px; border-radius: 2px; }
        .up .jack, .slow .jack { border-color: var(--fp-jack-up); }
        .dis .jack { background: repeating-linear-gradient(45deg, var(--fp-jack) 0 5px, #2a1414 5px 10px); border-color: #7a3a3a; }
        .w { font-size: 12px; font-weight: 700; color: var(--pw); font-variant-numeric: tabular-nums; z-index: 1; }
        .jack .spin { --mdc-icon-size: 14px; color: #fff; position: absolute; right: 2px; }
        .leds { display: flex; flex-direction: column; gap: 4px; }
        .leds i { display: block; width: 9px; height: 6px; border-radius: 1.5px; background: var(--fp-led-off); }
        .up .l1 { background: #5f5; box-shadow: 0 0 6px #5f5; }
        .slow .l1 { background: #fb3; box-shadow: 0 0 6px #fb3; }
        .dis .l1 { background: #f44; box-shadow: 0 0 6px #f44; }
        .pw .l2 { background: #fb3; box-shadow: 0 0 6px #fb3; }
        .down:not(.sel) .lbl, .down:not(.sel) .jack { opacity: .65; }

        /* selection panel */
        .pick { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 500; color: var(--fp-name); }
        .pick ha-icon { --mdc-icon-size: 20px; color: var(--fp-dim); }
        .legend { display: grid; grid-template-columns: 1fr 1fr; gap: 3px 8px; margin-top: 6px; font-size: 11.5px; }
        .legend span { display: flex; align-items: center; gap: 8px; }
        .lg { width: 9px; height: 6px; border-radius: 1.5px; }
        .lg.g { background: #5f5; box-shadow: 0 0 5px #5f5; } .lg.a, .lg.a2 { background: #fb3; box-shadow: 0 0 5px #fb3; }
        .lg.r { background: #f44; box-shadow: 0 0 5px #f44; } .lg.a2 { margin-top: 0; outline: 1px dashed var(--fp-dim); outline-offset: 2px; }
        .ptitle { display: flex; align-items: center; gap: 8px; }
        .pname { flex: 1; min-width: 0; font-size: 15px; font-weight: 600; color: var(--fp-name); overflow-wrap: anywhere; }
        .dn { flex: none; min-width: 26px; height: 26px; border-radius: 7px; display: inline-flex; align-items: center; justify-content: center;
              background: var(--primary-color); color: var(--text-primary-color, #fff); font-size: 14px; font-weight: 700; }
        .x { flex: none; border: none; background: none; padding: 2px; cursor: pointer; color: var(--fp-dim); display: flex; }
        .x ha-icon { --mdc-icon-size: 18px; }
        .pmeta { font-size: 12px; color: var(--fp-text); }
        .pmeta.one { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .prate { display: flex; gap: 8px; white-space: nowrap; overflow: hidden; font-variant-numeric: tabular-nums; font-weight: 600; }
        .shield { --mdc-icon-size: 16px; color: var(--fp-dim); flex: none; }
        .dn-r { color: var(--fp-down); } .up-r { color: var(--fp-upl); }
        .bad { color: var(--bad); }
        .pacts { display: flex; flex-direction: column; gap: 5px; margin-top: auto; }
        .prow { display: flex; align-items: center; gap: 6px; }
        .gl { width: 34px; font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: var(--fp-dim); }
        .act { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 4px; height: 28px; padding: 0 10px;
               border-radius: 16px; border: 1px solid var(--divider-color); cursor: pointer; white-space: nowrap;
               background: var(--card-background-color); color: var(--primary-text-color); font: 600 12.5px/1 var(--ha-font-family-body, inherit); }
        .act ha-icon { --mdc-icon-size: 16px; }
        .act.danger { color: var(--bad); }
        .act.good { color: var(--ok); }
        .act.armed { color: #fff; background: var(--bad); border-color: var(--bad); }
        .act.busy { cursor: progress; }
        .act:disabled { opacity: .4; cursor: not-allowed; }
        .pnote { display: flex; gap: 6px; align-items: flex-start; font-size: 11px; color: var(--fp-dim); }
        .pnote ha-icon { --mdc-icon-size: 14px; flex: none; }
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .pinfo { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
        /* narrow card: panel goes under the ports, info left and buttons right */
        @container (max-width: 1180px) {
          .chassis { flex-direction: column; }
          .side { flex: 0 0 96px; }
          .sidein { flex-direction: row; align-items: center; gap: 16px; }
          .pinfo { flex: 1; }
          .pacts { margin-top: 0; flex: none; }
          .act { flex: none; width: 124px; }
          .legend { flex-direction: row; flex-wrap: wrap; column-gap: 16px; margin-top: 0; }
          .sidein:has(.pick) { flex-direction: row; flex-wrap: wrap; align-content: center; align-items: center; gap: 4px 20px; }
          .sidein:has(.pick) .pick { display: none; }
          .legend { display: flex; flex-wrap: wrap; gap: 3px 14px; margin-top: 0; }
          .vlegend { margin-top: 0; }
          .vlh { width: auto; gap: 8px; }
        }
      </style>
      <ha-card class="${this._hass.themes?.darkMode ? 'dark' : ''}">
        ${this._header(ports)}
        ${this._chassis(ports)}
      </ha-card>`;
    const wrap = this.shadowRoot.querySelector('.chassis-wrap');
    if (wrap) wrap.scrollLeft = scroll;
  }
}

// The integration loads this file as an extra frontend module, which can run before HA installs its scoped
// custom element registry; an element defined that early gets lost. So define it once the HA app element exists.
function defineEdgeSwitchCard() {
  if (customElements.get('edgeswitch-card')) return;
  customElements.define('edgeswitch-card', EdgeSwitchCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: 'edgeswitch-card', name: 'EdgeSwitch', description: 'EdgeSwitch front panel with port and PoE control', preview: true });
}
if (customElements.get('home-assistant')) defineEdgeSwitchCard();
else customElements.whenDefined('home-assistant').then(defineEdgeSwitchCard);

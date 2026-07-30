const STATUS_STYLE = {
  ok: { color: "var(--success-color, #43a047)", icon: "mdi:check-circle" },
  warning: { color: "var(--warning-color, #fb8c00)", icon: "mdi:alert" },
  critical: { color: "var(--error-color, #db4437)", icon: "mdi:alert-octagon" },
  data_issue: { color: "var(--disabled-text-color, #9e9e9e)", icon: "mdi:database-alert" },
  learning: { color: "var(--info-color, #039be5)", icon: "mdi:school" },
  waiting: { color: "var(--info-color, #039be5)", icon: "mdi:clock-outline" },
  unavailable: { color: "var(--disabled-text-color, #9e9e9e)", icon: "mdi:help-circle" },
  unknown: { color: "var(--disabled-text-color, #9e9e9e)", icon: "mdi:help-circle" },
};

const COPY = {
  es: {
    title: "Diagnóstico de coherencia energética",
    latest: "Última comparación",
    date: "Día comparado",
    official: "Lectura oficial",
    local: "Lectura local",
    difference: "Diferencia",
    coverage: "Cobertura local",
    officialHours: "Horas oficiales recibidas",
    pendingOfficialHours: "Horas oficiales pendientes",
    recent: "Comparaciones recientes",
    backLatest: "Volver al último día",
    selectDay: "Mostrar el detalle de este día",
    close: "Cerrar",
    ok: "Las comparaciones recientes están dentro de los márgenes configurados.",
    learning: "La integración todavía está reuniendo suficientes días válidos.",
    waiting: "Se está esperando una nueva lectura oficial completa.",
    data_issue: "Falta información fiable de una de las fuentes. Revisa el detalle inferior.",
    warning: "Hay diferencias relevantes repetidas entre las últimas comparaciones válidas.",
    critical: "Se han repetido diferencias muy grandes durante varios días.",
    localHigher: "El medidor local registra más que la fuente oficial. Comprueba la evolución de las próximas comparaciones y la configuración de ambas fuentes.",
    officialHigher: "La fuente oficial registra más que el medidor local. Comprueba la evolución de las próximas comparaciones y la cobertura del medidor.",
    equal: "Las dos lecturas prácticamente coinciden.",
    source_unavailable: "Una de las entidades de origen no está disponible.",
    invalid_official_value: "El valor o la fecha oficial no se pueden interpretar.",
    official_data_too_old: "Los datos oficiales llevan más retraso del permitido.",
    local_sensor_may_be_frozen: "El contador local lleva demasiado tiempo sin cambiar.",
    insufficient_local_coverage: "Faltan estadísticas locales para completar ese día.",
    waiting_for_local_statistics: "Recorder todavía no dispone de las estadísticas locales.",
    waiting_for_complete_official_day: "La fuente oficial todavía no ha publicado todas las horas del día.",
    invalid_local_value: "El valor local no es un número de energía válido.",
    cachedResult: "Se mantiene el último resultado verificado del {date} mientras las fuentes terminan de recuperarse.",
    validDays: "días válidos",
    noData: "Sin datos",
  },
  en: {
    title: "Energy consistency diagnosis",
    latest: "Latest comparison",
    date: "Compared day",
    official: "Official reading",
    local: "Local reading",
    difference: "Difference",
    coverage: "Local coverage",
    officialHours: "Official hours received",
    pendingOfficialHours: "Pending official hours",
    recent: "Recent comparisons",
    backLatest: "Back to latest day",
    selectDay: "Show this day's details",
    close: "Close",
    ok: "Recent comparisons are within the configured margins.",
    learning: "The integration is still collecting enough valid days.",
    waiting: "Waiting for a new complete official reading.",
    data_issue: "Reliable information is missing from one of the sources. Check the detail below.",
    warning: "Relevant differences have repeated across recent valid comparisons.",
    critical: "Very large differences have repeated for several days.",
    localHigher: "The local meter reads more than the official source. This is usually less concerning and may be caused by calibration, rounding, or day boundaries.",
    officialHigher: "The official reading is higher than the local meter. Watch the next comparisons and check local meter coverage.",
    equal: "Both readings are practically identical.",
    source_unavailable: "One of the source entities is unavailable.",
    invalid_official_value: "The official value or date cannot be interpreted.",
    official_data_too_old: "Official data is older than the configured limit.",
    local_sensor_may_be_frozen: "The local meter has not changed for too long.",
    insufficient_local_coverage: "Local statistics do not cover the complete day.",
    waiting_for_local_statistics: "Recorder does not have the local statistics yet.",
    waiting_for_complete_official_day: "The official source has not published every hour of the day yet.",
    invalid_local_value: "The local value is not a valid energy number.",
    cachedResult: "Keeping the last verified result from {date} while the sources finish recovering.",
    validDays: "valid days",
    noData: "No data",
  },
};

class EnergyConsistencyBadge extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._selectedComparisonDate = null;
  }

  static getConfigElement() {
    return document.createElement("energy-consistency-badge-editor");
  }

  static getStubConfig(hass, entities = [], entitiesFallback = []) {
    const candidates = [...entities, ...entitiesFallback];
    const entity = candidates.find((entityId) => {
      const stateObj = hass?.states?.[entityId];
      const options = stateObj?.attributes?.options || [];
      return entityId.startsWith("sensor.") && options.includes("ok") && options.includes("critical");
    });
    return { entity: entity || "" };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Select the Energy Consistency status entity");
    }
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._config || !this._hass) return;

    const stateObj = this._hass.states[this._config.entity];
    const status = stateObj?.state || "unavailable";
    const visual = STATUS_STYLE[status] || STATUS_STYLE.unknown;
    const formattedState = stateObj
      ? this._hass.formatEntityState?.(stateObj) || stateObj.state
      : this._hass.localize?.("state.default.unavailable") || "No disponible";
    const name = stateObj
      ? this._hass.formatEntityName?.(stateObj) || stateObj.attributes.friendly_name || this._config.entity
      : this._config.entity;
    const content = this._config.show_name ? `${name}: ${formattedState}` : formattedState;

    this._ensureStructure();
    const button = this.shadowRoot.querySelector(".badge");
    button.style.setProperty("--status-color", visual.color);
    button.setAttribute("aria-label", `${name}: ${formattedState}`);
    button.querySelector("ha-icon").setAttribute("icon", visual.icon);
    button.querySelector("span").textContent = content;

    const dialog = this.shadowRoot.querySelector("dialog");
    if (dialog.open) this._renderDiagnosis(stateObj, formattedState, visual);
  }

  _ensureStructure() {
    if (this._structureReady) return;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: inline-flex; vertical-align: middle; }
        .badge {
          box-sizing: border-box; display: inline-flex; align-items: center; gap: 7px;
          min-height: 36px; padding: 0 13px 0 10px; border: 1px solid var(--status-color);
          border-radius: 18px; color: var(--primary-text-color); font: inherit;
          font-size: 14px; font-weight: 500; line-height: 1; cursor: pointer; white-space: nowrap;
          background: var(--ha-card-background, var(--card-background-color));
          background: color-mix(in srgb, var(--status-color) 18%, var(--ha-card-background, var(--card-background-color)));
          transition: background-color 180ms ease, border-color 180ms ease;
        }
        .badge:hover { background: color-mix(in srgb, var(--status-color) 26%, var(--ha-card-background, var(--card-background-color))); }
        button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
        .badge ha-icon { color: var(--status-color); --mdc-icon-size: 20px; }
        dialog {
          box-sizing: border-box; width: min(560px, calc(100vw - 32px)); max-height: min(760px, calc(100vh - 32px));
          padding: 0; border: 1px solid var(--divider-color); border-radius: 20px;
          color: var(--primary-text-color); background: var(--ha-card-background, var(--card-background-color));
          box-shadow: var(--ha-card-box-shadow, 0 12px 40px rgba(0,0,0,.4)); font: inherit;
        }
        dialog::backdrop { background: rgba(0, 0, 0, .55); backdrop-filter: blur(2px); }
        .dialog-head { display: flex; align-items: center; gap: 12px; padding: 20px 20px 12px; }
        .dialog-head ha-icon { color: var(--dialog-color); --mdc-icon-size: 30px; }
        .dialog-head h2 { flex: 1; margin: 0; font-size: 21px; line-height: 1.25; }
        .icon-button { border: 0; border-radius: 50%; padding: 7px; color: var(--secondary-text-color); background: transparent; cursor: pointer; }
        .body { overflow: auto; padding: 4px 20px 20px; }
        .status { margin: 0 0 16px; padding: 12px 14px; border-left: 4px solid var(--dialog-color); border-radius: 8px; background: color-mix(in srgb, var(--dialog-color) 12%, transparent); }
        .direction { margin: 14px 0 18px; color: var(--secondary-text-color); line-height: 1.45; }
        h3 { margin: 20px 0 10px; font-size: 16px; }
        .metrics { display: grid; grid-template-columns: 1fr auto; gap: 9px 18px; }
        .metrics span:nth-child(odd) { color: var(--secondary-text-color); }
        .metrics span:nth-child(even) { text-align: right; font-weight: 500; }
        .history { display: grid; gap: 7px; }
        .history-row { width: 100%; display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: center; padding: 8px 10px; border: 1px solid transparent; border-radius: 9px; color: inherit; background: var(--secondary-background-color); font: inherit; text-align: left; cursor: pointer; transition: background-color 150ms ease, border-color 150ms ease; }
        .history-row:hover { background: color-mix(in srgb, var(--row-color) 10%, var(--secondary-background-color)); }
        .history-row.selected { border-color: var(--row-color); background: color-mix(in srgb, var(--row-color) 17%, var(--secondary-background-color)); }
        .history-row .delta { color: var(--secondary-text-color); }
        .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--row-color); }
        .footer { display: flex; justify-content: space-between; gap: 12px; padding: 12px 20px 18px; border-top: 1px solid var(--divider-color); }
        .back-latest { border: 1px solid var(--divider-color); border-radius: 18px; padding: 8px 14px; color: var(--primary-text-color); background: transparent; font: inherit; font-weight: 500; cursor: pointer; }
        .back-latest[hidden] { display: none; }
        .close { border: 0; border-radius: 18px; padding: 9px 18px; color: var(--text-primary-color, white); background: var(--primary-color); font: inherit; font-weight: 500; cursor: pointer; }
      </style>
      <button class="badge" type="button"><ha-icon></ha-icon><span></span></button>
      <dialog>
        <div class="dialog-head"><ha-icon></ha-icon><h2></h2><button class="icon-button" type="button" aria-label="Close"><ha-icon icon="mdi:close"></ha-icon></button></div>
        <div class="body"><p class="status"></p><div class="metrics"></div><p class="direction"></p><h3 class="recent-title"></h3><div class="history"></div></div>
        <div class="footer"><button class="back-latest" type="button" hidden></button><button class="close" type="button"></button></div>
      </dialog>
    `;
    const dialog = this.shadowRoot.querySelector("dialog");
    this.shadowRoot.querySelector(".badge").addEventListener("click", () => {
      this._selectedComparisonDate = null;
      const stateObj = this._hass.states[this._config.entity];
      const status = stateObj?.state || "unavailable";
      const visual = STATUS_STYLE[status] || STATUS_STYLE.unknown;
      const formatted = stateObj ? this._hass.formatEntityState?.(stateObj) || stateObj.state : "No disponible";
      this._renderDiagnosis(stateObj, formatted, visual);
      dialog.showModal();
    });
    this.shadowRoot.querySelector(".icon-button").addEventListener("click", () => dialog.close());
    this.shadowRoot.querySelector(".close").addEventListener("click", () => dialog.close());
    this.shadowRoot.querySelector(".back-latest").addEventListener("click", () => {
      this._selectedComparisonDate = null;
      const stateObj = this._hass.states[this._config.entity];
      const status = stateObj?.state || "unavailable";
      const visual = STATUS_STYLE[status] || STATUS_STYLE.unknown;
      const formatted = stateObj ? this._hass.formatEntityState?.(stateObj) || stateObj.state : "No disponible";
      this._renderDiagnosis(stateObj, formatted, visual);
    });
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => { this._selectedComparisonDate = null; });
    this._structureReady = true;
  }

  _renderDiagnosis(stateObj, formattedState, visual) {
    const lang = (this._hass.language || this._hass.locale?.language || "en").toLowerCase().startsWith("es") ? "es" : "en";
    const text = COPY[lang];
    const attrs = stateObj?.attributes || {};
    const recentComparisons = attrs.recent_comparisons || [];
    const selected = recentComparisons.find((row) => row.date === this._selectedComparisonDate);
    if (this._selectedComparisonDate && !selected) this._selectedComparisonDate = null;
    const detail = selected || attrs;
    const reasonKey = String(detail.reason || "").split(":")[0];
    const status = selected?.status || stateObj?.state || "data_issue";
    const difference = detail.difference_kwh == null ? null : Number(detail.difference_kwh);
    const detailVisual = STATUS_STYLE[status] || visual;
    const number = (value, digits = 2) => value == null || Number.isNaN(Number(value)) ? text.noData : new Intl.NumberFormat(lang, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(Number(value));
    const dialog = this.shadowRoot.querySelector("dialog");
    dialog.style.setProperty("--dialog-color", detailVisual.color);
    dialog.querySelector(".dialog-head > ha-icon").setAttribute("icon", detailVisual.icon);
    const displayState = selected
      ? this._hass.localize?.(`component.energy_consistency.entity.sensor.status.state.${status}`) || status
      : formattedState;
    dialog.querySelector("h2").textContent = `${text.title}: ${displayState}`;
    let statusMessage = text[reasonKey] || text[status] || detail.reason || text.data_issue;
    if (!selected && attrs.using_cached_result) {
      statusMessage += ` ${text.cachedResult.replace("{date}", detail.comparison_date || text.noData)}`;
    }
    dialog.querySelector(".status").textContent = statusMessage;

    const metrics = [
      [text.date, detail.date || detail.comparison_date || text.noData],
      [text.official, `${number(detail.official_kwh)} kWh`],
      [text.local, `${number(detail.local_kwh)} kWh`],
      [text.difference, `${difference > 0 ? "+" : ""}${number(detail.difference_kwh)} kWh (${difference > 0 ? "+" : ""}${number(detail.difference_percent, 1)} %)`],
      [text.coverage, `${number(detail.coverage_percent, 1)} %`],
    ];
    if (detail.official_hours != null && detail.expected_official_hours != null) {
      metrics.push([
        text.officialHours,
        `${number(detail.official_hours, 0)} / ${number(detail.expected_official_hours, 0)} h`,
      ]);
    }
    if (!selected && attrs.pending_official_hours != null && attrs.pending_expected_official_hours != null) {
      metrics.push([
        text.pendingOfficialHours,
        `${number(attrs.pending_official_hours, 0)} / ${number(attrs.pending_expected_official_hours, 0)} h`,
      ]);
    }
    const metricsElement = dialog.querySelector(".metrics");
    metricsElement.replaceChildren();
    for (const [label, value] of metrics) {
      const labelElement = document.createElement("span"); labelElement.textContent = label;
      const valueElement = document.createElement("span"); valueElement.textContent = value;
      metricsElement.append(labelElement, valueElement);
    }

    dialog.querySelector(".direction").textContent = detail.difference_kwh == null
      ? ""
      : Math.abs(difference) < 0.01
        ? text.equal
        : difference > 0 ? text.localHigher : text.officialHigher;
    dialog.querySelector(".recent-title").textContent = `${text.recent} · ${attrs.valid_days || 0} ${text.validDays}`;
    const history = dialog.querySelector(".history");
    history.replaceChildren();
    for (const row of recentComparisons.slice().reverse()) {
      const rowElement = document.createElement("button"); rowElement.type = "button";
      rowElement.className = `history-row${row.date === this._selectedComparisonDate ? " selected" : ""}`;
      const rowVisual = STATUS_STYLE[row.status] || STATUS_STYLE.unknown;
      rowElement.style.setProperty("--row-color", rowVisual.color);
      rowElement.setAttribute("aria-pressed", row.date === this._selectedComparisonDate ? "true" : "false");
      rowElement.setAttribute("aria-label", `${text.selectDay}: ${row.date}`);
      rowElement.addEventListener("click", () => {
        this._selectedComparisonDate = row.date;
        const currentState = this._hass.states[this._config.entity];
        const currentStatus = currentState?.state || "unavailable";
        const currentVisual = STATUS_STYLE[currentStatus] || STATUS_STYLE.unknown;
        const currentFormatted = currentState ? this._hass.formatEntityState?.(currentState) || currentState.state : "No disponible";
        this._renderDiagnosis(currentState, currentFormatted, currentVisual);
      });
      const dateElement = document.createElement("span"); dateElement.textContent = row.date;
      const deltaElement = document.createElement("span"); deltaElement.className = "delta";
      deltaElement.textContent = row.difference_kwh == null ? text.noData : `${row.difference_kwh > 0 ? "+" : ""}${number(row.difference_kwh)} kWh`;
      const dot = document.createElement("span"); dot.className = "dot"; dot.title = row.status;
      rowElement.append(dateElement, deltaElement, dot); history.append(rowElement);
    }
    const backLatest = dialog.querySelector(".back-latest");
    backLatest.textContent = text.backLatest;
    backLatest.hidden = !selected;
    dialog.querySelector(".close").textContent = text.close;
    dialog.querySelector(".icon-button").setAttribute("aria-label", text.close);
  }
}

class EnergyConsistencyBadgeEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    const spanish = this._hass.language?.toLowerCase().startsWith("es");
    if (!this._initialized) {
      this.innerHTML = `
        <style>
          .editor { display: grid; gap: 16px; padding: 8px 0; }
          label { display: flex; align-items: center; gap: 10px; }
        </style>
        <div class="editor">
          <ha-entity-picker></ha-entity-picker>
          <label><ha-switch></ha-switch><span></span></label>
        </div>
      `;
      this.querySelector("ha-entity-picker").addEventListener("value-changed", (event) => {
        if (!event.detail?.value) return;
        this._changed({ ...this._config, entity: event.detail.value });
      });
      this.querySelector("ha-switch").addEventListener("change", (event) => {
        this._changed({ ...this._config, show_name: event.target.checked });
      });
      this._initialized = true;
    }

    const picker = this.querySelector("ha-entity-picker");
    picker.hass = this._hass;
    picker.value = this._config.entity || "";
    picker.label = spanish ? "Entidad de estado" : "Status entity";
    picker.includeDomains = ["sensor"];
    const toggle = this.querySelector("ha-switch");
    toggle.checked = Boolean(this._config.show_name);
    this.querySelector("label span").textContent = spanish
      ? "Mostrar también el nombre"
      : "Also show the name";
  }

  _changed(config) {
    this._config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config },
        bubbles: true,
        composed: true,
      }),
    );
  }
}

if (!customElements.get("energy-consistency-badge")) {
  customElements.define("energy-consistency-badge", EnergyConsistencyBadge);
}
if (!customElements.get("energy-consistency-badge-editor")) {
  customElements.define("energy-consistency-badge-editor", EnergyConsistencyBadgeEditor);
}

window.customBadges = window.customBadges || [];
if (!window.customBadges.some((badge) => badge.type === "energy-consistency-badge")) {
  window.customBadges.push({
    type: "energy-consistency-badge",
    name: "Energy Consistency",
    preview: true,
    description: "Traffic-light badge for the daily energy comparison status.",
    documentationURL: "https://github.com/tecnoyfoto/energy_consistency",
  });
}

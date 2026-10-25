const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

class Element {
  constructor() { this.children = []; this.nodes = new Map(); this.style = { setProperty() {} }; }
  querySelector(key) { if (!this.nodes.has(key)) this.nodes.set(key, new Element()); return this.nodes.get(key); }
  replaceChildren() { this.children = []; }
  append(...nodes) { this.children.push(...nodes); }
  setAttribute() {}
  addEventListener() {}
  attachShadow() { this.shadowRoot = new Element(); }
}
function render(attrs, language = "en", state = "data_issue", selected = null) {
  const classes = new Map();
  const context = vm.createContext({ HTMLElement: Element, Intl,
    document: { createElement: () => new Element() }, window: {},
    customElements: { get: (key) => classes.get(key), define: (key, value) => classes.set(key, value) },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../../custom_components/energy_consistency/www/energy-consistency-badge.js"), "utf8"), context);
  const Badge = classes.get("energy-consistency-badge");
  const badge = new Badge(); badge._hass = { language }; badge._selectedComparisonDate = selected;
  badge._renderDiagnosis({ state, attributes: attrs }, state, { color: "grey", icon: "mdi:help" });
  return badge.shadowRoot.querySelector("dialog");
}

test("a stale meter-disagreement flag cannot hide an unavailable official source", () => {
  const dialog = render({ reason: "source_unavailable: official_energy", local_sources_disagree: true,
    comparison_date: "2026-10-17", source_entities: { official_energy: "sensor.official" },
    source_states: { official_energy: "unavailable" } });
  assert.match(dialog.querySelector(".status").textContent, /source entities is unavailable/);
  assert.match(dialog.querySelector(".status").textContent, /last saved comparison/);
  assert(dialog.querySelector(".metrics").children.some((node) => node.textContent === "sensor.official: unavailable"));
});
test("an excluded backup does not appear as an outage to fix", () => {
  const dialog = render({ reason: "source_unavailable: official_energy", backup_local_enabled: false,
    source_entities: { backup_local_energy: "sensor.backup" }, source_states: { backup_local_energy: "unavailable" } });
  assert(!dialog.querySelector(".metrics").children.some((node) => String(node.textContent).includes("sensor.backup")));
});
test("Spanish diagnostics include recovery instructions without broken encoding", () => {
  const dialog = render({ reason: "source_unavailable: official_energy" }, "es");
  assert.match(dialog.querySelector(".status").textContent, /Dispositivos y servicios/);
  assert(!dialog.querySelector("h2").textContent.includes("\u00c3"));
});
test("a historic day keeps its own disagreement explanation", () => {
  const dialog = render({ reason: "source_unavailable: official_energy", recent_comparisons: [
    { date: "2026-10-17", status: "ok", local_sources_disagree: true, difference_kwh: 0.1 }
  ] }, "en", "data_issue", "2026-10-17");
  assert.match(dialog.querySelector(".status").textContent, /local meters have complete data but disagree/);
});
test("configured labels are rendered as text", () => {
  const label = '<img src=x onerror="alert(1)">';
  const dialog = render({ local_source_name: label, local_source_role: "primary" }, "en", "ok");
  assert(dialog.querySelector(".metrics").children.some((node) => node.textContent === label));
});

"use strict";
(() => {
const SVGNS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const LAYERS = [
  { key: "coverage", label: "Loaded map coverage (saved extract)", stroke: "#4a6a8a", width: 2, dash: "10 5" },
  { key: "context", label: "Mapped walking network", stroke: "#b4bcc4", width: 1.5, dash: "" },
  { key: "inactive", label: "Project sections not active on this date", stroke: "#e5a9a9", width: 3, dash: "3 3" },
  { key: "baseline", label: "Baseline route (no closures)", stroke: "#1d6fd1", width: 9, dash: "", opacity: 0.55 },
  { key: "closure", label: "Active closures", stroke: "#d02323", width: 8, dash: "" },
  { key: "route", label: "Route under active closures", stroke: "#e07b00", width: 5.5, dash: "11 6" },
  { key: "opt1", label: "Mitigation option 1 (AI-selected)", stroke: "#7b3fc4", width: 4, dash: "1 6", cap: "round" },
  { key: "opt2", label: "Mitigation option 2 (AI-selected)", stroke: "#00838f", width: 3, dash: "12 5 2 5" },
  { key: "markers", label: "Start and destination", stroke: "#1c2530", width: 2, dash: "" },
];
const st = {
  index: null, caseId: null, data: null, projects: [], nextProject: 1,
  journeyId: null, assessment: null, compare: null,
  assessStale: false, compareStale: false, busy: false, seq: 0, timer: null,
  layers: Object.fromEntries(LAYERS.map((l) => [l.key, true])),
  view: null, bounds: null, proj: null, pendingCompare: false,
  custom: { origin: null, destination: null }, customInfo: null, pick: null, customSeq: 0,
  demoBusy: false, bus: null,
};
const CUSTOM = "custom";
const isCustom = () => st.journeyId === CUSTOM;
const allSections = () => st.data.sections.concat(st.customInfo ? st.customInfo.sections : []);

function el(tag, attrs, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v; else node.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return node;
}
function svg(tag, attrs) {
  const node = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  return node;
}
const metres = (n) => (n === null || n === undefined ? "unreachable" : `${n} m`);
const signed = (n) => (n === null || n === undefined ? "n/a" : n === 0 ? "no change" : `${n > 0 ? "+" : "−"}${Math.abs(n)} m`);
const journeyLabel = (id) => (id === CUSTOM ? "Your journey" : (st.data.journeys.find((j) => j.id === id) || { label: id }).label);

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  let response;
  try { response = await fetch(path, options); } catch (e) { throw new Error("The local workspace server is not reachable."); }
  let data = null;
  try { data = await response.json(); } catch (e) { /* handled below */ }
  if (!response.ok) throw new Error((data && data.error) || `Request failed (${response.status})`);
  return data;
}

/* ---------- payload and form ---------- */
function payload(withQuestion) {
  const body = {
    case_id: st.caseId,
    assessment_date: $("assess-date").value,
    projects: st.projects.map((p) => ({
      name: p.name.trim(), start_date: p.start, end_date: p.end,
      sections: [...p.sections], hypothetical: true,
    })),
  };
  if (withQuestion) body.question = $("question").value.trim();
  if (st.custom.origin && st.custom.destination) {
    const [olat, olon] = st.custom.origin, [dlat, dlon] = st.custom.destination;
    body.custom_journey = { origin: { lat: olat, lon: olon }, destination: { lat: dlat, lon: dlon } };
  }
  return body;
}
function showError(message) {
  const box = $("form-error");
  box.hidden = !message;
  box.textContent = message || "";
}
function setBusy(message) {
  st.busy = Boolean(message);
  const busy = $("busy");
  busy.hidden = !message;
  busy.textContent = message || "";
  $("plan-fields").disabled = st.busy || st.demoBusy;
}

function defaultProjects() {
  const today = st.index.today;
  const sections = st.data.sections;
  const first = sections.find((s) => s.verified) || sections[0];
  st.projects = [{ uid: st.nextProject++, name: "Hypothetical roadworks A", start: today, end: today, sections: new Set([first.id]) }];
}

function renderProjects() {
  const host = $("projects");
  host.replaceChildren();
  st.projects.forEach((p, i) => {
    const sec = (cls, s) => el("label", { class: "check" },
      el("input", { type: "checkbox", "data-uid": p.uid, "data-section": s.id, checked: p.sections.has(s.id) }),
      el("span", {}, `${s.label} (${s.metres} m)`));
    const verified = st.data.sections.filter((s) => s.verified);
    const others = st.data.sections.filter((s) => !s.verified);
    const mine = st.customInfo ? st.customInfo.sections : [];
    host.append(el("fieldset", { class: "project" },
      el("legend", { class: "tag" }, "Hypothetical"),
      el("div", { class: "project-head" },
        el("h3", {}, `Project ${i + 1}`),
        st.projects.length > 1 ? el("button", { type: "button", class: "btn btn-small", "data-remove": p.uid, "aria-label": `Remove project ${i + 1}` }, "Remove") : null),
      el("label", { for: `pname-${p.uid}` }, "Project name"),
      el("input", { type: "text", id: `pname-${p.uid}`, value: p.name, maxlength: 60, "data-uid": p.uid, "data-field": "name" }),
      el("div", { class: "date-pair" },
        el("div", {}, el("label", { for: `pstart-${p.uid}` }, "Start date"),
          el("input", { type: "date", id: `pstart-${p.uid}`, value: p.start, "data-uid": p.uid, "data-field": "start" })),
        el("div", {}, el("label", { for: `pend-${p.uid}` }, "End date"),
          el("input", { type: "date", id: `pend-${p.uid}`, value: p.end, "data-uid": p.uid, "data-field": "end" }))),
      el("div", { class: "sections" },
        el("strong", {}, "Closed walking sections"),
        verified.map((s) => sec("v", s)),
        mine.length ? el("div", {}, el("strong", { class: "hint" }, "Sections on your journey's route"), mine.map((s) => sec("c", s))) : null,
        others.length ? el("details", {}, el("summary", {}, `Other route sections (${others.length}, hypothetical)`),
          el("div", {}, others.map((s) => sec("o", s)))) : null)));
  });
}

function onProjectInput(event) {
  const t = event.target;
  const project = st.projects.find((p) => String(p.uid) === t.getAttribute("data-uid"));
  if (!project) return;
  if (t.dataset.field === "name") project.name = t.value;
  else if (t.dataset.field === "start") project.start = t.value;
  else if (t.dataset.field === "end") project.end = t.value;
  else if (t.dataset.section) {
    if (t.checked) project.sections.add(t.dataset.section); else project.sections.delete(t.dataset.section);
  }
  inputsChanged();
}

/* ---------- stale handling: Python owns the fingerprint ---------- */
function applyStale() {
  if (st.bus) {
    $("map-stale").hidden = true;
    $("map-frame").classList.remove("stale");
    $("map-freshness").className = "chip " + (st.bus.result ? "chip-fresh" : "chip-idle");
    $("map-freshness").textContent = st.bus.result ? "Results current" : "No results yet";
    renderResults();
    return;
  }
  const anyResult = Boolean(st.assessment || st.compare);
  const staleAny = st.assessStale || (st.compareStale && $("demo-controls").hidden);
  $("map-stale").hidden = !staleAny;
  $("map-frame").classList.toggle("stale", staleAny);
  const chip = $("map-freshness");
  chip.className = "chip " + (!anyResult ? "chip-idle" : staleAny ? "chip-stale" : "chip-fresh");
  chip.textContent = !anyResult ? "No results yet" : staleAny ? "Outdated · recalculate" : "Results current";
  renderResults();
}
function inputsChanged() {
  $("demo-controls").hidden = true;
  showError("");
  if (st.assessment) st.assessStale = true;
  if (st.compare) st.compareStale = true;
  applyStale();
  clearTimeout(st.timer);
  st.timer = setTimeout(checkFingerprint, 150);
}
async function checkFingerprint() {
  if (!st.assessment && !st.compare) return;
  const seq = ++st.seq;
  let result;
  try { result = await api("/api/fingerprint", payload(true)); } catch (e) { return; }
  if (seq !== st.seq) return;
  st.assessStale = Boolean(st.assessment) && !(result.valid && result.assessment_fingerprint === st.assessment.fingerprint);
  st.compareStale = Boolean(st.compare) && !(result.valid && result.comparison_fingerprint === st.compare.fingerprint);
  applyStale();
  drawMap();
}

/* ---------- actions ---------- */
async function assess() {
  showError("");
  setBusy("Calculating the project assessment locally…");
  try {
    const result = await api("/api/assess", payload(false));
    st.assessment = result;
    st.assessStale = false;
    if (st.compare && st.compare.assessment.fingerprint !== result.fingerprint) st.compareStale = true;
    st.seq++;
    $("assess-btn").textContent = "Assess projects";
  } catch (e) {
    showError(e.message);
  } finally {
    setBusy("");
    applyStale(); drawMap(); renderEvidence();
    if (!$("demo-controls").hidden) {
      const row = !st.assessStale && st.assessment && st.assessment.custom_journey && st.assessment.custom_journey.row;
      $("demo-distance").textContent = row
        ? `Walking distance: ${metres(row.metres)} (baseline ${metres(row.baseline_metres)})`
        : "Demo route could not be calculated; see the error below.";
    }
  }
}
async function compareWithAi() {
  showError("");
  const body = payload(true);
  if (!body.question) { showError("Write a question first, for example: which two connections would best restore access?"); $("question").focus(); return; }
  setBusy("Asking the local model (one request, up to 30 seconds). The deterministic assessment is recalculated first…");
  st.pendingCompare = true; renderResults();
  try {
    const result = await api("/api/compare", body);
    st.compare = result;
    st.compareStale = false;
    st.assessment = result.assessment;
    st.assessStale = false;
    st.seq++;
  } catch (e) {
    showError(e.message);
  } finally {
    st.pendingCompare = false;
    setBusy("");
    applyStale(); drawMap(); renderEvidence(); renderDiagnostics();
  }
}

/* ---------- map ---------- */
function buildProjection() {
  const nodes = st.data.nodes;
  const ids = Object.keys(nodes);
  let lat0 = 0, lon0 = 0;
  for (const id of ids) { lat0 += nodes[id][0]; lon0 += nodes[id][1]; }
  lat0 /= ids.length; lon0 /= ids.length;
  const kx = Math.cos((lat0 * Math.PI) / 180) * 111320, ky = 110540;
  st.proj = (lat, lon) => [(lon - lon0) * kx, -(lat - lat0) * ky];
  st.unproj = (x, y) => [lat0 - y / ky, lon0 + x / kx];
  st.xy = {};
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  for (const id of ids) {
    const p = st.proj(nodes[id][0], nodes[id][1]);
    st.xy[id] = p;
    minx = Math.min(minx, p[0]); maxx = Math.max(maxx, p[0]); miny = Math.min(miny, p[1]); maxy = Math.max(maxy, p[1]);
  }
  st.bounds = { x: minx, y: miny, w: maxx - minx, h: maxy - miny };
  st.linkIndex = Object.fromEntries(st.data.links.map((l) => [l[0], l]));
}
function fitBox(box, pad) {
  const w = Math.max(box.w, 60) * (1 + pad), h = Math.max(box.h, 60) * (1 + pad);
  st.view = { x: box.x + box.w / 2 - w / 2, y: box.y + box.h / 2 - h / 2, w, h };
  const frame = $("map-frame").getBoundingClientRect();
  const aspect = frame.width / Math.max(frame.height, 1);
  if (w / h < aspect) { const nw = h * aspect; st.view.x -= (nw - w) / 2; st.view.w = nw; }
  else { const nh = w / aspect; st.view.y -= (nh - h) / 2; st.view.h = nh; }
  applyView();
}
function journeyBox() {
  if (st.bus) {
    const scenario = st.bus.scenario, result = st.bus.result;
    const ids = new Set([scenario.origin.node_id, busStop(scenario.usual_stop_id).node_id,
      busStop($("bus-destination").value).node_id]);
    if (result && result.skipped.stop_id) ids.add(busStop(result.skipped.stop_id).node_id);
    for (const route of result ? [result.normal, result.skipped] : []) route.path.forEach((id) => ids.add(id));
    const pts = [...ids].map((id) => st.xy[id]).filter(Boolean);
    for (const id of [scenario.usual_stop_id, $("bus-destination").value, result && result.skipped.stop_id].filter(Boolean)) {
      pts.push(st.proj(...busStop(id).coordinates));
    }
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x = Math.min(...xs), y = Math.min(...ys);
    return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
  }
  if (isCustom()) {
    const pts = [];
    for (const key of ["origin", "destination"]) {
      const info = st.customInfo && st.customInfo[key], raw = st.custom[key];
      if (raw) pts.push(st.proj(raw[0], raw[1]));
      if (info && info.snapped) pts.push(st.proj(info.snapped[0], info.snapped[1]));
    }
    const row = selectedRow();
    for (const p of [row && row.baseline_path, row && row.path]) pathPoints(p || []).forEach((q) => pts.push(q));
    if (!pts.length) return st.bounds;
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x = Math.min(...xs), y = Math.min(...ys);
    return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
  }
  const j = st.data.journeys.find((x) => x.id === st.journeyId);
  const ids = new Set([j.origin.id, j.destination.id]);
  const row = st.assessment && st.assessment.journeys.find((r) => r.journey_id === j.id);
  for (const p of [row && row.baseline_path, row && row.path]) (p || []).forEach((n) => ids.add(n));
  const pts = [...ids].map((n) => st.xy[n]).filter(Boolean);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x = Math.min(...xs), y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}
function applyView() {
  const v = st.view;
  $("map").setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`);
}
function zoom(factor) {
  const v = st.view, cx = v.x + v.w / 2, cy = v.y + v.h / 2;
  v.w /= factor; v.h /= factor; v.x = cx - v.w / 2; v.y = cy - v.h / 2;
  applyView();
}
function pan(dx, dy) { st.view.x += dx * st.view.w; st.view.y += dy * st.view.h; applyView(); }

function polyline(points, layer, extra) {
  const node = svg("polyline", {
    points: points.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" "),
    fill: "none", stroke: layer.stroke, "stroke-width": layer.width,
    "stroke-linecap": layer.cap || "butt", "stroke-linejoin": "round",
    "vector-effect": "non-scaling-stroke",
  });
  if (layer.dash) node.setAttribute("stroke-dasharray", layer.dash);
  if (layer.opacity) node.setAttribute("stroke-opacity", layer.opacity);
  return node;
}
const L = (key) => LAYERS.find((l) => l.key === key);
function pathPoints(ids) { return ids.map((n) => st.xy[n]).filter(Boolean); }
function linkSegments(linkIds) {
  return linkIds.map((id) => st.linkIndex[id]).filter(Boolean).map((l) => [st.xy[l[1]], st.xy[l[2]]]);
}
function addMarker(markers, p, text, fill, ring, side) {
  markers.append(svg("circle", { cx: p[0], cy: p[1], r: 7, fill: ring ? "#fff" : fill, stroke: ring ? fill : "#fff", "stroke-width": ring ? 3 : 2, "vector-effect": "non-scaling-stroke" }));
  const t = svg("text", { x: p[0] + (side === "left" ? -9 : side === "right" ? 9 : 0),
    y: p[1] - (side ? 2 : 12), class: side ? "bus-map-label" : "map-label", fill,
    "text-anchor": side === "left" ? "end" : side === "right" ? "start" : "middle" });
  t.textContent = text;
  markers.append(t);
}
function busStop(id) { return st.bus.scenario.stops.find((stop) => stop.id === id); }
function drawBusMap(group) {
  const scenario = st.bus.scenario, result = st.bus.result;
  group("inactive"); group("closure"); group("opt1"); group("opt2");
  const baseline = group("baseline"), route = group("route");
  if (result && result.normal.path.length) baseline.append(polyline(pathPoints(result.normal.path), L("baseline")));
  const selected = result && result[st.bus.mode];
  if (selected && selected.path.length) route.append(polyline(pathPoints(selected.path), L("route")));
  const markers = group("markers");
  const marker = (id, label, colour, ring, side) => addMarker(markers, st.proj(...busStop(id).coordinates), label, colour, ring, side);
  addMarker(markers, st.xy[scenario.origin.node_id], scenario.origin.label, "#14633a", false, "right");
  marker(scenario.usual_stop_id, "Usual: " + busStop(scenario.usual_stop_id).name,
    st.bus.mode === "skipped" ? "#d02323" : "#1d6fd1", st.bus.mode === "skipped", "left");
  if (result && result.skipped.stop_id) marker(result.skipped.stop_id,
    "Alternative: " + busStop(result.skipped.stop_id).name, "#8a4b00", false, "left");
  const destination = $("bus-destination").value;
  marker(destination, "Destination: " + busStop(destination).name, "#1c2530", true, "right");
  renderLegend();
  const description = st.bus.mode === "normal" ? "normal service" : "hypothetical skipped stop";
  $("map-caption").textContent = `${scenario.service} · ${scenario.direction} · ${description}. ${scenario.synthetic ? "Synthetic trip" : "Published dated trip; hypothetical change"}; walking distance only.`;
  $("map").setAttribute("aria-label", `${scenario.synthetic ? "Synthetic" : "Published"} bus access map: ${scenario.service}, ${scenario.direction}`);
}
function selectedRow() {
  if (!st.assessment) return null;
  if (isCustom()) return (!st.assessStale && st.assessment.custom_journey && st.assessment.custom_journey.row) || null;
  return st.assessment.journeys.find((r) => r.journey_id === st.journeyId);
}
function selectedOptions() {
  if (isCustom() || !st.compare || st.compare.state !== "success") return [];
  return st.compare.options.map((o) => ({ option: o, row: o.journeys.find((r) => r.journey_id === st.journeyId) }));
}

function drawMap() {
  const map = $("map");
  map.replaceChildren();
  if (!st.data) return;
  const row = selectedRow();
  const group = (key) => { const g = svg("g", { "data-layer": key }); if (st.layers[key]) map.append(g); return g; };

  const cov = st.data.coverage, covA = st.proj(cov.maxlat, cov.minlon), covB = st.proj(cov.minlat, cov.maxlon);
  group("coverage").append(svg("rect", {
    x: covA[0], y: covA[1], width: covB[0] - covA[0], height: covB[1] - covA[1], fill: "none",
    stroke: L("coverage").stroke, "stroke-width": L("coverage").width, "stroke-dasharray": L("coverage").dash,
    "vector-effect": "non-scaling-stroke",
  }));

  const ctx = group("context");
  for (const l of st.data.links) { const a = st.xy[l[1]], b = st.xy[l[2]]; if (a && b) ctx.append(polyline([a, b], L("context"))); }
  if (st.bus) { drawBusMap(group); return; }

  const inactive = group("inactive");
  const activeNames = new Set(st.assessment ? st.assessment.active_projects.map((p) => p.label) : []);
  const inactiveIds = new Set();
  for (const p of st.projects) {
    if (activeNames.has(p.name.trim())) continue;
    for (const sid of p.sections) { const s = allSections().find((x) => x.id === sid); if (s) s.link_ids.forEach((id) => inactiveIds.add(id)); }
  }
  for (const seg of linkSegments([...inactiveIds])) inactive.append(polyline(seg, L("inactive")));

  if (row) {
    const base = group("baseline");
    base.append(polyline(pathPoints(row.baseline_path), L("baseline")));
    const rt = group("route");
    if (row.path.length) rt.append(polyline(pathPoints(row.path), L("route")));
  } else { group("baseline"); group("route"); }

  const opts = selectedOptions();
  opts.forEach(({ option, row: r }, i) => {
    const g = group(i === 0 ? "opt1" : "opt2");
    if (r && r.path.length) g.append(polyline(pathPoints(r.path), L(i === 0 ? "opt1" : "opt2")));
    const geo = option.candidate.geometry.map((p) => st.proj(p[0], p[1]));
    const line = polyline(geo, { stroke: L(i === 0 ? "opt1" : "opt2").stroke, width: 2.5, dash: "" });
    line.setAttribute("stroke-opacity", "0.9");
    g.append(line);
    const mid = geo[Math.floor(geo.length / 2)];
    const tag = svg("text", { x: mid[0], y: mid[1] - 6, class: "map-label", fill: L(i === 0 ? "opt1" : "opt2").stroke, "text-anchor": "middle" });
    tag.textContent = `Option ${i + 1}`;
    g.append(tag);
  });
  const closure = group("closure");
  if (st.assessment) for (const seg of linkSegments(st.assessment.closed_link_ids)) closure.append(polyline(seg, L("closure")));

  const markers = group("markers");
  if (isCustom()) {
    for (const [key, name, fill] of [["origin", "Start", "#14633a"], ["destination", "Destination", "#1c2530"]]) {
      const raw = st.custom[key];
      if (!raw) continue;
      const info = st.customInfo && st.customInfo[key];
      const requested = st.proj(raw[0], raw[1]);
      if (info && info.status === "outside_coverage") {
        addMarker(markers, requested, `${name}: outside loaded map coverage`, "#0b3d75", true);
      } else {
        if (info && info.snapped) {
          const s = st.proj(info.snapped[0], info.snapped[1]);
          markers.append(svg("line", { x1: requested[0], y1: requested[1], x2: s[0], y2: s[1], stroke: fill, "stroke-width": 2, "stroke-dasharray": "3 3", "vector-effect": "non-scaling-stroke" }));
          addMarker(markers, s, info.snap_metres > 3 ? `${name} (nearest mapped node)` : name, fill, false);
        } else {
          addMarker(markers, requested, name, fill, false);
        }
        if (info && info.snapped && info.snap_metres > 3) {
          markers.append(svg("circle", { cx: requested[0], cy: requested[1], r: 4, fill: "#fff", stroke: fill, "stroke-width": 2, "vector-effect": "non-scaling-stroke" }));
        }
      }
    }
  } else {
    const j = st.data.journeys.find((x) => x.id === st.journeyId);
    for (const [pt, text, fill] of [[j.origin, `Start: ${j.origin.label}`, "#14633a"], [j.destination, `Destination: ${j.destination.label}`, "#1c2530"]]) {
      addMarker(markers, st.xy[pt.id] || st.proj(pt.coordinates[0], pt.coordinates[1]), text, fill, false);
    }
  }
  renderLegend();
  const sizeNote = st.assessment ? ` · assessed for ${st.assessment.assessment_date}` : " · not assessed yet";
  const demo = $("demo-controls").hidden ? "" : "Hypothetical demo · ";
  const demoDistance = demo && row ? ` · ${metres(row.metres)}` : "";
  $("map-caption").textContent = `${demo}${journeyLabel(st.journeyId)}${demoDistance}${sizeNote}. Walking network only.`;
  $("map").setAttribute("aria-label", `Map of ${journeyLabel(st.journeyId)}`);
}

function renderLegend() {
  const host = $("layer-list");
  const has = {
    coverage: true, context: true, inactive: st.projects.length > 0, baseline: Boolean(st.assessment), route: Boolean(st.assessment),
    closure: Boolean(st.assessment), opt1: selectedOptions().length > 0, opt2: selectedOptions().length > 1, markers: true,
  };
  if (st.bus) {
    has.inactive = false; has.closure = false; has.opt1 = false; has.opt2 = false;
    has.baseline = Boolean(st.bus.result); has.route = Boolean(st.bus.result);
  }
  const existing = host.children.length === LAYERS.length;
  LAYERS.forEach((layer, i) => {
    let item = existing ? host.children[i] : null;
    if (!item) {
      const box = el("input", { type: "checkbox", id: `layer-${layer.key}`, checked: st.layers[layer.key], "data-layer": layer.key });
      const sw = svg("svg", { width: 34, height: 12, viewBox: "0 0 34 12", "aria-hidden": "true" });
      const line = svg("line", { x1: 2, y1: 6, x2: 32, y2: 6, stroke: layer.stroke, "stroke-width": Math.min(layer.width, 8),
        "stroke-linecap": layer.cap || "butt" });
      if (layer.dash) line.setAttribute("stroke-dasharray", layer.dash);
      if (layer.opacity) line.setAttribute("stroke-opacity", layer.opacity);
      sw.append(line);
      item = el("label", { class: "layer-item", for: `layer-${layer.key}` }, box, el("span", { class: "swatch" }, sw), el("span", {}, layer.label));
      host.append(item);
    }
    item.classList.toggle("disabled", !has[layer.key]);
    item.lastElementChild.textContent = st.bus && layer.key === "baseline" ? "Walking to usual stop"
      : st.bus && layer.key === "route" ? "Selected walking route" : layer.label;
    item.querySelector("input").title = has[layer.key] ? "" : "No data for this layer yet";
  });
}

/* ---------- result cards ---------- */
function pill(text, cls) { return el("span", { class: `pill ${cls || ""}` }, text); }
function staleNote() { return el("p", { class: "alert", role: "status" }, "Outdated: dates, projects or question changed. Recalculate to refresh this card."); }

function assessmentCard() {
  const a = st.assessment;
  if (!a) {
    return el("article", { class: "card" }, el("h3", {}, "Project assessment"),
      el("p", { class: "hint" }, "Choose a date and projects, then select “Assess projects”. This runs locally and does not need Ollama."));
  }
  const names = Object.fromEntries(a.active_projects.concat(a.inactive_projects).map((p) => [p.id, p.label]));
  const rows = a.journeys.map((r) => el("tr", { class: r.journey_id === st.journeyId ? "selected" : null },
    el("td", {}, journeyLabel(r.journey_id), r.journey_id === st.journeyId ? " ◂" : ""),
    el("td", { class: "num" }, metres(r.baseline_metres)),
    el("td", { class: "num" }, metres(r.metres)),
    el("td", {}, r.status === "unreachable" ? pill("Unreachable", "pill-bad") : r.status === "longer" ? pill(signed(r.change_metres), "pill-warn") : pill("Unchanged", "pill-ok")),
    el("td", {}, r.contributing_projects.length ? r.contributing_projects.map((id) => names[id] || id).join(", ") : "None",
      r.overlap_effect ? el("div", {}, pill("Overlap makes it worse", "pill-bad")) : null,
      Object.keys(r.individual).length > 1 ? el("div", { class: "hint" }, "Alone: " + Object.entries(r.individual).map(([id, v]) => `${names[id] || id} ${v.metres === null ? "unreachable" : signed(v.change_metres)}`).join("; ")) : null)));
  return el("article", { class: "card " + (st.assessStale ? "stale" : "ok") },
    el("div", { class: "card-title" }, el("h3", {}, `Project assessment for ${a.assessment_date}`),
      el("span", {}, a.hypothetical ? pill("Hypothetical", "pill-hyp") : null, " ", pill(st.assessStale ? "Outdated" : "Current", st.assessStale ? "pill-warn" : "pill-ok"))),
    st.assessStale ? staleNote() : null,
    el("p", {}, a.active_projects.length
      ? `Active (${a.active_projects.length}): ${a.active_projects.map((p) => `${p.label} (${p.start_date} to ${p.end_date})`).join("; ")}.`
      : "No project is active on this date, so the routes equal the baseline."),
    a.inactive_projects.length ? el("p", { class: "hint" }, `Not active: ${a.inactive_projects.map((p) => `${p.label} (${p.start_date} to ${p.end_date})`).join("; ")}.`) : null,
    el("p", { class: "hint" }, `${a.closed_link_ids.length} walking link(s) closed together. ${a.date_rule}`),
    el("table", {}, el("thead", {}, el("tr", {}, ["Journey", "Baseline", "With closures", "Effect", "Caused by"].map((h) => el("th", { scope: "col" }, h)))), el("tbody", {}, rows)),
    el("p", { class: "hint" }, "Walking only. Calculated by Python from the saved map; not an official closure plan."));
}

function savedText(row) {
  if (row.access_restored) return "Restores access (closure-only route was unreachable)";
  if (row.change_vs_closure === null || row.change_vs_closure === undefined) return "n/a (still unreachable)";
  return row.change_vs_closure < 0 ? `${-row.change_vs_closure} m saved` : row.change_vs_closure === 0 ? "0 m saved" : `${row.change_vs_closure} m longer`;
}
function addedText(row) {
  if (row.change_vs_baseline === null || row.change_vs_baseline === undefined) return "n/a (unreachable)";
  return row.change_vs_baseline > 0 ? `${row.change_vs_baseline} m added` : row.change_vs_baseline === 0 ? "0 m added" : `${-row.change_vs_baseline} m shorter`;
}
function stat(label, value) { return el("div", { class: "stat" }, el("span", { class: "stat-value" }, value), el("span", { class: "stat-label" }, label)); }

function optionBlock(entry, i) {
  const { option, row } = entry;
  const c = option.candidate;
  return el("section", { class: `option slot${i + 1}` },
    el("h4", {}, `Option ${i + 1}: ${c.label}`),
    row ? el("div", { class: "stats" },
      stat("Total walking distance", metres(row.metres)),
      stat("Saved versus closure only", savedText(row)),
      stat("Added versus baseline", addedText(row))) : null,
    row ? el("p", { class: "hint" }, `Baseline ${metres(row.baseline_metres)} · closure only ${metres(row.closure_metres)}. Calculated by Python.`) : null,
    el("p", { class: "assumption" }, el("strong", {}, "Assumption: "), `${c.assumption} Allowance ${c.metres} m. `, el("strong", {}, "Site check: "), c.site_check),
    el("p", { class: "unverified" }, el("strong", {}, "Unverified: "), "safety, accessibility and construction feasibility have not been assessed."),
    el("details", {}, el("summary", {}, "All journeys for this option"),
      el("table", {}, el("tbody", {}, option.journeys.map((r) => el("tr", {}, el("td", {}, journeyLabel(r.journey_id)), el("td", { class: "num" }, metres(r.metres)), el("td", {}, savedText(r) + "; " + addedText(r))))))));
}

function aiCard() {
  const c = st.compare;
  if (st.busy && st.pendingCompare) return el("article", { class: "card" }, el("h3", {}, "AI mitigation options"), el("p", {}, "Waiting for the local model…"));
  if (!c) {
    return el("article", { class: "card" }, el("h3", {}, "AI mitigation options"),
      el("p", { class: "hint" }, "Optional. Write a question and select “Compare options with AI”. Candidate routes and lengths are always calculated by Python; the model only picks from the saved candidates."));
  }
  const stale = st.compareStale;
  const head = (label, cls) => el("div", { class: "card-title" }, el("h3", {}, "AI mitigation options"), el("span", {}, pill(label, cls), " ", pill(stale ? "Outdated" : "Current", stale ? "pill-warn" : "pill-ok")));
  const q = el("p", { class: "hint" }, `Question: “${c.question}”`);
  if (c.state === "failure" || c.state === "failed") {
    return el("article", { class: "card fail" + (stale ? " stale" : "") }, head("Failed", "pill-bad"), stale ? staleNote() : null, q,
      el("p", { role: "alert" }, c.failure.message),
      el("p", { class: "hint" }, c.failure.kind === "no_active_closure" ? "Pick a date when a project is active." : "The deterministic project assessment above is still valid and usable. Raw details are in the diagnostics panel."));
  }
  if (c.state === "clarification") {
    return el("article", { class: "card clar" + (stale ? " stale" : "") }, head("Needs clarification", "pill-hyp"), stale ? staleNote() : null, q,
      el("p", {}, c.clarification), el("p", { class: "hint" }, "Edit the question and run the comparison again. No options were calculated."));
  }
  const opts = selectedOptions();
  return el("article", { class: "card ok" + (stale ? " stale" : "") }, head("Success", "pill-ok"), stale ? staleNote() : null, q,
    el("p", { class: "hint" }, "Figures below are Python-checked. The model's rationale and per-option reasons are unchecked and are kept in the model diagnostics panel."),
    el("p", { class: "hint" }, `The same ${c.assessment.closed_link_ids.length} closed link(s) apply under every option. Route geometry and lengths were calculated by Python; the model only chose from saved candidates.`),
    el("div", { class: "option-grid" }, opts.map(optionBlock)),
    el("p", { class: "hint" }, "Connector lengths are planning allowances between mapped nodes; results apply to walking only."));
}

function endpointLine(label, info) {
  if (!info) return el("li", {}, `${label}: not resolved yet.`);
  if (info.status === "outside_coverage") {
    return el("li", {}, el("strong", {}, `${label}: outside loaded map coverage. `),
      info.reason === "outside_extract" ? "This point lies outside the saved map extract (dashed outline on the map)."
        : `This point is inside the extract but more than ${st.data.coverage.snap_metres} m from the nearest mapped walking node.`,
      ` (${info.requested[0].toFixed(5)}, ${info.requested[1].toFixed(5)})`);
  }
  return el("li", {}, `${label}: on the map, snapped to the nearest mapped walking node ${Math.round(info.snap_metres)} m away.`,
    ` (${info.requested[0].toFixed(5)}, ${info.requested[1].toFixed(5)})`);
}

function customCard() {
  if (!isCustom()) return null;
  const info = st.customInfo;
  const half = st.custom.origin || st.custom.destination;
  if (!info) {
    return el("article", { class: "card" }, el("h3", {}, "Your journey"),
      el("p", { class: "hint" }, half ? "Choose the other endpoint to calculate your journey." : "Press “Choose start on map” and “Choose destination on map”, then click the map. You can also enter coordinates."));
  }
  const res = !st.assessStale && st.assessment && st.assessment.custom_journey ? st.assessment.custom_journey : null;
  const row = res && res.row;
  const status = res ? res.status : info.status;
  let pillNode, cls = "card", text;
  if (status === "outside_coverage") {
    pillNode = pill("Outside map coverage", "pill-outside"); cls += " outside";
    text = "Not assessed. At least one endpoint is outside the loaded map coverage, so no route or closure effect can be calculated. This is a limit of the saved map, not a result of the closures.";
  } else if (status === "no_baseline_route") {
    pillNode = pill("No mapped route", "pill-warn"); cls += " stale";
    text = info.message;
  } else if (status === "same_place") {
    pillNode = pill("Same place", "pill-warn"); cls += " stale"; text = info.message;
  } else if (status === "unreachable_under_closures") {
    pillNode = pill("Unreachable under closures", "pill-bad"); cls += " fail";
    text = `Both endpoints are on the map and connected in the baseline without closures (${metres(row.baseline_metres)}), but the active closures cut every mapped walking route between them.`;
  } else if (status === "longer") {
    pillNode = pill(`Longer: ${signed(row.change_metres)}`, "pill-warn"); cls += " stale";
    text = `Reachable under the active closures: ${metres(row.baseline_metres)} without closures, ${metres(row.metres)} with them.`;
  } else if (status === "unchanged") {
    pillNode = pill("Unchanged", "pill-ok"); cls += " ok";
    text = `Reachable and unaffected: ${metres(row.baseline_metres)} with or without the active closures.`;
  } else {
    pillNode = pill("Ready to assess", "pill-ok"); cls += " ok";
    text = `Both endpoints are on the map and connected without closures (${metres(info.baseline_metres)}). Choose a date and closure sections, then select “Assess projects”.`;
  }
  return el("article", { class: cls },
    el("div", { class: "card-title" }, el("h3", {}, "Your journey"),
      el("span", {}, $("demo-controls").hidden ? null : pill("Hypothetical demo", "pill-hyp"), " ", pillNode)),
    el("ul", { class: "endpoint-list" }, endpointLine("Start", info.origin), endpointLine("Destination", info.destination)),
    el("p", {}, text),
    st.assessStale && st.assessment ? staleNote() : null,
    row && row.contributing_projects.length ? el("p", { class: "hint" }, `Caused by: ${row.contributing_projects.map((id) => (st.assessment.active_projects.find((p) => p.id === id) || { label: id }).label).join(", ")}.`) : null,
    el("p", { class: "hint" }, "Walking only. The AI mitigation comparison covers only the saved preset journeys."));
}

function renderResults() {
  const host = $("result-cards");
  if (st.bus) {
    const scenario = st.bus.scenario, result = st.bus.result;
    const kind = scenario.synthetic ? "Synthetic" : `Published ${scenario.service}`;
    if (!result) {
      host.replaceChildren(el("article", { class: "card" }, el("h3", {}, `${kind} bus stop access`),
        el("p", {}, "No bus access calculation is available.")));
      return;
    }
    const usual = busStop(result.normal.stop_id), destination = busStop(result.destination_stop_id);
    const alternative = result.skipped.stop_id && busStop(result.skipped.stop_id);
    const skipped = alternative
      ? `${alternative.name}: ${metres(result.skipped.metres)} walking from the illustrative start${scenario.synthetic ? "" : " to its snapped node"}.`
      : `No reachable alternative stop ${scenario.synthetic ? "remains before the selected destination on this synthetic trip" : "was found within the saved walking map"}.`;
    const selected = st.bus.mode === "normal"
      ? `Normal: ${usual.name}, ${metres(result.normal.metres)} walking.`
      : alternative ? `Hypothetical skip: ${alternative.name}, ${metres(result.skipped.metres)} walking.` : skipped;
    $("bus-summary").textContent = selected;
    host.replaceChildren(el("article", { class: "card" },
      el("div", { class: "card-title" }, el("h3", {}, `${kind} bus stop access`), pill(scenario.synthetic ? "Synthetic / hypothetical" : "Hypothetical skip", "pill-hyp")),
      el("p", {}, `${scenario.service} · ${scenario.direction} · destination ${destination.name}.`),
      el("p", {}, `Normal service: usual stop ${usual.name}, ${metres(result.normal.metres)} walking${scenario.synthetic ? "" : " to its snapped node"}.`),
      el("p", {}, `Hypothetical skipped usual stop: ${skipped}`),
      alternative && result.normal.metres !== null ? el("p", {}, `Walking change: ${signed(result.skipped.metres - result.normal.metres)}${scenario.synthetic ? "" : " between snapped-node routes"}.`) : null,
      el("p", { class: "hint" }, scenario.synthetic
        ? "The alternative is the closest reachable stop still served by this same synthetic trip before the destination. Bus delay: unknown. No walking closures applied."
        : `Closest reachable boardable stop within this saved map only; ${result.outside_coverage_stops} eligible earlier stops outside walking-map coverage were not assessed. Bus delay: unknown. No walking closures applied.`),
      result.outside_coverage_stop_ids.length ? el("details", { open: true },
        el("summary", {}, "Eligible stops outside walking-map coverage"),
        el("ul", {}, result.outside_coverage_stop_ids.map((id) => {
          const stop = busStop(id);
          const reason = stop.snap_reason === "no_walking_network_nearby" ? "no mapped walking node within 75 m" : "outside extract";
          return el("li", {}, `${stop.name} (${stop.id}) — ${reason}`);
        }))) : null,
      scenario.synthetic ? null : el("p", { class: "hint" }, `Straight-line snap offsets, not included in the walks: ${usual.name} ${usual.snap_metres} m${alternative ? `; ${alternative.name} ${alternative.snap_metres} m` : ""}.`),
      scenario.synthetic ? el("p", { class: "hint" }, "The fictional trip and stops are not published service facts.") : null));
    return;
  }
  host.replaceChildren(...[customCard(), assessmentCard(), aiCard()].filter(Boolean));
}

function renderEvidence() {
  const body = $("evidence-body");
  body.replaceChildren();
  if (st.bus) {
    const scenario = st.bus.scenario;
    body.append(el("h3", {}, scenario.synthetic ? "Synthetic scenario and source limits" : "Published trip and source limits"),
      el("p", {}, scenario.synthetic
        ? "The S1 service, direction, trip, stops and walking start are invented; stop positions are saved walking-network nodes, not verified bus stop locations."
        : `Entur scheduled trip ${scenario.trip_id}, service date ${scenario.service_date}; quay locations verified against the national stop registry. The walking start and skipped stop are hypothetical.`));
    if (!scenario.synthetic) body.append(el("p", {}, `Official sources: ${scenario.sources.timetable_url} and ${scenario.sources.stop_registry_url}. ${scenario.sources.attribution}`));
    body.append(el("p", {}, `Map fixture: ${st.data.evidence.fixture.file}; SHA-256: ${st.data.evidence.fixture.sha256}.`),
      el("p", {}, scenario.synthetic ? "Bus delay and boarding accessibility are unknown." : "Snapping is an approximation, not a verified physical connection; the offset and accessibility are not included in walking distances. Bus delay is unknown."));
    return;
  }
  const ev = st.data.evidence, fx = ev.fixture || {};
  const kv = (pairs) => el("dl", { class: "kv" }, pairs.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)]));
  body.append(el("h3", {}, "Provenance"),
    kv([["Scenario ID", el("code", {}, ev.scenario_id)], ["Fixture", el("code", {}, fx.file)], ["Fixture SHA-256", el("code", {}, fx.sha256)],
      ["Original download SHA-256", el("code", {}, fx.original_download_sha256)], ["Source", fx.source_url], ["Retrieved", fx.retrieved_at],
      ["Licence", `${fx.license} · ${fx.attribution}`], ["Planning source", ev.planning_source]]),
    el("p", { class: "hint" }, "The fixture hash is computed on line-ending-normalised bytes so Windows checkouts verify."));
  if (ev.interrupted_way) body.append(el("h3", {}, "Interrupted way"), el("pre", { class: "raw" }, JSON.stringify(ev.interrupted_way, null, 2)));
  body.append(el("h3", {}, "Loaded map coverage"), el("p", { class: "hint" }, coverageText()));
  if (st.customInfo) {
    body.append(el("h3", {}, "Your journey: snapped nodes"), el("pre", { class: "raw" }, JSON.stringify({
      status: st.customInfo.status, origin: st.customInfo.origin, destination: st.customInfo.destination,
      baseline_metres: st.customInfo.baseline_metres }, null, 2)));
  }
  if (ev.unknowns) body.append(el("h3", {}, "Unknowns"), el("pre", { class: "raw" }, JSON.stringify(ev.unknowns, null, 2)));
  if (st.assessment) {
    body.append(el("h3", {}, "Current calculation"),
      kv([["Closed link IDs", el("code", {}, st.assessment.closed_link_ids.join(", ") || "none")], ["Assessment fingerprint", el("code", {}, st.assessment.fingerprint)]]),
      el("h3", {}, "Journey node IDs"),
      el("table", {}, el("tbody", {}, st.assessment.journeys.map((r) => el("tr", {}, el("td", {}, journeyLabel(r.journey_id)),
        el("td", {}, el("code", {}, `${r.journey_id}: ${r.baseline_path[0]} → ${r.baseline_path[r.baseline_path.length - 1]}`)))))));
  }
  body.append(el("h3", {}, "Sections"), el("table", {}, el("tbody", {}, st.data.sections.map((s) => el("tr", {}, el("td", {}, s.label), el("td", {}, el("code", {}, s.id)), el("td", { class: "num" }, `${s.metres} m`))))));
  if (ev.journeys) body.append(el("h3", {}, "Journey evidence"), el("pre", { class: "raw" }, JSON.stringify(ev.journeys, null, 2)));
}

function renderDiagnostics() {
  const d = st.compare && st.compare.diagnostics;
  const body = $("diagnostics-body");
  body.replaceChildren();
  if (!d) { body.append(el("p", { class: "hint" }, "No model request has been made yet.")); return; }
  const textBlock = (title, text) => [el("h3", {}, title), el("p", {}, text)];
  const c = st.compare;
  const reasons = c.state === "success" ? [
    ...textBlock("Model rationale (unchecked)", c.rationale),
    ...c.options.flatMap((o, i) => textBlock(`Option ${i + 1} reason (unchecked): ${o.candidate.label}`, o.reason)),
  ] : [];
  body.append(el("dl", { class: "kv" }, ...[["Model", d.model], ["Endpoint", d.endpoint], ["Timeout", `${d.timeout_seconds} s`], ["Requests made", d.requests_made], ["Error", d.error || "none"]].flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, String(v))])),
    ...reasons,
    el("h3", {}, "Raw model reply"), el("pre", { class: "raw" }, d.raw_model_reply === null || d.raw_model_reply === undefined ? "(no reply received)" : d.raw_model_reply));
}

/* ---------- custom journey ---------- */
function coverageText() {
  const c = st.data.coverage;
  const km = (c.maxlat - c.minlat) * 110.54, kmx = (c.maxlon - c.minlon) * 111.32 * Math.cos(((c.minlat + c.maxlat) / 2) * Math.PI / 180);
  return `Loaded coverage (saved extract): latitude ${c.minlat}–${c.maxlat}, longitude ${c.minlon}–${c.maxlon}, about ${kmx.toFixed(1)} × ${km.toFixed(1)} km; ${c.walking_node_count} walking nodes, ${c.walking_link_count} links. Points outside it, or more than ${c.snap_metres} m from the nearest mapped walking node, cannot be assessed.`;
}
function syncCoordInputs() {
  const set = (id, value) => { $(id).value = value === undefined || value === null ? "" : String(value); };
  set("cj-start-lat", st.custom.origin && st.custom.origin[0]); set("cj-start-lon", st.custom.origin && st.custom.origin[1]);
  set("cj-dest-lat", st.custom.destination && st.custom.destination[0]); set("cj-dest-lon", st.custom.destination && st.custom.destination[1]);
}
function setPick(which) {
  st.pick = st.pick === which ? null : which;
  $("pick-start").setAttribute("aria-pressed", String(st.pick === "origin"));
  $("pick-dest").setAttribute("aria-pressed", String(st.pick === "destination"));
  $("map-frame").classList.toggle("picking", Boolean(st.pick));
  $("pick-hint").textContent = st.pick
    ? `Click the map to place the ${st.pick === "origin" ? "start" : "destination"}.`
    : "Or choose your own start and destination on the map.";
}
function selectCustom() {
  if (!$("journey-select").querySelector(`option[value="${CUSTOM}"]`)) $("journey-select").append(el("option", { value: CUSTOM }, "Your own journey"));
  st.journeyId = CUSTOM; $("journey-select").value = CUSTOM;
}
async function resolveCustom() {
  const seq = ++st.customSeq;
  if (!(st.custom.origin && st.custom.destination)) {
    st.customInfo = null;
  } else {
    try {
      const info = await api("/api/journey", { case_id: st.caseId, custom_journey: {
        origin: { lat: st.custom.origin[0], lon: st.custom.origin[1] },
        destination: { lat: st.custom.destination[0], lon: st.custom.destination[1] } } });
      if (seq !== st.customSeq) return;
      st.customInfo = info;
    } catch (e) { if (seq === st.customSeq) { st.customInfo = null; showError(e.message); } }
  }
  const valid = new Set(allSections().map((s) => s.id));
  for (const p of st.projects) for (const id of [...p.sections]) if (!valid.has(id)) p.sections.delete(id);
  renderProjects(); drawMap(); renderResults(); renderEvidence();
  if (st.customInfo) fitBox(journeyBox(), 0.25);
}
function setPoint(which, lat, lon) {
  st.custom[which] = [Math.round(lat * 1e6) / 1e6, Math.round(lon * 1e6) / 1e6];
  selectCustom(); setPick(null); syncCoordInputs();
  st.customInfo = null;
  inputsChanged(); drawMap(); renderResults();
  resolveCustom();
}
function clearCustom() {
  st.custom = { origin: null, destination: null }; st.customInfo = null; st.customSeq++;
  setPick(null); syncCoordInputs();
  const valid = new Set(st.data.sections.map((s) => s.id));
  for (const p of st.projects) for (const id of [...p.sections]) if (!valid.has(id)) p.sections.delete(id);
  if (isCustom()) { st.journeyId = st.data.journeys[0].id; $("journey-select").value = st.journeyId; }
  renderProjects(); inputsChanged(); drawMap(); renderResults(); renderEvidence();
  fitBox(journeyBox(), 0.25);
}
function applyCoords() {
  showError("");
  const num = (id) => (/^\s*-?\d{1,3}(\.\d+)?\s*$/.test($(id).value) ? Number($(id).value) : NaN);
  const values = ["cj-start-lat", "cj-start-lon", "cj-dest-lat", "cj-dest-lon"].map(num);
  if (values.some((v) => Number.isNaN(v))) { showError("Enter all four coordinates as decimal numbers, for example 60.8044 and 11.0490."); return; }
  st.custom.origin = [values[0], values[1]]; st.custom.destination = [values[2], values[3]];
  setPoint("origin", values[0], values[1]);
}
function mapPoint(event) {
  const map = $("map"), pt = map.createSVGPoint();
  pt.x = event.clientX; pt.y = event.clientY;
  const p = pt.matrixTransform(map.getScreenCTM().inverse());
  return st.unproj(p.x, p.y);
}

/* ---------- case loading and wiring ---------- */
function setBusView(active) {
  for (const id of ["walking-case", "walking-projects", "walking-ai"]) $(id).hidden = active;
  $("load-bus").hidden = active;
  $("published-bus-picker").hidden = active;
  $("bus-controls").hidden = !active;
  $("diagnostics").hidden = active;
  $("map-help").textContent = active
    ? "Drag to pan. With the map focused: arrow keys pan, + and − zoom, 0 fits the journey. Ctrl + wheel zooms."
    : "Drag to pan. With the map focused: arrow keys pan, + and − zoom, 0 fits the journey. Ctrl + wheel zooms. To set a start or destination, press its button, then click the map.";
  $("mode-badge").textContent = active ? `${st.bus.scenario.synthetic ? "Synthetic" : `Dated ${st.bus.scenario.service}`} bus scenario · walking access` : "Walking supported · other modes planned";
}

async function updateBus() {
  showError("");
  st.bus.result = null;
  $("bus-summary").textContent = "Calculating walking access locally…";
  applyStale(); drawMap();
  setBusy("Calculating bus stop access locally…");
  try {
    st.bus.result = await api("/api/bus/assess", { destination_stop_id: $("bus-destination").value, scenario: st.bus.scenario.synthetic ? "synthetic" : $("published-bus-case").value });
  } catch (e) {
    $("bus-summary").textContent = "Bus access could not be calculated; see the error below.";
    showError(e.message);
  } finally {
    setBusy("");
    applyStale(); drawMap(); renderEvidence();
    fitBox(journeyBox(), 0.25);
  }
}

async function loadBus(published = false) {
  st.demoBusy = true; $("plan-fields").disabled = true;
  showError("");
  setBusy("Loading bus scenario…");
  try {
    const scenario = await api(published ? `/api/bus/published/${encodeURIComponent($("published-bus-case").value)}` : "/api/bus");
    st.layers = Object.fromEntries(LAYERS.map((layer) => [layer.key, true]));
    $("demo-controls").hidden = true;
    if (!await loadCase(scenario.case_id)) return;
    $("case-select").value = st.caseId;
    st.bus = { scenario, result: null, mode: "normal" };
    const usualIndex = scenario.stops.findIndex((stop) => stop.id === scenario.usual_stop_id);
    $("bus-destination").replaceChildren(...scenario.stops.slice(usualIndex + 1)
      .filter((stop) => scenario.synthetic || (stop.node_id && stop.for_alighting && !stop.timing_point))
      .map((stop) => el("option", { value: stop.id }, stop.name)));
    $("bus-destination").value = scenario.default_destination_stop_id;
    $("bus-mode").value = "normal";
    $("bus-service").textContent = `${scenario.service} · ${scenario.direction} · ${scenario.trip_id}${scenario.service_date ? " · " + scenario.service_date : ""}`;
    $("bus-disclaimer").textContent = scenario.synthetic
      ? "Synthetic service, direction, trip and stops: not published bus service or actual stops. The skipped stop is hypothetical."
      : "Published scheduled trip and quay locations for the stated date; the walking start and skipped stop are hypothetical, not a reported closure.";
    $("bus-limits").textContent = scenario.synthetic
      ? "Synthetic stops are assumed boardable. Walking distance only; bus delay unknown. No walking closures or bus route are modeled."
      : "Distances end at nearby snapped map nodes, not the quay. Physical connections and accessibility are unverified; offsets are excluded. Outside-map stops are unassessed. Bus delay unknown.";
    $("bus-sequence").textContent = `${scenario.synthetic ? "Synthetic" : "Published scheduled"} trip stop order: ` + scenario.stops.map((stop) => stop.name).join(" → ");
    setBusView(true);
    await updateBus();
  } catch (e) {
    showError(e.message);
  } finally {
    st.demoBusy = false; setBusy("");
  }
}

function closeBus() {
  st.bus = null;
  setBusView(false); showError("");
  applyStale(); drawMap(); renderEvidence(); renderDiagnostics();
  fitBox(journeyBox(), 0.25);
}

async function loadCase(id) {
  clearTimeout(st.timer); st.seq++;
  setBusy("Loading saved map…");
  try {
    st.data = await api(`/api/cases/${encodeURIComponent(id)}`);
    st.caseId = id;
    st.assessment = null; st.compare = null; st.assessStale = false; st.compareStale = false;
    st.custom = { origin: null, destination: null }; st.customInfo = null; st.customSeq++;
    setPick(null); syncCoordInputs();
    buildProjection();
    $("case-summary").textContent = st.data.summary;
    $("coverage-note").textContent = coverageText();
    const js = $("journey-select");
    js.replaceChildren(...st.data.journeys.map((j) => el("option", { value: j.id }, j.label)), el("option", { value: CUSTOM }, "Your own journey (choose on map)"));
    st.journeyId = st.data.journeys[0].id; js.value = st.journeyId;
    st.nextProject = 1; defaultProjects(); renderProjects();
    $("layer-list").replaceChildren();
    $("question").value = "Which two connections would best restore walking access while the closures are active?";
    fitBox(st.bounds, 0.08);
    drawMap(); applyStale(); renderEvidence(); renderDiagnostics();
    fitBox(journeyBox(), 0.25);
    return true;
  } catch (e) { showError(e.message); return false; } finally { setBusy(""); }
}

async function updateDemo() {
  const choice = $("demo-closures").value;
  $("demo-distance").textContent = "Calculating demo route locally…";
  const active = {
    ringgata: choice === "ringgata" || choice === "both",
    furubergvegen: choice === "furubergvegen" || choice === "both",
  };
  const day = "2026-05-15", inactive = "2026-05-14";
  $("assess-date").value = day;
  st.projects = [
    { uid: st.nextProject++, name: "Hypothetical Ringgata closure", start: active.ringgata ? day : inactive, end: active.ringgata ? day : inactive, sections: new Set(["verified-closure"]) },
    { uid: st.nextProject++, name: "Hypothetical Furubergvegen closure", start: active.furubergvegen ? day : inactive, end: active.furubergvegen ? day : inactive, sections: new Set(["furubergvegen-crossing"]) },
  ];
  renderProjects();
  if (st.assessment) st.assessStale = true;
  if (st.compare) st.compareStale = true;
  applyStale(); drawMap();
  await assess();
  const row = !st.assessStale && st.assessment && st.assessment.custom_journey && st.assessment.custom_journey.row;
  if (row) fitBox(journeyBox(), 0.25);
}

async function loadDemo() {
  st.demoBusy = true; $("plan-fields").disabled = true;
  $("demo-controls").hidden = true;
  showError("");
  try {
    st.layers = Object.fromEntries(LAYERS.map((layer) => [layer.key, true]));
    if (!await loadCase("hamar-wider-extract")) return;
    $("case-select").value = st.caseId;
    const start = st.data.journeys.find((j) => j.id === "junction-to-north-path");
    const end = st.data.journeys.find((j) => j.id === "junction-area-to-ankerskogen");
    if (!start || !end || !st.data.sections.some((s) => s.id === "furubergvegen-crossing")) {
      throw new Error("The saved demo journey or closure sections are unavailable.");
    }
    st.custom = { origin: [...start.origin.coordinates], destination: [...end.origin.coordinates] };
    selectCustom(); syncCoordInputs();
    await resolveCustom();
    if (!st.customInfo) return;
    if (st.customInfo.status !== "ready") throw new Error(`Demo journey cannot be assessed: ${st.customInfo.message}`);
    $("demo-closures").value = "none";
    $("demo-controls").hidden = false;
    await updateDemo();
  } catch (e) {
    showError(e.message);
  } finally {
    st.demoBusy = false; $("plan-fields").disabled = st.busy;
  }
}

async function init() {
  try {
    st.index = await api("/api/cases");
  } catch (e) { $("map-caption").textContent = e.message; return; }
  $("assess-date").value = st.index.today;
  $("date-rule").textContent = "Start and end dates are inclusive.";
  $("ai-note").textContent = `Runs one request to ${st.index.ai.model} on this computer (${st.index.ai.timeout_seconds} s limit). Needs Ollama to be running; the assessment above does not. AI comparison applies only to the preset journeys, not to your own journey.`;
  $("mode-badge").textContent = "Walking supported · other modes planned";
  $("case-select").replaceChildren(...st.index.cases.map((c) => el("option", { value: c.id }, c.label)));
  $("published-bus-case").replaceChildren(...st.index.bus_cases.map((c) => el("option", { value: c.id }, c.label)));
  $("load-bus").addEventListener("click", () => loadBus());
  $("load-published-bus").addEventListener("click", () => loadBus(true));
  $("close-bus").addEventListener("click", closeBus);
  $("bus-destination").addEventListener("change", updateBus);
  $("bus-mode").addEventListener("change", (e) => {
    st.bus.mode = e.target.value;
    renderResults(); drawMap(); fitBox(journeyBox(), 0.25);
  });
  $("load-demo").addEventListener("click", loadDemo);
  $("demo-closures").addEventListener("change", updateDemo);
  $("case-select").addEventListener("change", (e) => { $("demo-controls").hidden = true; loadCase(e.target.value); });
  $("journey-select").addEventListener("change", (e) => { $("demo-controls").hidden = true; st.journeyId = e.target.value; drawMap(); renderResults(); fitBox(journeyBox(), 0.25); });
  $("pick-start").addEventListener("click", () => { $("demo-controls").hidden = true; selectCustom(); setPick("origin"); drawMap(); renderResults(); });
  $("pick-dest").addEventListener("click", () => { $("demo-controls").hidden = true; selectCustom(); setPick("destination"); drawMap(); renderResults(); });
  $("clear-custom").addEventListener("click", clearCustom);
  $("apply-coords").addEventListener("click", applyCoords);
  $("assess-date").addEventListener("input", inputsChanged);
  $("question").addEventListener("input", () => { if (st.compare) { st.compareStale = true; applyStale(); clearTimeout(st.timer); st.timer = setTimeout(checkFingerprint, 150); } });
  $("assess-btn").addEventListener("click", assess);
  $("compare-btn").addEventListener("click", compareWithAi);
  $("plan-form").addEventListener("submit", (e) => e.preventDefault());
  $("add-project").addEventListener("click", () => {
    if (st.projects.length >= 4) { showError("The workspace supports up to 4 projects."); return; }
    const verified = st.data.sections.find((s) => s.verified) || st.data.sections[0];
    const n = st.projects.length + 1;
    st.projects.push({ uid: st.nextProject++, name: `Hypothetical roadworks ${String.fromCharCode(64 + n)}`, start: $("assess-date").value || st.index.today, end: $("assess-date").value || st.index.today, sections: new Set([verified.id]) });
    renderProjects(); inputsChanged();
  });
  const projects = $("projects");
  projects.addEventListener("input", onProjectInput);
  projects.addEventListener("change", onProjectInput);
  projects.addEventListener("click", (e) => {
    const uid = e.target.getAttribute && e.target.getAttribute("data-remove");
    if (!uid) return;
    st.projects = st.projects.filter((p) => String(p.uid) !== uid);
    renderProjects(); inputsChanged();
  });
  $("layer-list").addEventListener("change", (e) => { const k = e.target.getAttribute("data-layer"); if (k) { st.layers[k] = e.target.checked; drawMap(); } });
  $("zoom-in").addEventListener("click", () => zoom(1.4));
  $("zoom-out").addEventListener("click", () => zoom(1 / 1.4));
  $("fit-route").addEventListener("click", () => fitBox(journeyBox(), 0.25));
  $("fit-all").addEventListener("click", () => fitBox(st.bounds, 0.08));
  const frame = $("map-frame");
  frame.addEventListener("keydown", (e) => {
    const step = 0.12;
    const actions = { ArrowLeft: () => pan(-step, 0), ArrowRight: () => pan(step, 0), ArrowUp: () => pan(0, -step), ArrowDown: () => pan(0, step),
      "+": () => zoom(1.25), "=": () => zoom(1.25), "-": () => zoom(0.8), "0": () => fitBox(journeyBox(), 0.25) };
    if (actions[e.key]) { e.preventDefault(); actions[e.key](); }
  });
  let drag = null;
  frame.addEventListener("pointerdown", (e) => { if (e.target.closest("button")) return; drag = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, moved: false }; frame.setPointerCapture(e.pointerId); });
  frame.addEventListener("pointermove", (e) => {
    if (!drag) return;
    if (Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 4) drag.moved = true;
    if (st.pick && !drag.moved) return;
    const rect = frame.getBoundingClientRect(), s = Math.max(st.view.w / rect.width, st.view.h / rect.height);
    st.view.x -= (e.clientX - drag.x) * s; st.view.y -= (e.clientY - drag.y) * s; drag = { ...drag, x: e.clientX, y: e.clientY }; applyView();
  });
  frame.addEventListener("pointerup", (e) => {
    const finished = drag;
    drag = null;
    if (finished && !finished.moved && st.pick) { const [lat, lon] = mapPoint(e); setPoint(st.pick, lat, lon); }
  });
  frame.addEventListener("wheel", (e) => { if (e.ctrlKey) { e.preventDefault(); zoom(e.deltaY < 0 ? 1.15 : 0.87); } }, { passive: false });
  window.addEventListener("resize", () => { if (st.data) fitBox(journeyBox(), 0.25); });
  await loadCase(st.index.cases[0].id);
}
init();
})();

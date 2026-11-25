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
  catalogue: null, catalogueBox: null, demoBusy: false, bus: null, noticeDraft: null, modeledConfirmed: false,
  endpointLabels: { origin: null, destination: null },
  endpointPlaces: { origin: null, destination: null },
  placeMatches: { origin: [], destination: [] }, placeSeq: { origin: 0, destination: 0 },
  placeTimer: { origin: null, destination: null }, savedJourneys: [],
  addressSeq: 0, aiPaused: false,
  invalidSavedData: false,
  journeyAlerts: [], dismissedJourneyAlerts: [], readJourneyAlerts: [], alertSnapshot: null,
  monitorScenario: null, invalidMonitorScenario: false, alertSeq: 0,
};
const CUSTOM = "custom";
const SAVED_JOURNEYS_KEY = "hamar-access-lab.saved-journeys.v1";
const JOURNEY_ALERT_STATE_KEY = "hamar-access-lab.journey-alert-state.v1";
const MONITOR_SCENARIO_KEY = "hamar-access-lab.monitor-scenario.v1";
const isDriving = () => st.data && st.data.mode === "vehicle";
const isCustom = () => st.journeyId === CUSTOM;
const allSections = () => st.data.sections.concat(st.customInfo ? st.customInfo.sections : []);
function endpointLabel(which) {
  return st.endpointLabels[which] || (which === "origin" ? "Start" : "Destination");
}

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

function showDetails(panelId) {
  const dialog = $("details-dialog");
  if (!dialog.open) dialog.showModal();
  if (panelId) { $(panelId).open = true; $(panelId).scrollIntoView({block:"nearest"}); }
}

function drawCatalogue() {
  const {line,pattern,service_date}=st.catalogue;
  const coordinates=pattern.geometry?.length>1?pattern.geometry:pattern.stops.map(stop=>[stop.longitude,stop.latitude]);
  const features=[{type:'Feature',properties:{kind:'opt2'},geometry:{type:'LineString',coordinates}},
    ...pattern.stops.map((stop,index)=>({type:'Feature',properties:{kind:'marker',colour:stop.in_hamar?'#735deb':'#7890aa',label:index===0||index===pattern.stops.length-1?stop.name:''},geometry:{type:'Point',coordinates:[stop.longitude,stop.latitude]}}))];
  const xs=coordinates.map(p=>p[0]),ys=coordinates.map(p=>p[1]);
  const bounds=[[Math.min(...xs),Math.min(...ys)],[Math.max(...xs),Math.max(...ys)]];
  window.__hamarMapPayload={caseId:pattern.id,data:{type:'FeatureCollection',features},bounds};
  window.hamarGeo?.sync(window.__hamarMapPayload);
  const points=coordinates.map(p=>st.proj(p[1],p[0]));
  const map=$('map');map.replaceChildren(polyline(points,{stroke:'#735deb',width:4}));
  const px=points.map(p=>p[0]),py=points.map(p=>p[1]);
  const x=Math.min(...px),y=Math.min(...py),w=Math.max(...px)-x,h=Math.max(...py)-y;
  st.catalogueBox={x,y,w,h};
  $('map-freshness').textContent='Saved timetable snapshot';$('map-freshness').className='chip chip-idle';
  $('map-caption').textContent=pattern.geometry?'Imported Entur route geometry; not a closure assessment.':'Stop-to-stop schematic: route geometry unavailable.';
  $('journey-overview').replaceChildren(
    el('div',{class:'overview-heading'},el('h3',{},`${line.code} · ${line.name}`),el('span',{class:'scenario-badge'},'Published bus route')),
    el('div',{class:'overview-stats'},stat('Ordered stops',String(pattern.stops.length)),stat('Stops in Hamar',String(pattern.stops.filter(s=>s.in_hamar).length)),stat('Scheduled journeys',String(pattern.scheduled_journey_count))),
    el('p',{class:'overview-note'},`${service_date} · ${pattern.stops[0].name} → ${pattern.stops.at(-1).name}. ${pattern.scheduled_journey_count===0?'No scheduled journeys for this variant on the snapshot date.':'Scheduled snapshot; not live departures.'} Bus delay and closure effects are not assessed.`));
}

function syncGeographicMap() {
  if (!st.data) return;
  const features = [];
  const coordinate = (id) => {const point=st.data.nodes[id] || st.customInfo?.routing_overlay?.nodes?.[id];return point?[point[1],point[0]]:null;};
  const line = (kind,path) => {
    if (!st.layers[kind]) return;
    const coordinates=path.map(coordinate).filter(Boolean);
    if(coordinates.length>1)features.push({type:"Feature",properties:{kind},geometry:{type:"LineString",coordinates}});
  };
  const marker=(point,label,colour)=>{if(point&&st.layers.markers)features.push({type:"Feature",properties:{kind:"marker",label,colour},geometry:{type:"Point",coordinates:[point[1],point[0]]}});};
  const section=(kind,ids)=>{for(const id of ids){const link=st.linkIndex[id];if(link)line(kind,[link[1],link[2]]);}};
  if(st.bus){
    const result=st.bus.result,scenario=st.bus.scenario;
    if(result){line("baseline",result.normal.path);line("route",result[st.bus.mode].path);}
    marker(scenario.origin.coordinates || st.data.nodes[scenario.origin.node_id],"A · Start","#127a66");
    const usual=busStop(scenario.usual_stop_id);marker(usual.coordinates,usual.name,st.bus.mode==="skipped"?"#e34c57":"#498dff");
    if(result?.skipped.stop_id){const stop=busStop(result.skipped.stop_id);marker(stop.coordinates,stop.name,"#ce7a20");}
    const stop=busStop($("bus-destination").value);if(stop)marker(stop.coordinates,stop.name,"#18374d");
  }else{
    const row=selectedRow();
    if(row&&!st.assessStale){line("baseline",row.baseline_path);if(!st.data.municipal || st.projects.length)line("route",row.path);}
    if(st.assessment&&!st.assessStale)section("closure",st.assessment.closed_link_ids);
    else for(const project of st.projects)for(const id of project.sections){const part=allSections().find(s=>s.id===id);if(part)section("inactive",part.link_ids);}
    if(!st.compareStale)selectedOptions().forEach(({row},i)=>{if(row)line(i?"opt2":"opt1",row.path);});
    if(isCustom()){
      marker(st.custom.origin,"A · Start","#127a66");marker(st.custom.destination,"B · Destination","#18374d");
    }else{
      const journey=st.data.journeys.find(item=>item.id===st.journeyId);
      if(journey){marker(journey.origin.coordinates || st.data.nodes[journey.origin.id],"A · Start","#127a66");marker(journey.destination.coordinates || st.data.nodes[journey.destination.id],"B · Destination","#18374d");}
    }
  }
  const c=st.data.coverage;
  if(st.layers.coverage)features.push({type:"Feature",properties:{kind:"coverage"},geometry:st.data.boundary || {type:"LineString",coordinates:[[c.minlon,c.minlat],[c.maxlon,c.minlat],[c.maxlon,c.maxlat],[c.minlon,c.maxlat],[c.minlon,c.minlat]]}});
  const box=journeyBox();
  const southwest=st.unproj(box.x,box.y+box.h),northeast=st.unproj(box.x+box.w,box.y);
  const payload={caseId:st.caseId,data:{type:"FeatureCollection",features},bounds:[[southwest[1],southwest[0]],[northeast[1],northeast[0]]]};
  window.__hamarMapPayload=payload;
  if(window.hamarGeo)window.hamarGeo.sync(payload);
}

/* ---------- workspace presentation ---------- */
function wrapDisclosure(id, label, nodes) {
  const first = nodes[0];
  if (!first) return null;
  const details = el("details", { id, class: "control-disclosure" }, el("summary", {}, label));
  first.before(details);
  nodes.forEach((node) => { if (node) details.append(node); });
  return details;
}

/* Mobile uses the same controls and state, inside a native modal sheet. */
function prepareMobileWorkspace() {
  const mobile = window.matchMedia("(max-width: 760px)");
  const controls = $("controls"), sheet = $("mobile-planner");
  const anchor = document.createComment("Desktop planner position");
  controls.before(anchor);
  const extras = [document.querySelector(".map-options"), document.querySelector(".map-status-line"), document.querySelector(".map-card > .attribution")];
  const extraAnchors = extras.map(node => { const marker = document.createComment("Map details position"); node.before(marker); return marker; });
  const show = () => {
    if (!mobile.matches || sheet.open) return;
    sheet.showModal();
    document.body.classList.add("mobile-planner-open");
    sheet.scrollTop = 0;
  };
  const hide = () => { if (sheet.open) sheet.close(); };
  $("open-mobile-planner").addEventListener("click", show);
  $("close-mobile-planner").addEventListener("click", hide);
  sheet.addEventListener("close", () => document.body.classList.remove("mobile-planner-open"));
  sheet.addEventListener("click", event => { if (event.target === sheet && event.clientY < sheet.getBoundingClientRect().top) hide(); });
  const changeLayout = () => {
    if (mobile.matches) {
      hide(); sheet.append(controls);
      extras.forEach(node => $("results").append(node));
    } else {
      hide(); anchor.after(controls);
      extras.forEach((node, index) => extraAnchors[index].after(node));
    }
    window.dispatchEvent(new Event("resize"));
  };
  mobile.addEventListener("change", changeLayout);
  changeLayout();
  const pickBar = el("div", {class:"mobile-pick-bar", id:"mobile-pick-bar", hidden:true},
    el("span", {id:"mobile-pick-label",role:"status"}),
    el("button", {type:"button",class:"btn btn-small",id:"cancel-mobile-pick"}, "Cancel"));
  $("map-frame").append(pickBar);
  $("cancel-mobile-pick").addEventListener("click", () => { setPick(null); show(); });
  window.addEventListener("hamar-pick-state", event => {
    pickBar.hidden = !mobile.matches || !event.detail;
    if (event.detail && mobile.matches) {
      hide();
      $("mobile-pick-label").textContent = event.detail === "origin" ? "Tap the map to choose your start" : "Tap the map to choose your destination";
    }
  });
  window.addEventListener("hamar-point-selected", () => { if (mobile.matches) show(); });
  window.addEventListener("hamar-assessed", hide);
  window.addEventListener("hamar-bus-catalogue", hide);
  document.querySelectorAll("[data-workspace-mode]").forEach(button => button.addEventListener("click", show));
  // Main journey inputs precede examples, coverage and expert controls on phones.
  $("custom-journey").classList.add("journey-inputs");
  document.querySelector(".place-search").append($("search-coverage"));
  const tools = wrapDisclosure("planning-tools", "Planning tools & changes", [$("walking-projects"), $("ai-tools")]);
  tools.open = !mobile.matches;
  mobile.addEventListener("change", () => { tools.open = !mobile.matches; });
  ["load-demo", "load-koigen-demo"].forEach(id => $(id).addEventListener("click", () => {
    $("demo-settings").open = true;
    tools.open = true;
  }));
}

function prepareAiControls(dialog) {
  const button=el("button",{type:"button",id:"toggle-ai-calls",class:"btn btn-small",disabled:true},"Pause AI assistance");
  const status=el("p",{id:"ai-control-status",class:"hint",role:"status"},"Checking AI controls…");
  dialog.append(el("section",{class:"ai-run-controls"},el("h3",{},"AI assistance"),status,button));
  function show(result) {
    st.aiPaused=!result.enabled;
    button.textContent=st.aiPaused?"Resume AI assistance":"Pause AI assistance";
    status.textContent=st.aiPaused?"AI paused. New calls are blocked; an already-started request may finish. Walking calculations still work.":"AI assistance is enabled. Each action allows one bounded local request.";
    button.disabled=false;syncWorkspace();
  }
  button.addEventListener("click",async()=>{
    button.disabled=true;
    try {show(await api("/api/ai/control",{enabled:st.aiPaused}));}
    catch(error){status.textContent=error.message;button.disabled=false;}
  });
  api("/api/ai/status").then(show).catch(()=>{status.textContent="Restart the workspace server to use AI pause controls.";});
}

function prepareWorkspace() {
  window.addEventListener("hamar-bus-catalogue",event=>{st.catalogue=event.detail;$("bus-controls").hidden=true;drawCatalogue();syncWorkspace();fitBox(journeyBox(),.2);});
  const results=$("results");
  const dialog=el("dialog", {id:"details-dialog",class:"details-modal","aria-labelledby":"details-heading"});
  const close=el("button",{type:"button",class:"btn btn-small","aria-label":"Close details"},"×");
  close.addEventListener("click",()=>dialog.close());
  dialog.append(el("div",{class:"details-header"},el("h2",{id:"details-heading"},"Source and technical details"),close));
  results.before(dialog);dialog.append(results);prepareAiControls(dialog);
  $("details-button").addEventListener("click",()=>showDetails());
  window.addEventListener("hamar-map-pick",(event)=>{if(st.pick){const [lat,lon]=event.detail;setPoint(st.pick,lat,lon);}});
  wrapDisclosure("demo-settings", "Example closure settings", [$("demo-controls")]);
  wrapDisclosure("case-options", "Map area & example journeys", [
    document.querySelector('label[for="case-select"]'), $("case-select"), $("case-summary"),
    document.querySelector('label[for="journey-select"]'), $("journey-select"),
  ]);
  wrapDisclosure("search-coverage", "Search coverage & limits", [$("place-search-scope")]);
  wrapDisclosure("saved-options", "Saved journeys & alerts", [$("custom-journey").querySelector(".saved-journeys")]);
  wrapDisclosure("project-options", "Review closures & project dates", [$("date-rule"), $("projects"), $("add-project")]);
  wrapDisclosure("monitor-options", "Save a scenario for alerts", [$("walking-projects").querySelector(".saved-journeys")]);
  wrapDisclosure("ai-tools", "Compare mitigation options with AI", [$("walking-ai")]);
  wrapDisclosure("bus-example-options", "Synthetic test example", [$("load-bus")]);
  wrapDisclosure("bus-source-details", "Trip details & coverage limits", [$("bus-service"), $("bus-disclaimer"), $("bus-sequence"), $("bus-limits")]);
  wrapDisclosure("pick-options", "Choose points on the map instead", [$("pick-hint"), $("custom-journey").querySelector(".pick-row")]);
  const koigen = $("koigen-demo-controls");
  wrapDisclosure("koigen-scope-details", "What the source confirms & what is unknown", [koigen.querySelector("p"), koigen.querySelectorAll("p")[1]]);
  const action = $("assess-btn");
  const note = action.nextElementSibling;
  $("planner-actions").append(action, note);
  document.querySelectorAll("[data-workspace-mode]").forEach((button) => {
    button.addEventListener("click", () => switchWorkspaceMode(button.dataset.workspaceMode));
  });
  prepareMobileWorkspace();
}

function syncWorkspace() {
  if (!st.data) return;
  const mode = (st.bus || st.catalogue) ? "bus" : isDriving() ? "driving" : "walking";
  document.body.dataset.mode = mode;
  document.body.dataset.plainWalk = String(mode === "walking" && st.data.municipal && !st.projects.length);
  document.querySelectorAll("[data-workspace-mode]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.workspaceMode === mode));
    button.disabled = st.busy || st.demoBusy;
  });
  $("draft-koigen-notice").disabled = st.aiPaused || st.busy;
  $("compare-btn").disabled = st.aiPaused || st.busy || st.data.candidates.length < 3;
  $("bus-section").hidden = mode !== "bus";
  $("planner-actions").hidden = mode === "bus";
  $("assessment-panel").hidden = Boolean(st.catalogue);
  $("evidence").hidden = Boolean(st.catalogue);
  $("diagnostics").hidden = Boolean(st.catalogue) || mode === "bus";
  $("details-button").hidden = Boolean(st.catalogue);
  document.querySelector(".map-key").hidden = Boolean(st.catalogue);
  $("walking-case").hidden = mode === "bus";
  $("walking-projects").hidden = mode === "bus";
  $("ai-tools").hidden = mode !== "walking" || st.data.candidates.length < 3;
  $("assess-btn").textContent = mode === "walking" && st.data.municipal && !st.projects.length ? "Find walking route" : "Assess projects";
  $("planner-title").textContent = {walking: "Plan a walk", bus: "Explore Hamar buses", driving: "Explore a driving change"}[mode];
  $("mode-scope").textContent = {
    walking: "Search a Hamar street, house number or bus stop, then choose a result.",
    bus: "Search imported bus lines and route variants, or compare walking access in the saved closure examples.",
    driving: "One supported driving example. The road closure is hypothetical; custom driving journeys are not available yet.",
  }[mode];
  for (const option of $("case-select").options) option.hidden = (option.value === "hamar-driving") !== (mode === "driving");
  $("demo-settings").hidden = mode !== "walking" || $("demo-controls").hidden;
  $("load-demo").hidden = mode !== "walking";
  $("load-koigen-demo").hidden = mode !== "walking";
  renderOverview();
  $("mobile-mode-label").textContent = {walking:"Plan a walk",bus:"Explore Hamar buses",driving:"Driving example"}[mode];
  $("mobile-journey-status").textContent = mode === "bus" ? "Saved timetable · not live departures" : "Saved map · hypothetical changes";
  $("open-mobile-planner").textContent = mode === "bus" ? "Find a bus" : mode === "driving" ? "Edit scenario" : "Plan journey";
}

async function switchWorkspaceMode(mode) {
  if (st.busy || st.demoBusy || !st.index || document.body.dataset.mode === mode) return;
  if (mode === "bus") { if (!st.bus) await loadBus(true); return; }
  st.catalogue = null;
  st.bus = null;
  setBusView(false);
  $("assess-date").value = st.index.today;
  if (mode === "driving") { if (await loadCase("hamar-driving")) await assess(); }
  else await loadCase("hamar-municipality");
  syncWorkspace();
}

function renderOverview() {
  const host = $("journey-overview");
  if (!host || !st.data) return;
  host.dataset.simple = String(Boolean(st.data.municipal && !st.projects.length));
  if (st.catalogue) { drawCatalogue(); return; }
  let normal = null, affected = null, title = "Choose your journey", status = "Ready to explore";
  let note = "Choose a start and destination, then check how the configured changes affect your walk.";
  if (st.bus) {
    title = `${st.bus.scenario.service} · Walking access to the bus`;
    status = st.bus.scenario.synthetic ? "Synthetic example" : "Dated trip · hypothetical stop skip";
    if (st.bus.result) { normal = st.bus.result.normal.metres; affected = st.bus.result.skipped.metres; }
    note = "Distances are walks to mapped stop connections. Bus travel time and delay are unknown.";
  } else {
    const row = selectedRow();
    const stale = st.assessStale;
    title = isDriving() ? "Driving route comparison" : st.data.municipal && !st.projects.length ? "Your walking route" : "Walking route comparison";
    status = stale ? "Inputs changed · recalculate" : row ? (st.data.municipal && !st.projects.length ? "Saved walking network" : "Hypothetical scenario") : "Choose a journey";
    if (row && !stale) { normal = row.baseline_metres; affected = row.metres; }
    if (st.caseId === "koigen-demo") note = "Modeled candidate section. Exact closure extent and dates are unknown; accessibility requires review.";
    else if (isDriving()) note = "Fixed driving example. Turn restrictions, conditional rules and live conditions are not modeled.";
    else if (row && !stale) note = st.data.municipal && !st.projects.length ? `Mapped network only. Start access: ${st.customInfo?.origin?.snap_metres ?? "unknown"} m; destination access: ${st.customInfo?.destination?.snap_metres ?? "unknown"} m excluded and unverified.` : `Walking assessment for ${st.assessment.assessment_date}. Saved map; hypothetical closures.`;
    else if (isCustom() && st.customInfo && st.customInfo.status !== "ready") note = st.customInfo.message;
  }
  const hasResult = normal !== null;
  const display = (value) => value === null ? hasResult ? "No route" : "—" : value >= 1000 ? `${(value / 1000).toFixed(2)} km` : `${value} m`;
  const change = normal !== null && affected !== null ? affected - normal : null;
  const busLimited = st.bus && st.bus.result && st.bus.result.skipped.status === "coverage_limited";
  if (busLimited) note += " Some eligible stops are outside coverage; an alternative cannot be ruled out.";
  host.replaceChildren(
    el("div", {class: "overview-heading"}, el("h3", {}, title), el("span", {class: "scenario-badge"}, status)),
    el("div", {class: "overview-stats"}, stat(st.bus ? "To usual stop" : st.data.municipal && !st.projects.length ? "Walking distance" : "Normal route", display(normal)),
      stat(st.bus ? "After stop skip" : "With changes", busLimited ? "Unassessed" : display(affected)),
      stat("Extra distance", change === null ? busLimited ? "Unknown" : hasResult ? "No route" : "—" : change === 0 ? "Unchanged" : signed(change))),
    el("p", {class: "overview-note"}, note));
}

function resizeMapMarkers() {
  if (!st.view) return;
  const frame = $("map-frame").getBoundingClientRect();
  const unit = Math.max(st.view.w / Math.max(frame.width, 1), st.view.h / Math.max(frame.height, 1));
  $("map").querySelectorAll("[data-map-marker]").forEach((node) => node.setAttribute("r", 6 * unit));
  $("map").querySelectorAll("[data-map-label]").forEach((node) => {
    node.style.fontSize = `${11 * unit}px`;
    node.style.strokeWidth = `${3.5 * unit}px`;
    node.setAttribute("dy", -12 * unit);
  });
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
  if (st.caseId === "koigen-demo") body.modeled_section_confirmation = st.modeledConfirmed;
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
  syncAssessmentGate();
  syncWorkspace();
}

function syncAssessmentGate() {
  $("assess-btn").disabled = st.busy || st.demoBusy || (st.caseId === "koigen-demo" && !st.modeledConfirmed);
}

function defaultProjects() {
  const today = st.index.today;
  const sections = st.data.sections;
  const first = sections.find((s) => s.verified) || sections[0];
  if (!first) { st.projects = []; return; }
  st.projects = [{ uid: st.nextProject++, name: "Hypothetical roadworks A", start: today, end: today, sections: new Set([first.id]) }];
}

function renderProjects() {
  const host = $("projects");
  $("add-project").disabled = !allSections().length;
  host.replaceChildren();
  st.projects.forEach((p, i) => {
    const sec = (cls, s) => el("label", { class: "check" },
      el("input", { type: "checkbox", "data-uid": p.uid, "data-section": s.id, checked: p.sections.has(s.id) }),
      el("span", {}, `${s.label}${s.modeled ? " (modeled)" : ""} (${s.metres} m)`));
    const verified = st.data.sections.filter((s) => s.verified || isDriving());
    const modeled = st.data.sections.filter((s) => s.modeled && !isDriving());
    const others = st.data.sections.filter((s) => !s.verified && !s.modeled && !isDriving());
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
        el("strong", {}, isDriving() ? "Closed road sections" : "Closed walking sections"),
        verified.map((s) => sec("v", s)),
        modeled.length ? el("div", {}, el("strong", { class: "hint" }, "Modeled candidate sections"), modeled.map((s) => sec("m", s))) : null,
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
    window.dispatchEvent(new Event("hamar-assessed"));
    if (st.compare && st.compare.assessment.fingerprint !== result.fingerprint) st.compareStale = true;
    st.seq++;
    $("assess-btn").textContent = "Assess projects";
  } catch (e) {
    showError(e.message);
  } finally {
    setBusy("");
    applyStale(); drawMap(); renderEvidence();
    if (!$("demo-controls").hidden && !$("ringgata-demo-controls").hidden) {
      const row = !st.assessStale && st.assessment && st.assessment.custom_journey && st.assessment.custom_journey.row;
      $("demo-distance").textContent = row
        ? `Walking distance: ${metres(row.metres)} (baseline ${metres(row.baseline_metres)})`
        : "Demo route could not be calculated; see the error below.";
    }
    if (!$("demo-controls").hidden && !$("koigen-demo-controls").hidden) {
      const row = !st.assessStale && st.assessment && st.assessment.journeys[0];
      $("koigen-distance").textContent = row
        ? `Modeled comparison: ${metres(row.baseline_metres)} with the candidate section open; ${metres(row.metres)} with it closed (${signed(row.change_metres)}).`
        : "Modeled route comparison could not be calculated; see the error below.";
    }
  }
}
async function draftFromNotice() {
  showError("");
  setBusy("Drafting from the saved notice with one local Ollama request…");
  st.noticeDraft = null;
  renderResults();
  try {
    st.noticeDraft = await api("/api/notice/draft", { notice_id: st.index.notice_draft.id });
  } catch (e) {
    st.noticeDraft = { state: "failed", failure: { kind: "request_failed", message: e.message } };
  } finally {
    setBusy("");
    renderResults();
    showDetails("assessment-panel");
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
    showDetails("assessment-panel");
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
  if(window.hamarGeo?.active){
    const sw=st.unproj(box.x,box.y+box.h),ne=st.unproj(box.x+box.w,box.y);
    window.hamarGeo.fit([[sw[1],sw[0]],[ne[1],ne[0]]]);
  }
}
function journeyBox() {
  if(st.catalogue)return st.catalogueBox || st.bounds;
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
  resizeMapMarkers();
}
function zoom(factor) {
  if(window.hamarGeo?.active){window.hamarGeo.zoomBy(factor);return;}
  const v = st.view, cx = v.x + v.w / 2, cy = v.y + v.h / 2;
  v.w /= factor; v.h /= factor; v.x = cx - v.w / 2; v.y = cy - v.h / 2;
  applyView();
}
function pan(dx, dy) { if(window.hamarGeo?.active){window.hamarGeo.pan(dx,dy);return;} st.view.x += dx * st.view.w; st.view.y += dy * st.view.h; applyView(); }

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
function nodePoint(id) { const point = st.customInfo?.routing_overlay?.nodes?.[id]; return point ? st.proj(...point) : st.xy[id]; }
function pathPoints(ids) { return ids.map(nodePoint).filter(Boolean); }
function linkSegments(linkIds) {
  const overlay = Object.fromEntries((st.customInfo?.routing_overlay?.links || []).map(link => [link.id,[link.id,link.from,link.to,link.metres]]));
  return linkIds.map((id) => st.linkIndex[id] || overlay[id]).filter(Boolean).map((l) => [nodePoint(l[1]), nodePoint(l[2])]);
}
function addMarker(markers, p, text, fill, ring, side, shortLabel) {
  markers.append(svg("circle", { "data-map-marker": true, cx: p[0], cy: p[1], r: 7, fill: ring ? "#fff" : fill, stroke: ring ? fill : "#fff", "stroke-width": ring ? 3 : 2, "vector-effect": "non-scaling-stroke" }));
  const t = svg("text", { x: p[0] + (side === "left" ? -9 : side === "right" ? 9 : 0),
    y: p[1] - (side ? 2 : 12), class: side ? "bus-map-label" : "map-label", fill,
    "text-anchor": side === "left" ? "end" : side === "right" ? "start" : "middle" });
  t.setAttribute("data-map-label", "true");
  t.textContent = shortLabel || (side ? text : text.startsWith("Start") ? "A · Start" : text.startsWith("Destination") ? "B · Destination" : text.replace(/Candidate endpoint node \d+/g, "Candidate endpoint"));
  const title = svg("title", {}); title.textContent = text; t.append(title);
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
  renderLegend(); resizeMapMarkers();
  const description = st.bus.mode === "normal" ? "normal service" : "hypothetical skipped stop";
  $("map-caption").textContent = `${scenario.service} · ${scenario.direction} · ${description}. ${scenario.synthetic ? "Synthetic trip" : "Published dated trip; hypothetical change"}; walking distance only.`;
  $("map").setAttribute("aria-label", `${scenario.synthetic ? "Synthetic" : "Published"} bus access map: ${scenario.service}, ${scenario.direction}`);
  syncWorkspace();
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
  if(st.catalogue){drawCatalogue();return;}
  const map = $("map");
  map.replaceChildren();
  if (!st.data) return;
  const row = selectedRow();
  const group = (key) => { const g = svg("g", { "data-layer": key }); if (st.layers[key]) map.append(g); return g; };

  const cov = st.data.coverage, covA = st.proj(cov.maxlat, cov.minlon), covB = st.proj(cov.minlat, cov.maxlon);
  group("coverage").append(svg("rect", {
    x: covA[0], y: covA[1], width: covB[0] - covA[0], height: covB[1] - covA[1], fill: "none",
    class: "coverage-outline", stroke: L("coverage").stroke, "stroke-width": L("coverage").width, "stroke-dasharray": L("coverage").dash,
    "vector-effect": "non-scaling-stroke",
  }));

  const ctx = group("context");
  const network = (st.data.municipal && window.hamarGeo?.active ? [] : st.data.links).map((l) => {
    const a = st.xy[l[1]], b = st.xy[l[2]];
    return a && b ? `M${a[0].toFixed(1)},${a[1].toFixed(1)}L${b[0].toFixed(1)},${b[1].toFixed(1)}` : "";
  }).join(" ");
  ctx.append(svg("path", {d: network, class: "network-casing", fill: "none", stroke: "#ffffff", "stroke-width": 5, "vector-effect": "non-scaling-stroke"}));
  ctx.append(svg("path", {d: network, class: "network-line", fill: "none", stroke: "#b8c9c0", "stroke-width": 1.6, "vector-effect": "non-scaling-stroke"}));
  if (st.bus) { drawBusMap(group); syncGeographicMap(); return; }

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
    if (row.path.length && (!st.data.municipal || st.projects.length)) rt.append(polyline(pathPoints(row.path), L("route")));
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
      const shortLabel = name === "Start" ? "A · Start" : "B · Destination";
      if (!raw) continue;
      const info = st.customInfo && st.customInfo[key];
      const requested = st.proj(raw[0], raw[1]);
      if (info && info.status === "outside_coverage") {
        addMarker(markers, requested, `${endpointLabel(key)}: outside loaded map coverage`, "#0b3d75", true, undefined, shortLabel);
      } else {
        if (info && info.snapped) {
          const s = st.proj(info.snapped[0], info.snapped[1]);
          markers.append(svg("line", { x1: requested[0], y1: requested[1], x2: s[0], y2: s[1], stroke: fill, "stroke-width": 2, "stroke-dasharray": "3 3", "vector-effect": "non-scaling-stroke" }));
          addMarker(markers, s, info.snap_metres > 3 ? `${endpointLabel(key)} (nearest mapped node)` : endpointLabel(key), fill, false, undefined, shortLabel);
        } else {
          addMarker(markers, requested, endpointLabel(key), fill, false, undefined, shortLabel);
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
  renderLegend(); resizeMapMarkers();
  const sizeNote = st.assessment ? ` · assessed for ${st.assessment.assessment_date}` : " · not assessed yet";
  const demo = $("demo-controls").hidden ? "" : "Hypothetical demo · ";
  const demoDistance = demo && row ? ` · ${metres(row.metres)}` : "";
  $("map-caption").textContent = `${demo}${journeyLabel(st.journeyId)}${demoDistance}${sizeNote}. ${isDriving() ? "Car road network; closure hypothetical." : "Walking network only."}`;
  $("map").setAttribute("aria-label", `Map of ${journeyLabel(st.journeyId)}`);
  syncWorkspace();
  syncGeographicMap();
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
      : st.bus && layer.key === "route" ? "Selected walking route"
      : isDriving() && layer.key === "context" ? "Mapped car road network" : layer.label;
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
  const projectDates = (p) => st.caseId === "koigen-demo"
    ? `${p.label} (model date inputs only; notice dates unknown)`
    : `${p.label} (${p.start_date} to ${p.end_date})`;
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
      ? `Active (${a.active_projects.length}): ${a.active_projects.map(projectDates).join("; ")}.`
      : "No project is active on this date, so the routes equal the baseline."),
    a.inactive_projects.length ? el("p", { class: "hint" }, `Not active: ${a.inactive_projects.map(projectDates).join("; ")}.`) : null,
    el("p", { class: "hint" }, `${a.closed_link_ids.length} ${a.mode === "vehicle" ? "road" : "walking"} link(s) closed together. ${a.date_rule}`),
    el("table", {}, el("thead", {}, el("tr", {}, ["Journey", "Baseline", "With closures", "Effect", "Caused by"].map((h) => el("th", { scope: "col" }, h)))), el("tbody", {}, rows)),
    el("p", { class: "hint" }, a.mode === "vehicle"
      ? "Driving distance only. Some direction and car access tags are modeled; turn restrictions, conditional rules and live conditions are not. Not an official closure plan."
      : st.caseId === "koigen-demo"
        ? "Walking only. The candidate section and calculated detour are modeled; exact closure extent and dates are unknown. The assessment date only activates the hypothetical calculation."
        : "Walking only. Calculated by Python from the saved map; not an official closure plan."));
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
  if (st.data.candidates.length < 3) {
    return el("article", { class: "card" }, el("h3", {}, "AI mitigation options"),
      el("p", { class: "hint" }, "No AI comparison is available for this case: fewer than three modeled mitigation candidates are configured."));
  }
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
    el("ul", { class: "endpoint-list" },
      endpointLine(endpointLabel("origin"), info.origin),
      endpointLine(endpointLabel("destination"), info.destination)),
    ...["origin", "destination"].filter((side) => st.endpointPlaces[side]).map((side) => {
      const selected = st.endpointPlaces[side], source = selected.source || {};
      return el("p", { class: "hint" }, `${endpointLabel(side)} source: ${source.provider || source.file || "saved Hamar place index"} · ${source.file || selected.source_id || "saved source"}${source.source_url ? ` · ${source.source_url}` : ""}`);
    }),
    el("p", {}, text),
    st.assessStale && st.assessment ? staleNote() : null,
    row && row.contributing_projects.length ? el("p", { class: "hint" }, `Caused by: ${row.contributing_projects.map((id) => (st.assessment.active_projects.find((p) => p.id === id) || { label: id }).label).join(", ")}.`) : null,
    el("p", { class: "hint" }, "Walking only. The AI mitigation comparison covers only the saved preset journeys."));
}

function noticeDraftCard() {
  if (st.caseId !== "koigen-demo") return null;
  const d = st.noticeDraft;
  if (!d) {
    return el("article", { class: "card" },
      el("h3", {}, "Saved-notice review"),
      el("p", { class: "hint" }, "Select “Draft from notice” to make one bounded local Ollama request. The saved source and hand-checked reference can still be used for manual review if Ollama is unavailable."));
  }
  if (d.state === "failed") {
    return el("article", { class: "card fail" },
      el("div", { class: "card-title" }, el("h3", {}, "Saved-notice draft"), pill("Unavailable", "pill-bad")),
      el("p", { role: "alert" }, d.failure.message),
      el("p", { class: "hint" }, "No notice draft was accepted. The manual Koigen demo remains available after explicit modeled-section confirmation."));
  }
  const f = d.fields, checks = d.evidence_checks;
  const modes = f.travel_modes.length ? f.travel_modes.join(", ") : "unknown";
  const review = [
    ["Access status", d.access_status || "unknown"],
    ["Affected location", f.location || "unknown"],
    ["Travel modes", modes],
    ["Restriction", f.restriction || "unknown"],
    ["Stated dates", f.stated_dates || "unknown for the footpath closure"],
  ];
  return el("article", { class: "card clar" },
    el("div", { class: "card-title" }, el("h3", {}, "Saved-notice draft"), pill("Needs human review", "pill-hyp")),
    el("p", { class: "hint" }, "Each consequence is kept separate. Python checks literal quotes within its source sentence; uncertain fields stay unknown. These checks do not verify meaning, closure geometry or physical access."),
    el("dl", { class: "kv" }, review.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)])),
    el("h4", {}, "Supporting sentence"),
    ...d.supporting_sentences.map((s) => el("blockquote", {}, `${s.sentence_id}. ${s.text}`)),
    el("p", { class: "hint" }, `${checks.verified_quotes || 0} source quote checks passed; ${checks.omissions.length + checks.unsupported_claims.length} review issue(s). Unresolved fields need source review.`),
    el("details", {},
      el("summary", {}, "Field evidence and review notes"),
      ...(d.field_evidence || []).map((item) => el("p", {},
        el("strong", {}, `${item.field} · sentence ${item.sentence_id} · ${{quote_found: "Quote found", source_rule: "Source rule — review", not_stated: "Not stated", withheld: "Withheld"}[item.check] || item.check}: `),
        item.source_quote || item.quote || "not stated")),
      checks.omissions.length ? el("p", {}, el("strong", {}, "Missing: "), checks.omissions.join(" ")) : null,
      checks.unsupported_claims.length ? el("p", {}, el("strong", {}, "Withheld or unresolved: "), checks.unsupported_claims.join(" ")) : null),
    el("details", {},
      el("summary", {}, "Local model draft and diagnostics"),
      el("p", { class: "hint" }, `${d.diagnostics.model}; ${d.diagnostics.requests_made} request; ${d.diagnostics.timeout_seconds} s limit; endpoint ${d.diagnostics.endpoint}.`),
      el("pre", { class: "raw" }, d.diagnostics.raw_model_reply || JSON.stringify(d.model_draft, null, 2))),
    el("p", { class: "hint" }, d.notice.attribution));
}

function accessibilityCard() {
  if (st.caseId !== "koigen-demo") return null;
  const a = st.assessment && st.assessment.accessibility;
  if (!a) {
    return el("article", { class: "card" },
      el("div", { class: "card-title" }, el("h3", {}, "Accessibility evidence"), pill("Review required", "pill-warn")),
      el("p", {}, el("strong", {}, "Requirement: avoid steps.")),
      el("p", { class: "hint" }, "Confirm the modeled section and assess to compare evidence for the calculated baseline and modeled detour."));
  }
  const metresBy = (route, key) => route.step_status_metres[key] || 0;
  const row = (label, route) => el("tr", {},
    el("td", {}, label), el("td", { class: "num" }, metres(route.metres)),
    el("td", { class: "num" }, metres(metresBy(route, "known_steps"))),
    el("td", { class: "num" }, metres(metresBy(route, "supported_step_free"))),
    el("td", { class: "num" }, metres(metresBy(route, "unknown"))));
  const evidenceLines = (route) => Object.entries(route.surface_metres)
    .map(([value, distance]) => `${value}: ${metres(distance)}`).join("; ");
  return el("article", { class: "card " + (st.assessStale ? "stale" : "clar") },
    el("div", { class: "card-title" }, el("h3", {}, "Accessibility evidence"), pill("Avoid steps", "pill-warn")),
    st.assessStale ? staleNote() : null,
    el("p", { class: "hint" }, "Only explicitly tagged evidence is counted. An absent steps tag is unknown, not step-free."),
    el("table", {},
      el("thead", {}, el("tr", {}, ["Route", "Distance", "Known steps", "Supported step-free", "Unknown"].map((h) => el("th", { scope: "col" }, h)))),
      el("tbody", {}, row("Shortest baseline", a.baseline), row("Modeled detour", a.modeled_detour))),
    el("p", {}, el("strong", {}, "Alternative: "), a.alternative.reason),
    el("p", {}, el("strong", {}, "Baseline surfaces: "), evidenceLines(a.baseline), "."),
    el("p", {}, el("strong", {}, "Detour surfaces: "), evidenceLines(a.modeled_detour), "."),
    el("p", { class: "unverified" }, `Slope: unknown for ${metres(a.baseline.slope_metres.unknown)} of the baseline and ${metres(a.modeled_detour.slope_metres.unknown)} of the detour. Two-dimensional coordinates were not used to infer slope.`),
    el("p", { class: "hint" }, `OSM historical route evidence checked ${a.provenance.evidence_checked_at}; ${a.provenance.route_nodes_checked} route nodes checked. Fixture retrieved ${a.provenance.snapshot_retrieved_at}; ${a.provenance.attribution}, ${a.provenance.license}.`),
    el("details", {},
      el("summary", {}, "Precise accessibility data gaps"),
      el("ul", {}, a.gaps.map((gap) => el("li", {}, gap))),
      el("p", { class: "hint" }, a.provenance.source_method)));
}

function renderResults() {
  if(st.catalogue){syncWorkspace();return;}
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
      result.unreachable_stop_ids.length ? el("details", { open: true },
        el("summary", {}, "Eligible mapped stops with no walking route from the start"),
        el("ul", {}, result.unreachable_stop_ids.map((id) => {
          const stop = busStop(id);
          return el("li", {}, `${stop.name} (${stop.id}) — disconnected or unmapped route`);
        }))) : null,
      scenario.synthetic ? null : el("p", { class: "hint" }, `Straight-line snap offsets, not included in the walks: ${usual.name} ${usual.snap_metres} m${alternative ? `; ${alternative.name} ${alternative.snap_metres} m` : ""}.`),
      scenario.synthetic ? el("p", { class: "hint" }, "The fictional trip and stops are not published service facts.") : null));
    return;
  }
  host.replaceChildren(...[noticeDraftCard(), accessibilityCard(), customCard(), assessmentCard(), isDriving() ? null : aiCard()].filter(Boolean));
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
  const planningSource = ev.planning_source && /^https?:\/\//.test(ev.planning_source)
    ? el("a", { href: ev.planning_source, target: "_blank", rel: "noopener noreferrer" },
      ev.planning_source_label || ev.planning_source)
    : ev.planning_source || "Not provided";
  body.append(el("h3", {}, "Provenance"),
    kv([["Scenario ID", el("code", {}, ev.scenario_id)], ["Fixture", el("code", {}, fx.file)], ["Fixture SHA-256", el("code", {}, fx.sha256)],
      ["Original download SHA-256", el("code", {}, fx.original_download_sha256)], ["Source", fx.source_url], ["Retrieved", fx.retrieved_at],
      ["Licence", `${fx.license} · ${fx.attribution}`], ["Planning source", planningSource]]),
    el("p", { class: "hint" }, "The fixture hash is computed on line-ending-normalised bytes so Windows checkouts verify."));
  if (ev.interrupted_way) body.append(
    el("h3", {}, st.data.sections.some((s) => s.modeled) ? "Modeled candidate section" : "Interrupted way"),
    el("pre", { class: "raw" }, JSON.stringify(ev.interrupted_way, null, 2)));
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
  if (isDriving()) return `Loaded road extract: latitude ${c.minlat}–${c.maxlat}, longitude ${c.minlon}–${c.maxlon}, about ${kmx.toFixed(1)} × ${km.toFixed(1)} km; ${c.node_count} car-road nodes, ${c.link_count} links. Only the fixed driving journey is supported.`;
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
  window.dispatchEvent(new CustomEvent("hamar-pick-state", {detail:st.pick}));
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
  st.endpointLabels[which] = which === "origin" ? "Selected start" : "Selected destination";
  st.endpointPlaces[which] = null;
  selectCustom(); setPick(null); syncCoordInputs();
  st.customInfo = null;
  inputsChanged(); drawMap(); renderResults();
  resolveCustom();
  window.dispatchEvent(new Event("hamar-point-selected"));
}
function clearCustom() {
  st.custom = { origin: null, destination: null }; st.customInfo = null; st.customSeq++;
  st.endpointLabels = { origin: null, destination: null };
  st.endpointPlaces = { origin: null, destination: null };
  for (const side of ["origin", "destination"]) {
    $(side === "origin" ? "place-from" : "place-to").value = "";
    $(side === "origin" ? "place-from-results" : "place-to-results").replaceChildren();
    $(side === "origin" ? "place-from-status" : "place-to-status").textContent = "";
  }
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
  st.endpointLabels = { origin: "Entered start", destination: "Entered destination" };
  st.endpointPlaces = { origin: null, destination: null };
  setPoint("origin", values[0], values[1]);
}

function placeResultButton(side, place) {
  const type = place.kind === "bus_stop"
    ? `Bus stop${place.services ? ` · ${place.services.join(", ")}` : ""}`
    : place.kind === "address" ? `Address · ${place.postal_code} ${place.postal_place}`
    : place.kind === "street" ? (place.walkable ? "Street · choose a house number for a precise location" : "Road · no mapped pedestrian access") : "Named walking place";
  return el("button", { type: "button", class: "btn btn-small place-result",
    "data-place-side": side, "data-place-id": place.id, disabled:place.kind === "street" && !place.walkable },
  place.name,
  el("small", {}, `${type} · ${place.kind === "address" ? "© Kartverket" : place.source && (place.source.provider || place.source.file)}`));
}

function showPlaceMatches(side, result) {
  const host = $(side === "origin" ? "place-from-results" : "place-to-results");
  const status = $(side === "origin" ? "place-from-status" : "place-to-status");
  st.placeMatches[side] = result.matches;
  if (!result.matches.length) {
    host.replaceChildren();
    status.textContent = result.message || "No Hamar address or saved place found. Check the spelling or choose a point on the map.";
    return;
  }
  status.textContent = result.message || (result.truncated ? "More matches available. Add a house number or a longer street name." : "Choose a result below.");
  host.replaceChildren(...result.matches.map((place) => placeResultButton(side, place)));
}

async function searchPlaces(side) {
  const input = $(side === "origin" ? "place-from" : "place-to");
  const status = $(side === "origin" ? "place-from-status" : "place-to-status");
  const host = $(side === "origin" ? "place-from-results" : "place-to-results");
  const query = input.value.trim(), seq = ++st.placeSeq[side];
  st.placeMatches[side] = []; host.replaceChildren();
  if (!query) { status.textContent = ""; return; }
  if (query.length > 80) { status.textContent = "Use at most 80 characters."; return; }
  const needsAddress = query.length >= 3 && /[^\W\d_]/u.test(query.replace(/[æøåÆØÅ]/g,"a"));
  status.textContent = needsAddress ? "Searching Hamar addresses…" : "Type at least three characters to search addresses.";
  // The offline results and address lookup run independently. An outage never
  // removes a usable bus-stop result or turns an unavailable source into no match.
  const addressRequest = needsAddress ? api(`/api/addresses?q=${encodeURIComponent(query)}`)
    .catch(() => ({status:"unavailable", matches:[], message:"Address lookup is unavailable. Saved places and map selection still work."})) : null;
  let local;
  try {
    const [saved, streets] = await Promise.all([
      api(`/api/places?q=${encodeURIComponent(query)}`).catch(()=>({matches:[],truncated:false})),
      api(`/api/streets?q=${encodeURIComponent(query)}`).catch(()=>({matches:[],truncated:false}))]);
    local = {matches:[...streets.matches,...saved.matches],truncated:streets.truncated || saved.truncated};
  } catch { local = {matches:[],truncated:false}; }
  if (seq !== st.placeSeq[side]) return;
  if (local.matches.length) showPlaceMatches(side, {...local, message:needsAddress ? "Searching Hamar addresses…" : "Choose a result below."});
  if (!addressRequest) return;
  const addresses = await addressRequest;
  if (seq !== st.placeSeq[side]) return;
  const exactLocal = local.matches.filter(item => item.name.toLocaleLowerCase() === query.toLocaleLowerCase());
  const otherLocal = local.matches.filter(item => !exactLocal.includes(item));
  const combined = [...exactLocal, ...addresses.matches, ...otherLocal];
  showPlaceMatches(side, {matches:combined.slice(0,20),truncated:addresses.truncated || local.truncated || combined.length>20,
    message: addresses.status === "unavailable" ? addresses.message : null});
}

async function choosePlace(side, id) {
  const place = st.placeMatches[side].find((item) => item.id === id);
  if (!place) {
    showError("The selected place is no longer in the current search results.");
    return;
  }
  if (["address","street"].includes(place.kind) && st.caseId !== "hamar-municipality") {
    const previous = isCustom() ? {custom:structuredClone(st.custom), labels:{...st.endpointLabels}, places:{...st.endpointPlaces}} : null;
    const selection = ++st.addressSeq;
    $("demo-controls").hidden = true;
    if (!await loadCase("hamar-municipality") || selection !== st.addressSeq) return;
    if (previous) {
      st.custom = previous.custom; st.endpointLabels = previous.labels; st.endpointPlaces = previous.places;
      for (const other of ["origin","destination"]) {
        if (other !== side && previous.custom[other]) $(other === "origin" ? "place-from" : "place-to").value = previous.labels[other] || "";
      }
    }
  }
  st.custom[side] = [...place.coordinates];
  st.endpointLabels[side] = place.name;
  st.endpointPlaces[side] = {
    id: place.id, source: place.source, source_id: place.source_id,
    kind: place.kind, services: place.services || [],
  };
  $(side === "origin" ? "place-from" : "place-to").value = place.name;
  $(side === "origin" ? "place-from-results" : "place-to-results").replaceChildren();
  $(side === "origin" ? "place-from-status" : "place-to-status").textContent = "Selected. Choose the other endpoint or check your journey.";
  selectCustom(); setPick(null); syncCoordInputs();
  st.customInfo = null;
  $("demo-controls").hidden = true;
  inputsChanged(); drawMap(); renderResults();
  await resolveCustom();
}

function savedJourneyError(message) {
  $("saved-journey-message").textContent = message || "";
}

function validSavedJourney(item) {
  const point = (value) => Array.isArray(value) && value.length === 2
    && value.every((number) => typeof number === "number" && Number.isFinite(number));
  const data = item && item.version === 1 && typeof item.id === "string"
    && typeof item.name === "string" && item.name.trim() && item.name.length <= 60
    && typeof item.case_id === "string"
    && st.index.cases.some((entry) => entry.id === item.case_id && entry.id !== "hamar-driving")
    && item.origin && typeof item.origin.label === "string" && item.origin.label.length <= 120
    && item.destination && typeof item.destination.label === "string" && item.destination.label.length <= 120
    && point(item.origin && item.origin.coordinates)
    && point(item.destination && item.destination.coordinates);
  return Boolean(data);
}

function writeSavedJourneys(items) {
  try {
    localStorage.setItem(SAVED_JOURNEYS_KEY, JSON.stringify({ version: 1, journeys: items }));
    st.savedJourneys = items;
    return true;
  } catch (e) {
    savedJourneyError("This browser could not save journeys. Check local storage permissions.");
    return false;
  }
}

function renderSavedJourneys() {
  const host = $("saved-journey-list");
  host.replaceChildren();
  if (!st.savedJourneys.length) {
    host.append(el("p", { class: "hint" }, "No valid saved journeys yet."));
    return;
  }
  for (const journey of st.savedJourneys) {
    const caseLabel = (st.index.cases.find((item) => item.id === journey.case_id) || {}).label || journey.case_id;
    const item = el("div", { class: "saved-item" },
      el("div", {},
        el("p", {}, el("strong", {}, journey.name)),
        el("p", { class: "hint" }, `${journey.origin.label} → ${journey.destination.label}`),
        el("p", { class: "hint" }, caseLabel)),
      el("div", {},
        el("button", { type: "button", class: "btn btn-small", "data-restore-saved": journey.id }, "Restore"),
        " ",
        el("button", { type: "button", class: "btn btn-small", "data-delete-saved": journey.id }, "Delete")));
    host.append(item);
  }
}

function loadSavedJourneys() {
  let raw;
  try {
    raw = localStorage.getItem(SAVED_JOURNEYS_KEY);
  } catch (e) {
    savedJourneyError("Local browser storage is unavailable; saved journeys cannot be loaded.");
    $("discard-saved-data").hidden = true;
    renderSavedJourneys();
    return;
  }
  if (raw === null) {
    st.invalidSavedData = false;
    savedJourneyError("Saved journeys are stored only in this browser.");
    $("discard-saved-data").hidden = true;
    renderSavedJourneys();
    return;
  }
  try {
    const parsed = JSON.parse(raw);
    if (
      !parsed || parsed.version !== 1 || !Array.isArray(parsed.journeys)
      || parsed.journeys.length > 20 || !parsed.journeys.every(validSavedJourney)
    ) {
      throw new Error("invalid");
    }
    st.savedJourneys = parsed.journeys;
    st.invalidSavedData = false;
    savedJourneyError(`Loaded ${st.savedJourneys.length} saved journey${st.savedJourneys.length === 1 ? "" : "s"} from this browser.`);
    $("discard-saved-data").hidden = true;
  } catch (e) {
    st.savedJourneys = [];
    st.invalidSavedData = true;
    savedJourneyError("Saved journey data is invalid and was not loaded. Discard it or leave it unchanged.");
    $("discard-saved-data").hidden = false;
  }
  renderSavedJourneys();
}

function saveSelectedJourney() {
  const name = $("saved-journey-name").value.trim();
  if (!name || name.length > 60) {
    savedJourneyError("Enter a journey name of 1 to 60 characters.");
    $("saved-journey-name").focus();
    return;
  }
  if (st.invalidSavedData) {
    savedJourneyError("Discard the invalid saved data before saving a new journey.");
    return;
  }
  const preset = !isCustom() && st.data.journeys.find((item) => item.id === st.journeyId);
  const origin = preset ? preset.origin.coordinates : st.custom.origin;
  const destination = preset ? preset.destination.coordinates : st.custom.destination;
  if (st.caseId === "hamar-driving" || !origin || !destination) {
    savedJourneyError("Choose both walking endpoints before saving.");
    return;
  }
  if (!preset && (!st.customInfo || st.customInfo.status !== "ready")) {
    savedJourneyError("Resolve a connected walking journey before saving. Outside-coverage and unmapped connections cannot be saved.");
    return;
  }
  if (st.savedJourneys.some((item) => item.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
    savedJourneyError("Use a different name; saved journey names must be unique.");
    return;
  }
  if (st.savedJourneys.length >= 20) {
    savedJourneyError("Delete a saved journey before adding another; this browser stores at most 20.");
    return;
  }
  const journey = {
    version: 1,
    id: `journey-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name, case_id: st.caseId,
    origin: { coordinates: [...origin], label: preset ? preset.origin.label : endpointLabel("origin"), place_id: preset ? null : st.endpointPlaces.origin && st.endpointPlaces.origin.id },
    destination: { coordinates: [...destination], label: preset ? preset.destination.label : endpointLabel("destination"), place_id: preset ? null : st.endpointPlaces.destination && st.endpointPlaces.destination.id },
    saved_at: new Date().toISOString(),
  };
  if (writeSavedJourneys([...st.savedJourneys, journey])) {
    $("saved-journey-name").value = "";
    savedJourneyError(`Saved “${name}” in this browser.`);
    renderSavedJourneys();
    refreshJourneyAlerts();
  }
}

function renderMonitorScenario(message) {
  const scenario = st.monitorScenario;
  $("restore-monitor-scenario").hidden = !scenario;
  $("delete-monitor-scenario").hidden = !scenario && !st.invalidMonitorScenario;
  $("monitor-scenario-status").textContent = message || (scenario
    ? `Saved user-confirmed simulation: ${scenario.request.projects[0].start_date} to ${scenario.request.projects[0].end_date}. Source footpath dates are unknown.`
    : "No scenario saved in this browser.");
}

function loadMonitorScenario() {
  try {
    const raw = localStorage.getItem(MONITOR_SCENARIO_KEY);
    if (!raw) return renderMonitorScenario();
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.version !== 1 || !parsed.scenario
        || !parsed.scenario.request || !Array.isArray(parsed.scenario.request.projects)
        || !parsed.scenario.request.projects[0]) throw new Error("invalid");
    st.monitorScenario = parsed.scenario;
    renderMonitorScenario();
  } catch (e) {
    st.invalidMonitorScenario = true;
    renderMonitorScenario("Saved scenario could not be loaded. Delete invalid data before saving another.");
  }
}

async function saveMonitorScenario() {
  if (st.invalidMonitorScenario) {
    renderMonitorScenario("Delete invalid saved scenario data before saving another.");
    return;
  }
  try {
    const request = payload(false);
    delete request.custom_journey;
    const scenario = await api("/api/monitor-scenario", request);
    localStorage.setItem(MONITOR_SCENARIO_KEY, JSON.stringify({ version: 1, scenario }));
    st.monitorScenario = scenario;
    renderMonitorScenario("Confirmed simulation saved in this browser. Notice footpath dates remain unknown.");
    await refreshJourneyAlerts();
  } catch (e) {
    renderMonitorScenario(`Scenario not saved: ${e.message}`);
  }
}

async function restoreMonitorScenario() {
  const scenario = st.monitorScenario;
  if (!scenario) return false;
  try {
    // Validate the persisted record before restoring its confirmation.
    await api("/api/journey-alerts", { saved_journeys: [], previous_projects: [], monitor_scenario: scenario });
    await loadKoigenDemo();
    if (st.caseId !== "koigen-demo") throw new Error("Koigen case could not be loaded.");
    const request = scenario.request, project = request.projects[0];
    $("assess-date").value = request.assessment_date;
    st.projects = [{ uid: st.nextProject++, name: project.name, start: project.start_date,
      end: project.end_date, sections: new Set(project.sections) }];
    st.modeledConfirmed = true;
    $("confirm-koigen-model").checked = true;
    renderProjects(); syncAssessmentGate();
    renderMonitorScenario("Saved confirmation restored. Select Assess projects for a fresh calculation.");
    return true;
  } catch (e) {
    renderMonitorScenario(`Scenario could not be restored: ${e.message}`);
    return false;
  }
}

function deleteMonitorScenario() {
  try {
    localStorage.removeItem(MONITOR_SCENARIO_KEY);
    st.monitorScenario = null;
    st.invalidMonitorScenario = false;
    renderMonitorScenario("Saved scenario removed from this browser.");
    refreshJourneyAlerts();
  } catch (e) {
    renderMonitorScenario("This browser could not remove the saved scenario.");
  }
}

async function restoreSavedJourney(id) {
  const journey = st.savedJourneys.find((item) => item.id === id);
  if (!journey) {
    savedJourneyError("That saved journey is no longer available.");
    return;
  }
  setBusy("Restoring saved walking endpoints…");
  try {
    if (journey.case_id === "koigen-demo" && st.monitorScenario) {
      if (!await restoreMonitorScenario()) {
        savedJourneyError("The saved Koigen scenario could not be restored; review its error.");
        return;
      }
    } else if (!await loadCase(journey.case_id)) return;
    $("case-select").value = st.caseId;
    st.custom.origin = [...journey.origin.coordinates];
    st.custom.destination = [...journey.destination.coordinates];
    st.endpointLabels = { origin: journey.origin.label, destination: journey.destination.label };
    st.endpointPlaces = { origin: null, destination: null };
    $("place-from").value = journey.origin.label;
    $("place-to").value = journey.destination.label;
    selectCustom(); syncCoordInputs();
    await resolveCustom();
    if (!st.customInfo || st.customInfo.status !== "ready") {
      savedJourneyError(`Restored “${journey.name}”, but ${st.customInfo ? st.customInfo.message : "the endpoints could not be resolved."}`);
      return;
    }
    await assess();
    if (st.assessment && !st.assessStale) {
      savedJourneyError(`Restored “${journey.name}” and calculated a fresh assessment.`);
    } else {
      savedJourneyError(`Restored “${journey.name}”, but the fresh assessment failed; review the error above.`);
    }
  } catch (e) {
    savedJourneyError(e.message);
  } finally {
    setBusy("");
  }
}

function deleteSavedJourney(id) {
  const deleted = st.savedJourneys.find((item) => item.id === id);
  if (!deleted) {
    savedJourneyError("That saved journey is no longer available.");
    return;
  }
  if (writeSavedJourneys(st.savedJourneys.filter((item) => item.id !== id))) {
    savedJourneyError(`Deleted “${deleted.name}” from this browser.`);
    renderSavedJourneys();
    refreshJourneyAlerts();
  }
}

function loadAlertState() {
  try {
    const raw = localStorage.getItem(JOURNEY_ALERT_STATE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.version !== 1
        || !Array.isArray(parsed.dismissed_alerts)
        || parsed.dismissed_alerts.length > 200
        || parsed.dismissed_alerts.some((item) => typeof item !== "string")
        || (parsed.snapshot && (!parsed.snapshot.projects || !Array.isArray(parsed.snapshot.projects)))) {
      throw new Error("invalid");
    }
    st.dismissedJourneyAlerts = parsed.dismissed_alerts;
    st.readJourneyAlerts = Array.isArray(parsed.read_alerts)
      ? parsed.read_alerts.filter((id) => typeof id === "string") : [];
    st.alertSnapshot = parsed.snapshot || null;
  } catch (e) {
    $("journey-alert-status").textContent =
      "Saved alert state is invalid and was not loaded. Refresh will replace it with current saved project data.";
    st.dismissedJourneyAlerts = [];
    st.alertSnapshot = null;
  }
}

function saveAlertState(snapshot) {
  st.alertSnapshot = snapshot || st.alertSnapshot;
  try {
    localStorage.setItem(JOURNEY_ALERT_STATE_KEY, JSON.stringify({
      version: 1,
      dismissed_alerts: st.dismissedJourneyAlerts,
      read_alerts: st.readJourneyAlerts,
      snapshot: st.alertSnapshot,
    }));
    return true;
  } catch (e) {
    $("journey-alert-status").textContent =
      "The alert check completed, but browser-local alert state could not be saved.";
    return false;
  }
}

function alertLabel(kind) {
  return {
    approaching_works: "Approaching works",
    active_impact: "Active route impact",
    dates_changed: "Project dates changed",
    reopening_confirmed: "Reopening confirmed",
    reopening_unconfirmed: "Scheduled end passed",
  }[kind] || kind;
}

function readableDate(value, withTime = false) {
  const date = new Date(withTime ? value : value + "T12:00:00");
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric", month: "short", year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

function journeyAlertCard(alert, dismissed = false) {
  const source = alert.source;
  const effect = alert.route_effect;
  const simulated = alert.user_confirmed_simulation;
  let headline = alertLabel(alert.kind);
  if (effect && alert.kind === "active_impact") {
    headline = effect.status === "unreachable"
      ? "No mapped route during works"
      : effect.change_metres > 0
        ? `${metres(effect.change_metres)} extra on your walk`
        : "Your walking route changes";
  } else if (alert.kind === "dates_changed") {
    headline = `Works dates updated · ends ${readableDate(alert.end_date)}`;
  } else if (alert.kind === "approaching_works") {
    headline = `Works start ${readableDate(alert.start_date)}`;
  } else if (simulated && alert.kind === "reopening_unconfirmed") {
    headline = "Simulation period ended";
  }
  const phase = alert.kind === "approaching_works" ? "Expected modeled route"
    : alert.kind === "active_impact" ? "Modeled route" : "Previously modeled route";
  const routeText = effect
    ? effect.status === "unreachable"
      ? `${phase}: ${metres(effect.baseline_metres)} baseline; destination becomes unreachable.`
      : `${phase}: ${metres(effect.baseline_metres)} → ${metres(effect.metres)}.`
    : "";
  const realSource = /^https?:\/\//i.test(source.project_source_url)
    && !new URL(source.project_source_url).hostname.endsWith(".invalid");
  const sourceLabel = realSource
    ? el("a", { href: source.project_source_url, target: "_blank", rel: "noopener noreferrer" }, source.project_source_label)
    : el("span", {}, source.project_source_label);
  return el("article", {
    class: `card alert-card compact-alert ${alert.kind === "reopening_confirmed" ? "confirmed" : ""} ${alert.synthetic ? "synthetic" : ""}`,
  },
  el("div", { class: "card-title" },
    el("h3", {}, headline),
    pill(simulated ? "User-confirmed simulation" : alert.synthetic ? "Synthetic project" : "Saved project",
      alert.synthetic ? "pill-warn" : "pill-ok"),
    pill(st.readJourneyAlerts.includes(alert.id) ? "Read" : "Unread")),
  el("p", { class: "alert-journey" }, alert.journey_name),
  routeText ? el("p", { class: "alert-route" }, routeText) : null,
  alert.kind === "reopening_unconfirmed"
    ? el("p", { class: "hint" }, "Scheduled end passed; reopening unconfirmed.") : null,
  el("p", { class: "hint" }, alert.project_label),
  el("details", { class: "alert-details" },
    el("summary", {}, "Source and assessment details"),
    el("p", {}, alert.message),
    el("p", {}, `${simulated ? "User-selected simulation dates" : "Project dates"}: ${readableDate(alert.start_date)} – ${readableDate(alert.end_date)}.`),
    simulated ? el("p", { class: "hint" }, "The notice leaves the exact footpath dates and closure extent unknown. These dates belong to the simulation.") : null,
    el("p", { class: "alert-meta" }, "Source: ", sourceLabel),
    el("p", { class: "alert-meta" }, `Last assessment: ${readableDate(alert.checked_at, true)}. Saved data: ${source.snapshot_file}.`),
    source.excerpt ? el("blockquote", {}, source.excerpt) : null),
  el("div", { class: "notification-actions" },
    !dismissed && !st.readJourneyAlerts.includes(alert.id)
      ? el("button", { type: "button", class: "btn btn-small", "data-read-alert": alert.id }, "Mark as read") : null,
    el("button", { type: "button", class: "btn btn-small",
      [dismissed ? "data-restore-alert" : "data-dismiss-alert"]: alert.id },
      dismissed ? "Restore alert" : "Dismiss")));
}

function renderJourneyAlerts() {
  const host = $("journey-alerts");
  const visible = st.journeyAlerts.filter(
    (alert) => !st.dismissedJourneyAlerts.includes(alert.id)
  );
  const dismissed = st.journeyAlerts.filter(
    (alert) => st.dismissedJourneyAlerts.includes(alert.id)
  );
  if (!visible.length && !dismissed.length) {
    host.replaceChildren();
    host.hidden = true;
    return;
  }
  host.hidden = false;
  host.replaceChildren(
    el("p", { class: "hint" }, "Checks occur when the app opens or when you refresh; there is no continuous monitoring."),
    ...visible.map((alert) => journeyAlertCard(alert)),
    ...(dismissed.length ? [el("details", { class: "dismissed-alerts alert-details" },
      el("summary", {}, `Show dismissed alerts (${dismissed.length})`),
      ...dismissed.map((alert) => journeyAlertCard(alert, true)))] : []),
  );
}

async function refreshJourneyAlerts() {
  const status = $("journey-alert-status");
  const seq = ++st.alertSeq;
  if (!st.savedJourneys.length) {
    $("alert-check-details")?.remove();
    st.journeyAlerts = [];
    status.textContent = "No saved walking journeys to check.";
    renderJourneyAlerts();
    return;
  }
  status.textContent = "Checking saved local project records…";
  try {
    const result = await api("/api/journey-alerts", {
      saved_journeys: st.savedJourneys,
      previous_projects: st.alertSnapshot && st.alertSnapshot.projects
        ? st.alertSnapshot.projects : [],
      monitor_scenario: st.monitorScenario,
    });
    if (seq !== st.alertSeq) return;
    st.journeyAlerts = result.alerts;
    st.alertSnapshot = result.snapshot;
    saveAlertState(result.snapshot);
    const unavailable = result.unavailable || [];
    $("alert-check-details")?.remove();
    const visibleCount = result.alerts.filter((alert) => !st.dismissedJourneyAlerts.includes(alert.id)).length;
    status.textContent = `${visibleCount} visible alert(s). Checked ${readableDate(result.checked_at, true)}.`;
    if (unavailable.length) {
      const grouped = new Map();
      for (const item of unavailable) {
        const key = `${item.kind}:${item.message}`;
        if (!grouped.has(key)) grouped.set(key, { message: item.message, journeys: new Set() });
        grouped.get(key).journeys.add(item.journey_name || item.journey_id || "Saved journey");
      }
      status.after(el("details", { id: "alert-check-details", class: "alert-details" },
        el("summary", {}, `${grouped.size} distinct data issue(s) across ${unavailable.length} checks`),
        el("ul", {}, ...Array.from(grouped.values(), (item) => el("li", {}, item.message,
          el("span", { class: "hint" }, ` Affected journeys: ${Array.from(item.journeys).join(", ")}.`))))));
    }
    renderJourneyAlerts();
  } catch (e) {
    if (seq !== st.alertSeq) return;
    st.journeyAlerts = [];
    $("alert-check-details")?.remove();
    status.textContent = `Project data unavailable: ${e.message}`;
    renderJourneyAlerts();
  }
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
  if (!active && isDriving()) $("walking-ai").hidden = true;
  $("load-bus").hidden = false;
  $("published-bus-picker").hidden = false;
  $("bus-controls").hidden = !active;
  $("diagnostics").hidden = active;
  $("map-help").textContent = active
    ? "Drag to pan. With the map focused: arrow keys pan, + and − zoom, 0 fits the journey. Ctrl + wheel zooms."
    : isDriving() ? "Drag to pan. With the map focused: arrow keys pan, + and − zoom, 0 fits the journey. Ctrl + wheel zooms."
      : "Drag to pan. With the map focused: arrow keys pan, + and − zoom, 0 fits the journey. Ctrl + wheel zooms. To set a start or destination, press its button, then click the map.";
  $("mode-badge").textContent = active ? `${st.bus.scenario.synthetic ? "Synthetic" : `Dated ${st.bus.scenario.service}`} bus scenario · walking access` : "Walking and driving supported";
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
      : "Approximate platform connections: distances end at nearby snapped map nodes, not the quay. Physical connections and accessibility are unverified; offsets are excluded. Outside-map stops are unassessed. Bus delay unknown.";
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
  st.catalogue = null;
  st.bus = null;
  setBusView(false); showError("");
  applyStale(); drawMap(); renderEvidence(); renderDiagnostics();
  fitBox(journeyBox(), 0.25);
  syncWorkspace();
}

async function loadCase(id) {
  st.catalogue = null;
  clearTimeout(st.timer); st.seq++;
  setBusy("Loading saved map…");
  try {
    st.data = await api(`/api/cases/${encodeURIComponent(id)}`);
    st.caseId = id;
    $("case-select").value = id;
    st.assessment = null; st.compare = null; st.assessStale = false; st.compareStale = false;
    st.noticeDraft = null; st.modeledConfirmed = false;
    $("confirm-koigen-model").checked = false;
    syncAssessmentGate();
    st.custom = { origin: null, destination: null }; st.customInfo = null; st.customSeq++;
    st.endpointLabels = { origin: null, destination: null };
    st.endpointPlaces = { origin: null, destination: null };
    for (const side of ["origin", "destination"]) {
      clearTimeout(st.placeTimer[side]); st.placeSeq[side]++;
      st.placeMatches[side] = [];
      const field = side === "origin" ? "place-from" : "place-to";
      $(field).value = ""; $(`${field}-results`).replaceChildren(); $(`${field}-status`).textContent = "";
    }
    setPick(null); syncCoordInputs();
    $("custom-journey").hidden = isDriving();
    $("place-search-scope").textContent = isDriving()
      ? ""
      : `Walking scope: ${st.data.label}. Address search uses Kartverket for Hamar municipality; bus stops and named places use saved data. Address and street selection use the Hamar municipal walking network. A mapped public connection is needed near each endpoint.`;
    renderSavedJourneys();
    $("walking-ai").hidden = isDriving();
    $("compare-btn").disabled = st.data.candidates.length < 3;
    $("ai-note").textContent = st.data.candidates.length < 3
      ? "No AI comparison is available for this case: fewer than three modeled mitigation candidates are configured."
      : `Runs one request to ${st.index.ai.model} on this computer (${st.index.ai.timeout_seconds} s limit). Needs Ollama to be running; the assessment above does not. AI comparison applies only to the preset journeys, not to your own journey.`;
    $("diagnostics").hidden = isDriving();
    $("map-help").textContent = isDriving()
      ? "Drag to pan. With the map focused: arrow keys pan, + and − zoom, 0 fits the journey. Ctrl + wheel zooms."
      : "Drag to pan. With the map focused: arrow keys pan, + and − zoom, 0 fits the journey. Ctrl + wheel zooms. To set a start or destination, press its button, then click the map.";
    buildProjection();
    $("case-summary").textContent = st.data.summary;
    $("coverage-note").textContent = coverageText();
    const js = $("journey-select");
    js.replaceChildren(...st.data.journeys.map((j) => el("option", { value: j.id }, j.label)),
      ...(isDriving() ? [] : [el("option", { value: CUSTOM }, "Your own journey (choose on map)")]));
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
  $("ringgata-demo-controls").hidden = false;
  $("koigen-demo-controls").hidden = true;
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
    st.endpointLabels = {origin: start.origin.label, destination: end.destination.label};
    $("place-from").value = start.origin.label; $("place-to").value = end.destination.label;
    $("demo-closures").value = "none";
    $("demo-controls").hidden = false; $("demo-settings").open = true;
    await updateDemo();
  } catch (e) {
    showError(e.message);
  } finally {
    st.demoBusy = false; $("plan-fields").disabled = st.busy; syncAssessmentGate(); syncWorkspace();
  }
}

async function loadKoigenDemo() {
  st.demoBusy = true; $("plan-fields").disabled = true;
  $("demo-controls").hidden = true;
  showError("");
  try {
    st.layers = Object.fromEntries(LAYERS.map((layer) => [layer.key, true]));
    if (!await loadCase("koigen-demo")) return;
    $("case-select").value = st.caseId;
    const section = st.data.sections.find((s) => s.id === "koigen-candidate-closure" && s.modeled);
    const journey = st.data.journeys.find((j) => j.id === "koigen-footpath-candidate");
    if (!section || !journey || journey.origin.id !== "302372908" || journey.destination.id !== "1023215093") {
      throw new Error("The modeled Koigen candidate section or journey is unavailable.");
    }
    const source = st.data.evidence.planning_source;
    if (!source) throw new Error("The Hamar municipality notice link is unavailable.");
    $("koigen-source-link").replaceChildren(el("a", {
      href: source, target: "_blank", rel: "noopener noreferrer",
    }, st.data.evidence.planning_source_label || "Hamar municipality notice"));
    const day = st.index.today;
    $("assess-date").value = day;
    st.projects = [{
      uid: st.nextProject++,
      name: "Modeled Koigen candidate closure (dates unknown)",
      start: day,
      end: day,
      sections: new Set([section.id]),
    }];
    renderProjects();
    $("ringgata-demo-controls").hidden = true;
    $("koigen-demo-controls").hidden = false;
    $("demo-controls").hidden = false; $("demo-settings").open = true;
    syncAssessmentGate();
    renderResults();
    fitBox(journeyBox(), 0.25);
  } catch (e) {
    showError(e.message);
  } finally {
    st.demoBusy = false; $("plan-fields").disabled = st.busy; syncAssessmentGate(); syncWorkspace();
  }
}

async function init() {
  prepareWorkspace();
  try {
    st.index = await api("/api/cases");
  } catch (e) { $("map-caption").textContent = e.message; return; }
  $("assess-date").value = st.index.today;
  $("date-rule").textContent = "Start and end dates are inclusive.";
  $("ai-note").textContent = `Runs one request to ${st.index.ai.model} on this computer (${st.index.ai.timeout_seconds} s limit). Needs Ollama to be running; the assessment above does not. AI comparison applies only to the preset journeys, not to your own journey.`;
  $("mode-badge").textContent = "Walking and driving supported";
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
  $("load-koigen-demo").addEventListener("click", loadKoigenDemo);
  $("draft-koigen-notice").addEventListener("click", draftFromNotice);
  $("confirm-koigen-model").addEventListener("change", (e) => {
    st.modeledConfirmed = e.target.checked;
    syncAssessmentGate();
    if (st.assessment) {
      st.assessStale = true;
      st.compareStale = Boolean(st.compare);
      applyStale();
      drawMap();
    }
  });
  $("demo-closures").addEventListener("change", updateDemo);
  $("case-select").addEventListener("change", (e) => { $("demo-controls").hidden = true; loadCase(e.target.value); });
  $("journey-select").addEventListener("change", (e) => { $("demo-controls").hidden = true; st.journeyId = e.target.value; drawMap(); renderResults(); fitBox(journeyBox(), 0.25); });
  $("pick-start").addEventListener("click", () => { $("demo-controls").hidden = true; selectCustom(); setPick("origin"); drawMap(); renderResults(); });
  $("pick-dest").addEventListener("click", () => { $("demo-controls").hidden = true; selectCustom(); setPick("destination"); drawMap(); renderResults(); });
  $("clear-custom").addEventListener("click", clearCustom);
  $("apply-coords").addEventListener("click", applyCoords);
  for (const side of ["origin", "destination"]) {
    const id = side === "origin" ? "place-from" : "place-to";
    $(id).addEventListener("input", () => {
      clearTimeout(st.placeTimer[side]);
      st.placeSeq[side]++;
      st.placeMatches[side] = [];
      $(side === "origin" ? "place-from-results" : "place-to-results").replaceChildren();
      if (st.custom[side]) {
        st.custom[side] = null; st.customInfo = null; st.endpointPlaces[side] = null;
        selectCustom(); inputsChanged(); drawMap(); renderResults();
      }
      st.placeTimer[side] = setTimeout(() => searchPlaces(side), 400);
    });
    $(id).addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        searchPlaces(side);
      }
    });
    $(side === "origin" ? "place-from-results" : "place-to-results")
      .addEventListener("click", (e) => {
        const button = e.target.closest && e.target.closest("[data-place-id]");
        if (button) choosePlace(button.getAttribute("data-place-side"), button.getAttribute("data-place-id"));
      });
  }
  $("save-journey").addEventListener("click", saveSelectedJourney);
  $("save-monitor-scenario").addEventListener("click", saveMonitorScenario);
  $("restore-monitor-scenario").addEventListener("click", restoreMonitorScenario);
  $("delete-monitor-scenario").addEventListener("click", deleteMonitorScenario);
  $("saved-journey-list").addEventListener("click", (e) => {
    const restore = e.target.closest && e.target.closest("[data-restore-saved]");
    if (restore) return restoreSavedJourney(restore.getAttribute("data-restore-saved"));
    const remove = e.target.closest && e.target.closest("[data-delete-saved]");
    if (remove) deleteSavedJourney(remove.getAttribute("data-delete-saved"));
  });
  $("discard-saved-data").addEventListener("click", () => {
    try {
      localStorage.removeItem(SAVED_JOURNEYS_KEY);
      st.savedJourneys = [];
      st.invalidSavedData = false;
      $("discard-saved-data").hidden = true;
      savedJourneyError("Invalid saved data was discarded.");
      renderSavedJourneys();
    } catch (e) {
      savedJourneyError("This browser could not remove the invalid saved data.");
    }
  });
  $("refresh-journey-alerts").addEventListener("click", refreshJourneyAlerts);
  $("journey-alerts").addEventListener("click", (e) => {
    const read = e.target.closest("[data-read-alert]");
    if (read) {
      st.readJourneyAlerts.push(read.dataset.readAlert);
      saveAlertState();
      renderJourneyAlerts();
      return;
    }
    const restore = e.target.closest && e.target.closest("[data-restore-alert]");
    if (restore) {
      const id = restore.getAttribute("data-restore-alert");
      st.dismissedJourneyAlerts = st.dismissedJourneyAlerts.filter((item) => item !== id);
      saveAlertState();
      renderJourneyAlerts();
      return;
    }
    const button = e.target.closest && e.target.closest("[data-dismiss-alert]");
    if (!button) return;
    const id = button.getAttribute("data-dismiss-alert");
    if (!st.dismissedJourneyAlerts.includes(id)) {
      st.dismissedJourneyAlerts.push(id);
    }
    saveAlertState();
    renderJourneyAlerts();
  });
  loadAlertState();
  loadSavedJourneys();
  loadMonitorScenario();
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
  frame.addEventListener("pointerdown", (e) => { if (window.hamarGeo?.active || e.target.closest("button")) return; drag = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, moved: false }; frame.setPointerCapture(e.pointerId); });
  frame.addEventListener("pointermove", (e) => {
    if (window.hamarGeo?.active || !drag) return;
    if (Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 4) drag.moved = true;
    if (st.pick && !drag.moved) return;
    const rect = frame.getBoundingClientRect(), s = Math.max(st.view.w / rect.width, st.view.h / rect.height);
    st.view.x -= (e.clientX - drag.x) * s; st.view.y -= (e.clientY - drag.y) * s; drag = { ...drag, x: e.clientX, y: e.clientY }; applyView();
  });
  frame.addEventListener("pointerup", (e) => {
    if(window.hamarGeo?.active)return;
    const finished = drag;
    drag = null;
    if (finished && !finished.moved && st.pick) { const [lat, lon] = mapPoint(e); setPoint(st.pick, lat, lon); }
  });
  frame.addEventListener("wheel", (e) => { if(window.hamarGeo?.active)return; if (e.ctrlKey) { e.preventDefault(); zoom(e.deltaY < 0 ? 1.15 : 0.87); } }, { passive: false });
  window.addEventListener("resize", () => { if (st.data) fitBox(journeyBox(), 0.25); });
  await loadCase("hamar-municipality");
  selectCustom(); drawMap(); renderResults();
  $("demo-settings").open = false;
  await refreshJourneyAlerts();
  syncWorkspace();
}
window.hamarNotificationSupport = { $, el, pill, api, refreshJourneyAlerts };
init();
})();

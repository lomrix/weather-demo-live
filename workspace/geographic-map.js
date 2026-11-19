import * as maplibregl from '/vendor/maplibre/maplibre-gl.mjs';

maplibregl.setWorkerUrl('/vendor/maplibre/maplibre-gl-worker.mjs');
const $ = (id) => document.getElementById(id);
const frame = $('map-frame');
let map, latest = window.__hamarMapPayload || null, active = false, offline = false, threeD = false, lastCase = null;
let timeout, applied = null, ready = false;
const styles = {light: 'https://tiles.openfreemap.org/styles/liberty', dark: 'https://tiles.openfreemap.org/styles/dark'};
const colour = {coverage:'#64788b',baseline:'#4c8eff',route:'#f59c35',closure:'#ec5359',inactive:'#e9959b',opt1:'#a584ed',opt2:'#36c4c2',markers:'#102d40'};
function status(text) { $('geographic-status').textContent = text; }
function fallback(message) {
  active = false; frame.classList.remove('geo-active');
  status(message || 'Saved map · offline');
}
function setActive() {
  if (offline) return;
  active = true; frame.classList.add('geo-active');
  clearTimeout(timeout);
  status(threeD ? '3D buildings · online context' : 'Street map · online context');
}
function prepareBasemap() {
  if(document.documentElement.dataset.theme==='dark'){
    for(const layer of map.getStyle().layers){
      const id=layer.id;
      if(layer.type==='background')map.setPaintProperty(id,'background-color','#102032');
      if(layer.type==='fill')map.setPaintProperty(id,'fill-color',/water/.test(id)?'#173c56':/park|wood|grass|forest/.test(id)?'#183b36':/building/.test(id)?'#2c435d':'#14283c');
      if(layer.type==='line'&&/road|highway|transportation/.test(id))map.setPaintProperty(id,'line-color',/casing|outline/.test(id)?'#263a52':'#69809c');
      if(layer.type==='symbol'&&layer.layout?.['text-field']){
        map.setPaintProperty(id,'text-color','#becfe4');map.setPaintProperty(id,'text-halo-color','#102032');map.setPaintProperty(id,'text-halo-width',1.2);
      }
      if(layer.type==='fill-extrusion')map.setPaintProperty(id,'fill-extrusion-color','#42617e');
    }
  }
  if(map.getLayer('building-3d'))map.setLayerZoomRange('building-3d',13,24);
  if(!map.getLayer('building-3d')&&map.getSource('openmaptiles'))map.addLayer({id:'building-3d',type:'fill-extrusion',source:'openmaptiles','source-layer':'building',minzoom:13,
    layout:{visibility:threeD?'visible':'none'},paint:{'fill-extrusion-color':document.documentElement.dataset.theme==='dark'?'#42617e':'#c9c7c0','fill-extrusion-height':['coalesce',['get','render_height'],3],'fill-extrusion-base':['coalesce',['get','render_min_height'],0],'fill-extrusion-opacity':.85}});
}
function applyOverlays() {
  if (!map || !map.isStyleLoaded() || !latest) return;
  if (!map.getSource('hamar-routes')) {
    map.addSource('hamar-routes', {type:'geojson',data:latest.data});
    for (const kind of ['coverage','inactive','baseline','route','opt1','opt2','closure']) {
      map.addLayer({id:'hamar-'+kind,type:'line',source:'hamar-routes',filter:['==',['get','kind'],kind],
        layout:{'line-cap':'round','line-join':'round'},
        paint:{'line-color':colour[kind],'line-width':kind==='coverage'?1.3:kind==='baseline'?8:kind==='closure'?7:5,
          'line-opacity':kind==='baseline'?.65:1,...(['route','coverage'].includes(kind)?{'line-dasharray':[2,1.3]}:{})}});
    }
    map.addLayer({id:'hamar-markers',type:'circle',source:'hamar-routes',filter:['==',['get','kind'],'marker'],
      paint:{'circle-color':['get','colour'],'circle-radius':7,'circle-stroke-width':3,'circle-stroke-color':'#ffffff'}});
    map.addLayer({id:'hamar-labels',type:'symbol',source:'hamar-routes',filter:['==',['get','kind'],'marker'],
      layout:{'text-field':['case',['==',['get','label'],'A · Start'],window.hamarPreferences?.language==='nb'?'A · Start':'A · Start',['==',['get','label'],'B · Destination'],window.hamarPreferences?.language==='nb'?'B · Mål':'B · Destination',['get','label']],'text-size':12,'text-anchor':'bottom','text-offset':[0,-1.2],'text-font':['Noto Sans Regular'],'text-allow-overlap':true},
      paint:{'text-color':document.documentElement.dataset.theme==='dark'?'#e8f2fa':'#173349','text-halo-color':document.documentElement.dataset.theme==='dark'?'#142433':'#ffffff','text-halo-width':2}});
    applied=latest;
  } else if(applied!==latest){map.getSource('hamar-routes').setData(latest.data);applied=latest;}
  const building = map.getLayer('building-3d');
  if (building && map.getLayoutProperty('building-3d','visibility') !== (threeD?'visible':'none')) map.setLayoutProperty('building-3d','visibility',threeD?'visible':'none');
  if (latest.caseId !== lastCase) { fit(latest.bounds); lastCase = latest.caseId; }
}
function fit(bounds) {
  if (!active || !map || !bounds) return;
  map.fitBounds(bounds,{padding:55,duration:0,maxZoom:17,pitch:threeD?50:0,bearing:threeD?-15:0});
}
function start() {
  if (map) { offline = false; map.resize(); if(map.isStyleLoaded()){setActive();applyOverlays();fit(latest?.bounds);} return; }
  status('Loading geographic map…');
  try {
    map = new maplibregl.Map({container:'geographic-map',style:styles[document.documentElement.dataset.theme==='dark'?'dark':'light'],
      center:[11.069,60.800],zoom:13.5,maxPitch:65,cooperativeGestures:true,attributionControl:true,
      canvasContextAttributes:{antialias:true}});
    map.addControl(new maplibregl.NavigationControl({showZoom:false,visualizePitch:true}),'top-right');
    map.on('idle',()=>{if(!offline){applyOverlays();ready=Boolean(map.getSource('hamar-routes'));frame.dataset.geoReady=String(ready);}});
    map.on('load',()=>{setActive();applyOverlays();fit(latest?.bounds);});
    map.on('style.load',()=>{prepareBasemap();applyOverlays();if(!offline){setActive();fit(latest?.bounds);}});
    map.on('error',()=>{if(!map.isStyleLoaded()) fallback('Online map unavailable · saved map shown');});
    map.on('click',(event)=>window.dispatchEvent(new CustomEvent('hamar-map-pick',{detail:[event.lngLat.lat,event.lngLat.lng]})));
    timeout = setTimeout(()=>{if(!active)fallback('Online map unavailable · saved map shown');},9000);
  } catch { fallback('3D map unavailable · saved map shown'); }
}
window.hamarGeo = {
  get active(){return active;}, fit,
  get stats(){return !map?{}:{ready,styleName:map.getStyle().name,loaded:map.isStyleLoaded(),zoom:map.getZoom(),pitch:map.getPitch(),routeFeatures:map.getLayer('hamar-route')?map.queryRenderedFeatures({layers:['hamar-route']}).length:0,buildings:map.getLayer('building-3d')?map.queryRenderedFeatures({layers:['building-3d']}).length:0};},
  zoomBy(factor){if(active)map.zoomTo(map.getZoom()+Math.log2(factor),{duration:150});},
  pan(dx,dy){if(active)map.panBy([dx*frame.clientWidth,dy*frame.clientHeight],{duration:0});},
  sync(payload){latest=payload;if(active)applyOverlays();},
};
window.addEventListener('hamar-map-update',(event)=>{latest=event.detail;if(active)applyOverlays();});
window.addEventListener('hamar-theme',()=>{
  if(map&&!offline){ready=false;lastCase=null;map.setStyle(styles[document.documentElement.dataset.theme==='dark'?'dark':'light']);}
});
window.addEventListener('hamar-language',()=>{if(map?.getLayer('hamar-labels'))map.setLayoutProperty('hamar-labels','text-field',['case',['==',['get','label'],'B · Destination'],window.hamarPreferences.language==='nb'?'B · Mål':'B · Destination',['get','label']]);});
window.addEventListener('resize',()=>{if(map)map.resize();});
$('map-style').addEventListener('change',(event)=>{
  const choice=event.target.value;
  offline=choice==='offline';threeD=choice==='3d';
  if(offline){fallback();return;}
  start();if(active){applyOverlays();map.easeTo({pitch:threeD?50:0,bearing:threeD?-15:0,duration:500});status(threeD?'3D buildings · online context':'Street map · online context');}
});
start();

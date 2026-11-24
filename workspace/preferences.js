"use strict";
(() => {
  const key='hamar-access-lab.preferences.v1';
  let preferences={language:'en',theme:'light'};
  try {const saved=JSON.parse(localStorage.getItem(key));if(saved?.language==='nb')preferences.language='nb';if(['light','dark'].includes(saved?.theme))preferences.theme=saved.theme;} catch {}
  const dictionary={
    "Source summary":"Sammendrag av kilden","Source quotation":"Sitat fra kilden","Source note":"Kildemerknad",
    'Notifications':'Varsler','Notification centre':'Varslingssenter',
    'Close notifications':'Lukk varsler','Follow updates in this browser':'Følg oppdateringer i denne nettleseren',
    'Hamar-area updates':'Oppdateringer for Hamar','My journeys':'Mine reiser',
    'Refresh saved updates':'Oppdater lagrede varsler','Dismissed updates':'Skjulte varsler',
    'Simulation examples':'Simuleringseksempler','Simulation':'Simulering',
    'Selected saved notices for Hamar. Coverage is partial. Updates are available inside this app.':'Utvalgte lagrede varsler for Hamar. Dekningen er begrenset. Oppdateringene vises i appen.',
    'Route effects are calculated for supported saved walking journeys.':'Rutevirkninger beregnes for lagrede gangreiser som støttes.',
    'Source evidence':'Kildegrunnlag','Source last checked':'Kilde sist kontrollert',
    'Hamar municipality':'Hamar kommune','Saved simulation fixture':'Lagret simuleringsgrunnlag',
    'Scheduled works':'Planlagt arbeid','Upcoming works':'Kommende arbeid',
    'Reported works start':'Meldt oppstart','Announced closure':'Varslet stenging',
    'Reported active closure':'Meldt pågående stenging','Reopening confirmed':'Gjenåpning bekreftet',
    'Scheduled end passed; reopening unconfirmed.':'Planlagt sluttdato er passert. Gjenåpning er ubekreftet.',
    'Dates changed':'Endrede datoer','Planned period':'Planlagt periode',
    'Closure dates unspecified':'Stengningsdatoer er ikke oppgitt',
    'Previous planned period':'Tidligere planlagt periode','Travel modes unspecified':'Reisemåter ikke oppgitt',
    'Route impact unmodeled':'Rutevirkning er ikke modellert','Read':'Lest','Unread':'Ulest',
    'Mark as read':'Merk som lest','Restore update':'Vis varselet igjen',
    'Loading saved notices…':'Laster lagrede varsler…','No visible Hamar-area notices.':'Ingen synlige varsler for Hamar.',
    'Saved notices unavailable. Any displayed notices are from the previous load.':'Lagrede varsler er utilgjengelige. Eventuelle viste varsler er fra forrige innlasting.',
    'Browser notification preferences could not be loaded.':'Varslingsinnstillingene kunne ikke lastes.',
    'Browser notification preferences could not be saved.':'Varslingsinnstillingene kunne ikke lagres.',
    'Explore Hamar buses':'Utforsk busstilbudet i Hamar',
    'Search imported bus lines and route variants, or compare walking access in the saved closure examples.':'Søk i importerte busslinjer og rutevarianter, eller sammenlign gangtilgangen i de lagrede stengningseksemplene.',

    'Explore Hamar bus lines':'Utforsk busslinjer i Hamar','Loading imported bus services…':'Laster importerte busslinjer…',
    'Search line or destination':'Søk etter linje eller reisemål','Line number or destination':'Linjenummer eller reisemål','Bus line':'Busslinje',
    'Direction and route variant':'Retning og rutevariant','Show bus route':'Vis bussrute','Ordered stops':'Holdeplasser i rekkefølge',
    'Stops in Hamar':'Holdeplasser i Hamar','Scheduled journeys':'Planlagte avganger','Published bus route':'Publisert bussrute',
    'Saved timetable snapshot':'Lagret rutedatasnapshot','No matching bus lines.':'Fant ingen busslinjer.',
    'Entur source and attribution':'Entur-kilde og kreditering','Route-variant data unavailable for this line.':'Rutevariantdata er utilgjengelig for denne linjen.',
    'Imported Entur route geometry; not a closure assessment.':'Importert rutegeometri fra Entur; ingen stengningsvurdering.',
    'Stop-to-stop schematic: route geometry unavailable.':'Skisse mellom holdeplasser: rutegeometri utilgjengelig.',
    'Published network view. This does not calculate a closure impact or confirm a departure is running now.':'Publisert rutenett. Visningen beregner ikke virkningen av stengninger og bekrefter ikke at en avgang kjøres nå.',

    'Understand the way ahead':'Forstå veien videre','Hamar, Norway · Access planning':'Hamar, Norge · Tilgjengelighetsplanlegging',
    'A clearer way through the city.':'Finn veien gjennom en by i endring.','Explore how street changes affect the journeys that matter.':'Se hvordan veiarbeid påvirker reisene som betyr noe for deg.',
    'Walking':'Til fots','Bus':'Buss','Driving':'Bil','Saved local data':'Lagrede lokale data','Planning prototype':'Planleggingsprototype','Hypothetical changes':'Hypotetiske endringer',
    'Make it your journey':'Din reise','Plan a walk':'Planlegg en gåtur','Reach your bus':'Kom deg til bussen','Explore a driving change':'Utforsk en endret bilrute',
    'Explore the impact':'Se konsekvensene','Your journey, on the map':'Reisen din på kartet','Walking route comparison':'Sammenligning av gangruter','Driving route comparison':'Sammenligning av bilruter',
    'Normal route':'Vanlig rute','With changes':'Med endringer','Extra distance':'Ekstra avstand','Unchanged':'Uendret','No route':'Ingen rute','Unknown':'Ukjent','Unassessed':'Ikke vurdert',
    'Hypothetical scenario':'Hypotetisk scenario','Inputs changed · recalculate':'Inndata endret · beregn på nytt','Choose a journey':'Velg en reise','Choose your journey':'Velg reisen din','Ready to explore':'Klar til å utforske',
    'Zoom in':'Zoom inn','Zoom out':'Zoom ut','Fit journey':'Vis reisen','Whole area':'Hele området','Closed section':'Stengt strekning','Map layers, coverage & help':'Kartlag, dekning og hjelp',
    'Street map':'Gatekart','3D buildings':'3D-bygninger','Saved map (offline)':'Lagret kart (frakoblet)','Street map · online context':'Gatekart · bakgrunn fra nettet','3D buildings · online context':'3D-bygninger · bakgrunn fra nettet',
    'Loading geographic map…':'Laster geografisk kart…','Saved map · offline':'Lagret kart · frakoblet','Online map unavailable · saved map shown':'Nettkart utilgjengelig · viser lagret kart','3D map unavailable · saved map shown':'3D-kart utilgjengelig · viser lagret kart',
    'Basemap is geographic context. Routing uses saved data; 3D heights may be approximate.':'Bakgrunnskartet gir geografisk sammenheng. Rutene bruker lagrede data; 3D-høyder kan være omtrentlige.',
    'Details':'Detaljer','Assessment details':'Vurderingsdetaljer','Close details':'Lukk detaljer','Source and technical details':'Kilder og tekniske detaljer',
    'Saved-journey alerts':'Varsler for lagrede reiser','Full assessment & accessibility evidence':'Full vurdering og tilgjengelighetsgrunnlag','Evidence and technical IDs':'Dokumentasjon og tekniske ID-er','Model diagnostics (raw reply)':'Modelldiagnostikk (råsvar)',
    'Load Ringgata demo':'Last Ringgata-eksempel','Load Koigen demo':'Last Koigen-eksempel','Example closure settings':'Innstillinger for stengningseksempel','Map area & example journeys':'Kartområde og eksempelreiser','Search coverage & limits':'Søkedekning og begrensninger',
    'From':'Fra','To':'Til','Search a saved place or bus stop':'Søk etter et lagret sted eller holdeplass','Choose points on the map instead':'Velg punkter på kartet i stedet','Enter coordinates instead':'Skriv inn koordinater i stedet',
    'Choose start on map':'Velg start på kartet','Choose destination on map':'Velg mål på kartet','Clear':'Tøm','Start latitude':'Start: breddegrad','Start longitude':'Start: lengdegrad','Destination latitude':'Mål: breddegrad','Destination longitude':'Mål: lengdegrad','Use these coordinates':'Bruk koordinatene',
    'Date & changes':'Dato og endringer','Assessment date':'Vurderingsdato','Assess projects':'Vurder prosjekter','Review closures & project dates':'Se stengninger og prosjektdatoer','Save a scenario for alerts':'Lagre et scenario for varsler',
    'Local calculation. Works without Ollama.':'Lokal beregning. Fungerer uten Ollama.','Compare mitigation options with AI':'Sammenlign tiltak med KI','Compare options with AI':'Sammenlign alternativer med KI','Mitigation options':'Tiltaksalternativer','Question for the planning assistant':'Spørsmål til planleggingsassistenten',
    'Saved journeys & alerts':'Lagrede reiser og varsler','Save this journey on this browser':'Lagre reisen i denne nettleseren','Journey name':'Navn på reisen','Morning walk':'Morgentur','Save selected journey':'Lagre valgt reise','Restore':'Hent frem','Delete':'Slett','Refresh journey alerts':'Oppdater reisevarsler','Dismiss':'Skjul','Restore alert':'Vis varselet igjen',
    'Mapped Hamar case':'Kartlagt Hamar-tilfelle','Journey':'Reise','Project name':'Prosjektnavn','Start date':'Startdato','End date':'Sluttdato','Add hypothetical project':'Legg til hypotetisk prosjekt','Hypothetical':'Hypotetisk','Closed walking sections':'Stengte gangstrekninger','Closed road sections':'Stengte veistrekninger',
    'No closures':'Ingen stengninger','Ringgata only':'Bare Ringgata','Furubergvegen only':'Bare Furubergvegen','Both closures':'Begge stengninger',
    'Bus stop access':'Tilgang til holdeplass','Published dated bus trip':'Publisert bussavgang med dato','Load published bus scenario':'Last publisert busseksempel','Synthetic test example':'Syntetisk testeksempel','Load synthetic bus scenario':'Last syntetisk busseksempel',
    'Trip details & coverage limits':'Avgangsdetaljer og dekningsgrenser','Destination stop on the same trip':'Målholdeplass på samme avgang','Map comparison':'Kartsammenligning','Normal service':'Vanlig drift','Hypothetical skipped usual stop':'Hypotetisk bortfall av vanlig holdeplass','Return to walking workspace':'Tilbake til gåturer',
    'To usual stop':'Til vanlig holdeplass','After stop skip':'Når holdeplassen utgår','Dated trip · hypothetical stop skip':'Datert avgang · hypotetisk holdeplassbortfall','Synthetic example':'Syntetisk eksempel',
    'Results current':'Oppdaterte resultater','No results yet':'Ingen resultater ennå','Outdated · recalculate':'Utdatert · beregn på nytt',
    'Draft from notice':'Lag utkast fra meldingen','What the source confirms & what is unknown':'Hva kilden bekrefter og hva som er ukjent','Field evidence and review notes':'Dokumentasjon per felt og merknader','Saved-notice draft':'Utkast fra lagret melding','Saved-notice review':'Gjennomgang av lagret melding','Needs human review':'Krever menneskelig gjennomgang',
    'Access status':'Tilgangsstatus','Affected location':'Berørt sted','Travel modes':'Transportformer','Restriction':'Begrensning','Stated dates':'Oppgitte datoer','Supporting sentence':'Kildesetning','unknown for the footpath closure':'ukjent for stengningen av gangstien','Unavailable':'Utilgjengelig',
    'Accessibility evidence':'Dokumentasjon for tilgjengelighet','Review required':'Krever gjennomgang','Avoid steps':'Unngå trapper','Requirement: avoid steps.':'Krav: unngå trapper.','Local model draft and diagnostics':'Lokalt modellutkast og diagnostikk',
    'Current':'Gjeldende','Outdated':'Utdatert','Unreachable':'Ikke mulig å nå','Outside map coverage':'Utenfor kartdekningen','Unreachable under closures':'Kan ikke nås med stengningene','No mapped route':'Ingen kartlagt rute',
    'No saved walking journeys to check.':'Ingen lagrede gåturer å kontrollere.','No valid saved journeys yet.':'Ingen gyldige lagrede reiser ennå.','Saved journeys are stored only in this browser.':'Lagrede reiser finnes bare i denne nettleseren.',
    'Junction crossing':'Kryssing ved veikrysset','Ankerskogen park path':'Gangvei ved Ankerskogen','Your journey':'Din reise','Your own journey':'Din egen reise','Your own journey (choose on map)':'Din egen reise (velg på kartet)',
    'Search saved places, pick map points, or try an example. Coverage depends on the selected map area.':'Søk etter lagrede steder, velg kartpunkter eller prøv et eksempel. Dekningen avhenger av valgt kartområde.',
    'Compare walking access to stops on a saved dated trip. Bus delay is unknown.':'Sammenlign gangavstanden til holdeplasser på en lagret avgang. Bussforsinkelsen er ukjent.',
    'One supported driving example. The road closure is hypothetical; custom driving journeys are not available yet.':'Ett støttet bileksempel. Veistengningen er hypotetisk; egne bilreiser er foreløpig ikke tilgjengelige.',
    'Distances are walks to mapped stop connections. Bus travel time and delay are unknown.':'Avstandene gjelder gange til karttilkoblinger ved holdeplasser. Kjøretid og bussforsinkelse er ukjent.',
    'Modeled candidate section. Exact closure extent and dates are unknown; accessibility requires review.':'Modellert kandidatstrekning. Nøyaktig omfang og datoer er ukjent; tilgjengelighet må vurderes.',
    'Fixed driving example. Turn restrictions, conditional rules and live conditions are not modeled.':'Fast bileksempel. Svingrestriksjoner, betingede regler og sanntidsforhold er ikke modellert.',
    'Choose two saved places or use an example, then assess the configured changes.':'Velg to lagrede steder eller bruk et eksempel, og vurder deretter endringene.',
    'Checking saved local project records…':'Kontrollerer lagrede lokale prosjektdata…','Checks occur when the app opens or when you refresh; there is no continuous monitoring.':'Kontroller skjer når appen åpnes eller du oppdaterer; det er ingen kontinuerlig overvåking.',
  };
  const originals=new WeakMap(),attributeOriginals=new WeakMap();
  const patterns=[
    [/^(.+) · outside Hamar$/,m=>`${m[1]} · utenfor Hamar`],
    [/^(.+) · (inbound|outbound) · (\d+) stops$/,m=>`${m[1]} · ${m[2]==='inbound'?'inngående':'utgående'} · ${m[3]} holdeplasser`],
    [/^(.+) · (.+) → (.+)\. (Scheduled snapshot; not live departures\.|No scheduled journeys for this variant on the snapshot date\.) Bus delay and closure effects are not assessed\.$/,m=>`${m[1]} · ${m[2]} → ${m[3]}. ${m[4].startsWith('No scheduled')?'Ingen planlagte avganger for denne varianten på snapshotdatoen.':'Lagrede rutedata; ingen sanntidsavganger.'} Bussforsinkelse og stengningsvirkninger er ikke vurdert.`],

    [/^(\d+) lines reported by Entur within Hamar municipality\. Snapshot: (.+)\.$/,m=>`${m[1]} linjer oppgitt av Entur innenfor Hamar kommune. Snapshot: ${m[2]}.`],
    [/^(\d+) scheduled journeys on (.+)\. Full stops may extend beyond Hamar and our walking map\. No live bus delay is available\.$/,m=>`${m[1]} planlagte avganger ${m[2]}. Holdeplassrekken kan strekke seg utenfor Hamar og gangkartet. Sanntidsforsinkelse er ikke tilgjengelig.`],
    [/^Source checked: (.+)$/,m=>`Kilde kontrollert: ${m[1]}`],

    [/^Walking assessment for (.+)\. Saved map; hypothetical closures\.$/,m=>`Gangrute vurdert for ${m[1]}. Lagret kart; hypotetiske stengninger.`],
    [/^(.+) · Walking access to the bus$/,m=>`${m[1]} · Gangtilgang til bussen`],
    [/^Show dismissed alerts \((\d+)\)$/,m=>`Vis skjulte varsler (${m[1]})`],
    [/^(\d+) m extra on your walk$/,m=>`${m[1]} m ekstra på gåturen`],
    [/^Project (\d+)$/,m=>`Prosjekt ${m[1]}`],
    [/^Project assessment for (.+)$/,m=>`Prosjektvurdering for ${m[1]}`],
    [/^Walking distance: (.+) \(baseline (.+)\)$/,m=>`Gangavstand: ${m[1]} (vanlig rute ${m[2]})`],
    [/^Hypothetical demo: (.+)$/,m=>`Hypotetisk eksempel: ${m[1]}`],
    [/^(\d+) distinct data issue\(s\) across (\d+) checks$/,m=>`${m[1]} ulike dataproblemer i ${m[2]} kontroller`],
  ];
  function translate(value){
    if(preferences.language!=='nb')return value;
    const trimmed=value.trim();let translated=dictionary[trimmed];
    if(!translated){for(const [pattern,render] of patterns){const match=trimmed.match(pattern);if(match){translated=render(match);break;}}}
    if(!translated && /^\d+\.\d+ km$/.test(trimmed))translated=trimmed.replace('.',',');
    return translated ? value.replace(trimmed,translated) : value;
  }
  function apply(root=document.body){
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    let node;
    while((node=walker.nextNode())){
      if(node.parentElement?.closest('script,style,pre,blockquote,option[value="en"],option[value="nb"],.maplibregl-ctrl-attrib,[data-source-text]'))continue;
      if(!originals.has(node))originals.set(node,node.data);
      const value=translate(originals.get(node));if(node.data!==value)node.data=value;
    }
    root.querySelectorAll?.('[placeholder],[title],[aria-label]').forEach(element=>{
      if(element.closest('.maplibregl-ctrl-attrib,[data-source-text]'))return;
      if(!attributeOriginals.has(element))attributeOriginals.set(element,{});
      const saved=attributeOriginals.get(element);
      for(const attribute of ['placeholder','title','aria-label']){
        if(!element.hasAttribute(attribute))continue;
        if(!(attribute in saved))saved[attribute]=element.getAttribute(attribute);
        const value=translate(saved[attribute]);if(element.getAttribute(attribute)!==value)element.setAttribute(attribute,value);
      }
    });
  }
  function save(){try{localStorage.setItem(key,JSON.stringify(preferences));}catch{}}
  function setLanguage(language){preferences.language=language==='nb'?'nb':'en';document.documentElement.lang=preferences.language;$('language-select').value=preferences.language;apply();save();window.dispatchEvent(new CustomEvent('hamar-language',{detail:preferences.language}));}
  function $(id){return document.getElementById(id);}
  function setTheme(theme){preferences.theme=theme==='dark'?'dark':'light';document.documentElement.dataset.theme=preferences.theme;$('theme-toggle').setAttribute('aria-pressed',String(preferences.theme==='dark'));$('theme-toggle').textContent=preferences.theme==='dark'?'☀':'☾';save();window.dispatchEvent(new CustomEvent('hamar-theme',{detail:preferences.theme}));}
  window.hamarPreferences={translate,get language(){return preferences.language;},get theme(){return preferences.theme;}};
  $('language-select').addEventListener('change',event=>setLanguage(event.target.value));
  $('theme-toggle').addEventListener('click',()=>setTheme(preferences.theme==='dark'?'light':'dark'));
  setTheme(preferences.theme);setLanguage(preferences.language);
  let pending=false;
  new MutationObserver(()=>{if(!pending){pending=true;queueMicrotask(()=>{pending=false;apply();});}}).observe(document.body,{childList:true,subtree:true,characterData:true});
})();

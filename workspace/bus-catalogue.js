"use strict";
(() => {
 const $=id=>document.getElementById(id);
 function element(tag,text,attrs={}){const node=document.createElement(tag);node.textContent=text;for(const [k,v]of Object.entries(attrs))node.setAttribute(k,v);return node;}
 let catalogue,details,sequence=0;
 const host=element('div','',{id:'bus-catalogue',class:'bus-catalogue'});
 host.append(element('h3','Explore Hamar bus lines'),element('p','Loading imported bus services…',{id:'catalogue-status',class:'hint',role:'status'}),
   element('label','Search line or destination',{for:'catalogue-search'}),element('input','',{id:'catalogue-search',type:'search',placeholder:'Line number or destination',maxlength:'80'}),
   element('label','Bus line',{for:'catalogue-line'}),element('select','',{id:'catalogue-line'}),
   element('label','Direction and route variant',{for:'catalogue-pattern'}),element('select','',{id:'catalogue-pattern'}),
   element('button','Show bus route',{id:'catalogue-show',type:'button',class:'btn btn-primary'}),
   element('p','',{id:'catalogue-service',class:'hint'}),element('div','',{id:'catalogue-stops'}));
 $('g-bus').after(host);
 $('catalogue-show').disabled=true;
 async function get(url){const response=await fetch(url);const value=await response.json();if(!response.ok)throw Error(value.error||'Bus data unavailable');return value;}
 function fillLines(){
   const q=$('catalogue-search').value.trim().toLocaleLowerCase();
   const matches=catalogue.lines.filter(line=>`${line.code} ${line.name}`.toLocaleLowerCase().includes(q));
   $('catalogue-line').replaceChildren(...matches.map(line=>element('option',`${line.code} · ${line.name}`,{value:line.id})));
   if(!matches.length){sequence++;details=null;$('catalogue-pattern').replaceChildren();$('catalogue-show').disabled=true;$('catalogue-status').textContent='No matching bus lines.';return;}
   loadLine();
 }
 async function loadLine(){
   const turn=++sequence;$('catalogue-show').disabled=true;$('catalogue-stops').replaceChildren();
   $('catalogue-service').textContent='';
   try{
     const result=await get('/api/bus/catalogue/'+encodeURIComponent($('catalogue-line').value));
     if(turn!==sequence)return;details=result;
     $('catalogue-pattern').replaceChildren(...result.patterns.map(p=>element('option',`${p.first_stop} → ${p.last_stop} · ${p.direction||'—'} · ${p.stop_count} stops`,{value:p.id})));
     $('catalogue-status').textContent=`${catalogue.line_count} lines reported by Entur within Hamar municipality. Snapshot: ${catalogue.service_date}.`;
     $('catalogue-show').disabled=!result.patterns.length;serviceNote();
   }catch(error){if(turn===sequence)$('catalogue-status').textContent=error.message;}
 }
 function serviceNote(){
   const p=details?.patterns.find(p=>p.id===$('catalogue-pattern').value);
   $('catalogue-service').textContent=p?`${p.scheduled_journey_count} scheduled journeys on ${details.service_date}. Full stops may extend beyond Hamar and our walking map. No live bus delay is available.`:'Route-variant data unavailable for this line.';
 }
 $('catalogue-search').addEventListener('input',()=>{if(catalogue)fillLines();});
 $('catalogue-line').addEventListener('change',loadLine);
 $('catalogue-pattern').addEventListener('change',serviceNote);
 $('catalogue-show').addEventListener('click',async()=>{
   const turn=++sequence;$('catalogue-show').disabled=true;
   try{
     const result=await get('/api/bus/catalogue/'+encodeURIComponent($('catalogue-line').value)+'?pattern='+encodeURIComponent($('catalogue-pattern').value));
     if(turn!==sequence)return;
     const list=element('ol','',{class:'catalogue-stop-list'});
     for(const stop of result.pattern.stops)list.append(element('li',stop.name+(stop.in_hamar?'':' · outside Hamar')));
     const stopDetails=element('details','');stopDetails.append(element('summary','Ordered stops'),list);
     const source=element('a','Entur source and attribution',{href:result.source_url,target:'_blank',rel:'noopener noreferrer'});
     $('catalogue-stops').replaceChildren(stopDetails,element('p',`Source checked: ${result.retrieved_at}`,{class:'hint'}),source,
       element('p','Published network view. This does not calculate a closure impact or confirm a departure is running now.',{class:'hint'}));
     window.dispatchEvent(new CustomEvent('hamar-bus-catalogue',{detail:result}));
   }catch(error){$('catalogue-status').textContent=error.message;}finally{if(turn===sequence)$('catalogue-show').disabled=false;}
 });
 get('/api/bus/catalogue').then(result=>{catalogue=result;fillLines();}).catch(error=>{$('catalogue-status').textContent=error.message;});
})();

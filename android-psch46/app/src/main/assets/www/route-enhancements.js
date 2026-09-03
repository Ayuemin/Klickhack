(function(){
'use strict';
if(typeof routeStage!=='function'||typeof map==='undefined'||typeof state==='undefined')return;

// --- Natural water layer ----------------------------------------------------
prefs.showWater = prefs.showWater !== false;
state.waters = state.waters || [];
state.nearWaterMarks = state.nearWaterMarks || [];

function waterIsLine(w){return w.type==='река'||w.type==='ручей'}
function waterNamed(w){return w.name && !String(w.name).includes('без названия')}
function drawWater(){
  state.waters.forEach(x=>{try{map.removeLayer(x)}catch(e){}});state.waters=[];
  if(!prefs.showWater)return;
  (D.waterSources||[]).forEach(w=>{
    const pts=Array.isArray(w.p)?w.p:[];
    let layer=null;
    if(waterIsLine(w)&&pts.length>1){
      layer=L.polyline(pts,{renderer:canvas,color:'#4b9dca',weight:w.type==='река'?2.4:1.15,opacity:w.type==='река'?.78:.55,interactive:waterNamed(w)});
    }else if(pts.length>2){
      layer=L.polygon(pts,{renderer:canvas,color:'#4b9dca',weight:1.05,fillColor:'#8bc7e5',fillOpacity:.22,opacity:.68,interactive:waterNamed(w)});
    }else{
      layer=L.circleMarker([w.lat,w.lon],{renderer:canvas,radius:w.type==='пруд'?3.5:4.5,color:'#4b9dca',weight:1,fillColor:'#8bc7e5',fillOpacity:.36,opacity:.7,interactive:waterNamed(w)});
    }
    layer.addTo(map); if(layer.bringToBack)layer.bringToBack();
    if(waterNamed(w))layer.bindTooltip(`${esc(w.type)} · ${esc(w.name)}`,{direction:'top',sticky:true});
    state.waters.push(layer);
  });
}

// Add a settings switch without touching the large base HTML file.
const settingsModal=document.querySelector('#settings .modal');
if(settingsModal&&!document.getElementById('waterSwitch')){
  const anchor=document.getElementById('openCatalogFromSettings');
  const row=document.createElement('div');row.className='row';
  row.innerHTML='<div class="rowText"><b>Природные водоисточники</b><span>Реки, ручьи, озёра, пруды и водохранилища из офлайн-карты</span></div><div class="switch on" id="waterSwitch"><i></i></div>';
  if(anchor)settingsModal.insertBefore(row,anchor); else settingsModal.appendChild(row);
  const sw=document.getElementById('waterSwitch');
  const sync=()=>sw.classList.toggle('on',prefs.showWater);
  sync();
  sw.onclick=()=>{prefs.showWater=!prefs.showWater;savePrefs();sync();drawWater()};
}
drawWater();

function waterLabel(w){
  const n=String(w.name||w.type||'водоём');
  return n.includes('без названия')?esc(w.type):`${esc(w.type)} ${esc(n)}`;
}
function addNearWaterMarkers(list){
  state.nearWaterMarks.forEach(x=>{try{map.removeLayer(x)}catch(e){}});state.nearWaterMarks=[];
  if(!prefs.showWater)return;
  list.slice(0,3).forEach(w=>{
    const html=`<div style="white-space:nowrap;background:rgba(224,245,255,.97);border:1px solid #4b9dca;border-radius:7px;padding:3px 6px;box-shadow:0 1px 4px rgba(0,0,0,.16);font-size:9px;font-weight:800;color:#16506f">💧 ${waterLabel(w)} · ${Number(w.distanceKm).toFixed(1)} км</div>`;
    const m=L.marker([w.lat,w.lon],{interactive:false,zIndexOffset:610,icon:L.divIcon({className:'',html:html,iconSize:[170,24],iconAnchor:[5,12]})}).addTo(map);
    state.nearWaterMarks.push(m);
  });
}

window.routeStage=function(){
  state.stage='route';
  clearDots();
  clearRoute();
  state.nearWaterMarks.forEach(x=>{try{map.removeLayer(x)}catch(e){}});state.nearWaterMarks=[];
  stageBar.textContent='Маршрут-награда · ПСЧ‑46 → '+state.target.name;
  const real=state.target.route&&state.target.route.length>1;
  const route=real?state.target.route:[[D.station.lat,D.station.lon],[state.target.lat,state.target.lon]];
  state.route=L.polyline(route,{color:'#d73531',weight:5,opacity:.94,lineCap:'round',lineJoin:'round'}).addTo(map);

  const via=Array.isArray(state.target.via)?state.target.via:[];
  via.forEach((p)=>{
    const html=`<div style="display:flex;align-items:center;gap:4px;white-space:nowrap;background:rgba(255,255,255,.96);border:1px solid rgba(26,69,98,.28);border-radius:7px;padding:3px 6px;box-shadow:0 1px 4px rgba(0,0,0,.18);font-size:10px;font-weight:800;color:#17354f"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#2f77b5"></span>${esc(p.name)}</div>`;
    const m=L.marker([p.lat,p.lon],{interactive:false,zIndexOffset:520,icon:L.divIcon({className:'',html:html,iconSize:[120,24],iconAnchor:[6,12]})}).addTo(map);
    state.dots.push(m);
  });

  const nearWater=Array.isArray(state.target.nearWater)?state.target.nearWater:[];
  addNearWaterMarkers(nearWater);

  const targetIcon=L.divIcon({className:'',html:'<div style="width:24px;height:24px;border-radius:50% 50% 50% 0;background:#d93632;border:3px solid white;transform:rotate(-45deg);box-shadow:0 2px 7px rgba(0,0,0,.3)"><i style="display:block;width:6px;height:6px;border-radius:50%;background:white;margin:6px"></i></div>',iconSize:[24,24],iconAnchor:[12,22]});
  state.targetMark=L.marker([state.target.lat,state.target.lon],{icon:targetIcon,zIndexOffset:700}).addTo(map).bindTooltip(state.target.name,{permanent:true,direction:'top',offset:[0,-16]});
  const bounds=state.route.getBounds();
  nearWater.filter(w=>Number(w.distanceKm)<=3).slice(0,3).forEach(w=>bounds.extend([w.lat,w.lon]));
  map.fitBounds(bounds,{paddingTopLeft:[28,66],paddingBottomRight:[28,270],maxZoom:14});

  card.style.display='block';
  card.className='card routeCard';
  const km=state.target.distanceKm!=null?state.target.distanceKm+' км':(real?'маршрут':'направление');
  const viaHtml=via.length
    ? `<div style="margin:7px 0 8px;background:#edf3f7;border-radius:10px;padding:8px 9px"><div style="font-size:8px;text-transform:uppercase;letter-spacing:.55px;color:#6c7d89;font-weight:850;margin-bottom:4px">По пути</div><div style="font-size:11px;line-height:1.45;font-weight:750;color:#27465d">ПСЧ‑46 · Рамешки → ${via.map(x=>esc(x.name)).join(' → ')} → ${esc(state.target.name)}</div></div>`
    : `<div style="margin:7px 0 8px;background:#edf3f7;border-radius:10px;padding:8px 9px"><div style="font-size:8px;text-transform:uppercase;letter-spacing:.55px;color:#6c7d89;font-weight:850;margin-bottom:4px">По пути</div><div style="font-size:11px;line-height:1.45;font-weight:750;color:#27465d">ПСЧ‑46 · Рамешки → ${esc(state.target.name)}</div></div>`;
  const waterRows=nearWater.slice(0,4).map(w=>`<div style="display:flex;gap:7px;align-items:baseline;padding:2px 0"><span style="flex:1;font-weight:750">💧 ${waterLabel(w)}</span><b style="white-space:nowrap">${Number(w.distanceKm).toFixed(1)} км</b></div>`).join('');
  const waterHtml=`<div style="margin:0 0 8px;background:#e9f6fc;border-left:4px solid #4b9dca;border-radius:9px;padding:7px 9px"><div style="font-size:8px;text-transform:uppercase;letter-spacing:.55px;color:#367895;font-weight:850;margin-bottom:3px">Вода рядом с целью</div>${waterRows||'<div style="font-size:10px;color:#587687">В радиусе 7 км источник на карте не найден.</div>'}<div style="font-size:8px;color:#66818f;margin-top:4px">Ориентир по OSM. Подъезд и возможность забора воды требуют проверки на местности.</div></div>`;
  const safe=D.meta&&String(D.meta.routingProfile||'').startsWith('firetruck-safe');
  const safeHtml=safe?'<span style="display:inline-block;margin-left:6px;border-radius:999px;background:#e4f4eb;color:#28724f;padding:3px 6px;font-size:8px;font-weight:850">проверенный дорожный маршрут</span>':'';
  card.innerHTML=`<div class="kicker">Правильный ответ ${safeHtml}</div><div class="place">${esc(state.target.name)}</div>${viaHtml}${waterHtml}<div class="routeInfo"><div class="pill"><small>От ПСЧ‑46</small><b>${km}</b></div><div class="pill"><small>Серия</small><b>${stats.streak}</b></div><div class="pill"><small>Лучшее</small><b>${stats.best}</b></div></div><div class="actions"><button class="secondary" id="overview">Карта</button><button class="primary" id="next">Готов — следующее</button></div>`;
  document.getElementById('next').onclick=()=>{state.catalogTraining=false;question()};
  document.getElementById('overview').onclick=()=>map.fitBounds(D.bbox,{padding:[8,8]});
};
})();

(function(){
'use strict';
if(typeof routeStage!=='function'||typeof map==='undefined'||typeof state==='undefined')return;

// --- Natural water layer ----------------------------------------------------
prefs.showWater = prefs.showWater !== false;
state.waters = state.waters || [];
state.nearWaterMarks = state.nearWaterMarks || [];
state.unverifiedConnector = state.unverifiedConnector || null;

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

const baseClearRoute=clearRoute;
window.clearRoute=function(){
  state.nearWaterMarks.forEach(x=>{try{map.removeLayer(x)}catch(e){}});state.nearWaterMarks=[];
  if(state.unverifiedConnector){try{map.removeLayer(state.unverifiedConnector)}catch(e){};state.unverifiedConnector=null}
  baseClearRoute();
};

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

function warningText(list){
  return (Array.isArray(list)?list:[]).slice(0,3).map(x=>esc(x)).join('; ');
}

window.routeStage=function(){
  state.stage='route';
  clearDots();
  clearRoute();
  stageBar.textContent='Маршрут-награда · ПСЧ‑46 → '+state.target.name;

  const real=state.target.route&&state.target.route.length>1;
  const verified=state.target.routeVerified!==false;
  const caution=state.target.routeCaution===true;
  const hardWarnings=Array.isArray(state.target.routeHardWarnings)?state.target.routeHardWarnings:[];
  const cautionWarnings=Array.isArray(state.target.routeCautionWarnings)?state.target.routeCautionWarnings:[];
  const route=real?state.target.route:null;

  // Red = no hard prohibition found. Amber dashed = route contains a hard warning and must NOT be memorised as a confirmed driveable route.
  if(route){
    state.route=L.polyline(route,verified
      ? {color:'#d73531',weight:5,opacity:.94,lineCap:'round',lineJoin:'round'}
      : {color:'#d98a22',weight:4,opacity:.88,dashArray:'9 8',lineCap:'round',lineJoin:'round'}
    ).addTo(map);
  }

  // Never pretend that the final gap from the road graph to the settlement marker is a road.
  if(route&&route.length){
    const end=route[route.length-1];
    const gapKm=Number(state.target.routeSnapKm||0);
    if(gapKm>0.03){
      state.unverifiedConnector=L.polyline([end,[state.target.lat,state.target.lon]],{color:'#d98a22',weight:2.8,opacity:.82,dashArray:'5 7',lineCap:'round',interactive:false}).addTo(map);
    }
  }

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

  let bounds=state.route?state.route.getBounds():L.latLngBounds([[state.target.lat,state.target.lon],[D.station.lat,D.station.lon]]);
  bounds.extend([state.target.lat,state.target.lon]);
  nearWater.filter(w=>Number(w.distanceKm)<=3).slice(0,3).forEach(w=>bounds.extend([w.lat,w.lon]));
  map.fitBounds(bounds,{paddingTopLeft:[28,66],paddingBottomRight:[28,320],maxZoom:14});

  card.style.display='block';
  card.className='card routeCard';
  const km=state.target.distanceKm!=null?state.target.distanceKm+' км':(real?'маршрут':'—');
  const chain=via.length?via.map(x=>esc(x.name)).join(' → ')+' → ':'';
  let viaHtml='';
  if(!verified){
    const why=warningText(hardWarnings)||'на маршруте найдено ограничение, требующее ручной проверки';
    viaHtml=`<div style="margin:7px 0 8px;background:#fff0dc;border-left:4px solid #d47b18;border-radius:10px;padding:8px 9px"><div style="font-size:8px;text-transform:uppercase;letter-spacing:.55px;color:#9b5710;font-weight:850;margin-bottom:4px">Маршрут не подтверждён для пожарной машины</div><div style="font-size:11px;line-height:1.45;font-weight:750;color:#704817">ПСЧ‑46 · Рамешки → ${chain}${esc(state.target.name)}</div><div style="font-size:9px;color:#8a5e2a;margin-top:4px"><b>Причина:</b> ${why}. Оранжевый пунктир — только картографический ориентир; не использовать как подтверждённый проезд.</div></div>`;
  }else if(caution){
    const why=warningText(cautionWarnings)||'часть картографической разметки неполна';
    viaHtml=`<div style="margin:7px 0 8px;background:#fff8e8;border-left:4px solid #e0a221;border-radius:10px;padding:8px 9px"><div style="font-size:8px;text-transform:uppercase;letter-spacing:.55px;color:#8b681b;font-weight:850;margin-bottom:4px">Маршрут дорожный, но требует сверки</div><div style="font-size:11px;line-height:1.45;font-weight:750;color:#5d4b22">ПСЧ‑46 · Рамешки → ${chain}${esc(state.target.name)}</div><div style="font-size:9px;color:#77683e;margin-top:4px">${why}. Жёсткого запрета для машины по данным OSM не найдено, но разметка неполна.</div></div>`;
  }else{
    viaHtml=`<div style="margin:7px 0 8px;background:#edf3f7;border-radius:10px;padding:8px 9px"><div style="font-size:8px;text-transform:uppercase;letter-spacing:.55px;color:#6c7d89;font-weight:850;margin-bottom:4px">По пути</div><div style="font-size:11px;line-height:1.45;font-weight:750;color:#27465d">ПСЧ‑46 · Рамешки → ${chain}${esc(state.target.name)}</div></div>`;
  }

  const waterRows=nearWater.slice(0,4).map(w=>`<div style="display:flex;gap:7px;align-items:baseline;padding:2px 0"><span style="flex:1;font-weight:750">💧 ${waterLabel(w)}</span><b style="white-space:nowrap">${Number(w.distanceKm).toFixed(1)} км</b></div>`).join('');
  const waterHtml=`<div style="margin:0 0 8px;background:#e9f6fc;border-left:4px solid #4b9dca;border-radius:9px;padding:7px 9px"><div style="font-size:8px;text-transform:uppercase;letter-spacing:.55px;color:#367895;font-weight:850;margin-bottom:3px">Вода рядом с целью</div>${waterRows||'<div style="font-size:10px;color:#587687">В радиусе 7 км источник на карте не найден.</div>'}<div style="font-size:8px;color:#66818f;margin-top:4px">Ориентир по OSM. Подъезд, состояние берега и возможность забора воды требуют проверки на местности.</div></div>`;

  let statusHtml='';
  if(!verified)statusHtml='<span style="display:inline-block;margin-left:6px;border-radius:999px;background:#ffe6c8;color:#9a5310;padding:3px 6px;font-size:8px;font-weight:850">не подтверждён</span>';
  else if(caution)statusHtml='<span style="display:inline-block;margin-left:6px;border-radius:999px;background:#fff3c9;color:#816117;padding:3px 6px;font-size:8px;font-weight:850">требует сверки</span>';
  else statusHtml='<span style="display:inline-block;margin-left:6px;border-radius:999px;background:#e4f4eb;color:#28724f;padding:3px 6px;font-size:8px;font-weight:850">без жёстких ограничений OSM</span>';

  const distanceLabel=verified?'От ПСЧ‑46':'Картографический путь';
  card.innerHTML=`<div class="kicker">Правильный ответ ${statusHtml}</div><div class="place">${esc(state.target.name)}</div>${viaHtml}${waterHtml}<div class="routeInfo"><div class="pill"><small>${distanceLabel}</small><b>${km}</b></div><div class="pill"><small>Серия</small><b>${stats.streak}</b></div><div class="pill"><small>Лучшее</small><b>${stats.best}</b></div></div><div class="actions"><button class="secondary" id="overview">Карта</button><button class="primary" id="next">Готов — следующее</button></div>`;
  document.getElementById('next').onclick=()=>{state.catalogTraining=false;question()};
  document.getElementById('overview').onclick=()=>map.fitBounds(D.bbox,{padding:[8,8]});
};
})();

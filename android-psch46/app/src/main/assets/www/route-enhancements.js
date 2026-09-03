(function(){
'use strict';
if(typeof routeStage!=='function'||typeof map==='undefined'||typeof state==='undefined')return;

window.routeStage=function(){
  state.stage='route';
  clearDots();
  clearRoute();
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

  const targetIcon=L.divIcon({className:'',html:'<div style="width:24px;height:24px;border-radius:50% 50% 50% 0;background:#d93632;border:3px solid white;transform:rotate(-45deg);box-shadow:0 2px 7px rgba(0,0,0,.3)"><i style="display:block;width:6px;height:6px;border-radius:50%;background:white;margin:6px"></i></div>',iconSize:[24,24],iconAnchor:[12,22]});
  state.targetMark=L.marker([state.target.lat,state.target.lon],{icon:targetIcon,zIndexOffset:700}).addTo(map).bindTooltip(state.target.name,{permanent:true,direction:'top',offset:[0,-16]});
  map.fitBounds(state.route.getBounds(),{paddingTopLeft:[28,66],paddingBottomRight:[28,225],maxZoom:14});

  card.style.display='block';
  card.className='card routeCard';
  const km=state.target.distanceKm!=null?state.target.distanceKm+' км':(real?'маршрут':'направление');
  const viaHtml=via.length
    ? `<div style="margin:7px 0 10px;background:#edf3f7;border-radius:10px;padding:8px 9px"><div style="font-size:8px;text-transform:uppercase;letter-spacing:.55px;color:#6c7d89;font-weight:850;margin-bottom:4px">По пути</div><div style="font-size:11px;line-height:1.45;font-weight:750;color:#27465d">ПСЧ‑46 · Рамешки → ${via.map(x=>esc(x.name)).join(' → ')} → ${esc(state.target.name)}</div></div>`
    : `<div style="margin:7px 0 10px;background:#edf3f7;border-radius:10px;padding:8px 9px"><div style="font-size:8px;text-transform:uppercase;letter-spacing:.55px;color:#6c7d89;font-weight:850;margin-bottom:4px">По пути</div><div style="font-size:11px;line-height:1.45;font-weight:750;color:#27465d">ПСЧ‑46 · Рамешки → ${esc(state.target.name)}</div></div>`;
  const safe=D.meta&&String(D.meta.routingProfile||'').startsWith('firetruck-safe');
  const safeHtml=safe?'<span style="display:inline-block;margin-left:6px;border-radius:999px;background:#e4f4eb;color:#28724f;padding:3px 6px;font-size:8px;font-weight:850">проверенный дорожный маршрут</span>':'';
  card.innerHTML=`<div class="kicker">Правильный ответ ${safeHtml}</div><div class="place">${esc(state.target.name)}</div>${viaHtml}<div class="routeInfo"><div class="pill"><small>От ПСЧ‑46</small><b>${km}</b></div><div class="pill"><small>Серия</small><b>${stats.streak}</b></div><div class="pill"><small>Лучшее</small><b>${stats.best}</b></div></div><div class="actions"><button class="secondary" id="overview">Карта</button><button class="primary" id="next">Готов — следующее</button></div>`;
  document.getElementById('next').onclick=()=>{state.catalogTraining=false;question()};
  document.getElementById('overview').onclick=()=>map.fitBounds(D.bbox,{padding:[8,8]});
};
})();

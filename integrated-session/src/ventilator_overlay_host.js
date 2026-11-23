// The student window owns its DOM. File-based windows communicate through authenticated messages.
if(isPatient){
 let ventBox=null,ventKey='',ventFrame=null,lastGeometry=null,ventAbort=null;
 const notify=(type,extra={})=>window.opener?.postMessage({app:'vital-lab-vent-overlay',session:token,key:ventKey,type,...extra},'*');
 function geometry(){if(!ventBox)return;const r=ventBox.getBoundingClientRect();lastGeometry={left:r.left,top:r.top,width:r.width,height:r.height};notify('geometry',{bounds:lastGeometry})}
 function hideVent(){if(ventBox){geometry();ventBox.remove()}ventAbort?.abort();ventAbort=null;ventBox=null;ventFrame=null;notify('hidden',{bounds:lastGeometry})}
 function showVent(d){
  if(ventBox&&ventKey===d.key){notify('shown');return}
  if(ventBox)hideVent();ventKey=d.key;ventAbort=new AbortController();
  const width=innerWidth,height=innerHeight,left=0,top=0;
  const box=document.createElement('section');box.id='vitalSparrowOverlay';box.setAttribute('aria-label','Ventilator display');box.style.cssText='position:fixed;inset:0;z-index:30000;display:flex;flex-direction:column;box-sizing:border-box;background:#000;overflow:hidden';
  const bar=document.createElement('div');bar.style.cssText='display:flex;flex:0 0 44px;align-items:center;gap:12px;justify-content:space-between;padding:0 8px;background:#26333d;color:white;font:14px Arial';const label=document.createElement('span');label.textContent='Ventway Sparrow';const controls=document.createElement('div');controls.style.cssText='display:flex;gap:8px';const full=document.createElement('button');full.type='button';full.textContent=document.fullscreenElement?'Exit full screen':'Full screen';full.style.cssText='min-height:38px;padding:4px 16px;font:14px Arial';full.onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen({navigationUI:'hide'})}catch{full.textContent='Use F11 for full screen'}};document.addEventListener('fullscreenchange',()=>{full.textContent=document.fullscreenElement?'Exit full screen':'Full screen'},{signal:ventAbort.signal});const close=document.createElement('button');close.type='button';close.textContent='Return to vitals';close.setAttribute('aria-label','Hide ventilator');close.style.cssText='min-height:38px;padding:4px 16px;border:1px solid #a5b9c5;background:#26333d;color:white;font:14px Arial;cursor:pointer';controls.append(full,close);bar.append(label,controls);
  const frame=document.createElement('iframe');frame.title='Sparrow read-only ventilator';frame.style.cssText='display:block;flex:1;width:100%;min-height:0;border:0;background:#080b0e';box.append(bar,frame);document.body.append(box);ventBox=box;ventFrame=frame;frame.onload=()=>notify('ready');frame.srcdoc=d.html;close.onclick=hideVent;
  new ResizeObserver(geometry).observe(box);geometry();notify('shown');if(d.autoFullscreen&&!document.fullscreenElement)document.documentElement.requestFullscreen({navigationUI:'hide'}).catch(()=>{});
 }
 window.addEventListener('message',e=>{const d=e.data;if(e.source!==window.opener||d?.session!==token)return;
  if(d.app==='vital-lab-vent-overlay'){if(d.type==='show')showVent(d);else if(d.key===ventKey&&d.type==='hide')hideVent()}
  else if(d.app==='vital-lab-sparrow'&&d.key===ventKey)ventFrame?.contentWindow.postMessage(d,'*');
 });
 window.addEventListener('beforeunload',()=>notify('hidden'));
 window.addEventListener('resize',geometry);
}

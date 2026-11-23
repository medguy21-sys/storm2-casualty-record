const Q=new URLSearchParams(location.search), key=Q.get('key')||'';
let live=null,received=0;
const $=id=>document.getElementById(id), esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function seconds(){return live?live.seconds+(live.running?(performance.now()-received)/1000:0):0}
function fmt(s){s=Math.floor(s);return [Math.floor(s/3600),Math.floor(s/60)%60,s%60].map(x=>String(x).padStart(2,'0')).join(':')}
async function api(p){const r=await fetch('/api/state'+(p?'':'?key='+encodeURIComponent(key)+'&view=control'),p?{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Key':key},body:JSON.stringify({request:crypto.randomUUID?.()||Date.now()+'-'+Math.random(),session:live.id,...p})}:{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||r.status);live=d;received=performance.now();return d}

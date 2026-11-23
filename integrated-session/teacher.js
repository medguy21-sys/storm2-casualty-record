// Bridge the full instructor console to the server-owned clock and selected bed.
(()=>{
const qp=new URLSearchParams(location.search),key=qp.get('key'),bed=+(qp.get('bed')||1);let ready=false,applying=false,dirty=false,busy=false,hub=null,lastAt=0,lastPerf=0,seq=0,counter=0;
const originalLog=log,originalSend=send;
let signature='';function sig(){return JSON.stringify({values:transition?null:['hr','spo2','sbp','dbp','rr','etco2'].map(k=>state[k]),transition,rhythm:state.rhythm,disconnect:state.disconnect,unavailable:state.unavailable,limits:state.limits,capno:state.syncoCapnoAttached,pattern:state.syncoCapnoPattern,pleth:state.syncoPlethPattern,ecg:state.syncoECGAttached,lead:state.syncoECGLead,sparrow:state.sparrow})}
function elapsed(){return hub?lastAt+(hub.running?(performance.now()-lastPerf)/1000:0):state.elapsed}
const oldProgress=progressScenario;stepClock=function(){state.elapsed=elapsed();state.paused=hub?!hub.running:true;clockLast=performance.now();if(transition&&hub){const p=Math.min(1,Math.max(0,(state.elapsed-transition.at)/transition.duration));for(const k of Object.keys(transition.target))state[k]=transition.start[k]+(transition.target[k]-transition.start[k])*p;syncControls()}};
log=function(m,o={}){state.elapsed=elapsed();originalLog(m,o);if(ready&&!applying){events.at(-1).sequence=++counter;dirty=true;queue()}};
send=function(){originalSend();if(ready&&!applying&&sig()!==signature){dirty=true;queue()}};
let timer;function queue(){if(timer)return;timer=setTimeout(()=>{timer=null;flush()},150)}
async function request(p){const r=await fetch('/api/state'+(p?'':'?key='+key+'&view=control'),p?{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Key':key},body:JSON.stringify({request:crypto.randomUUID(),session:hub.id,bed,...p})}:{cache:'no-store'});let d=await r.json();if(!r.ok)throw Error(d.error);return d}
window.labFlush=async()=>{for(let i=0;i<20&&busy;i++)await new Promise(r=>setTimeout(r,100));await flush();return !dirty&&!busy};
async function flush(){if(!ready||!dirty||busy)return;busy=true;dirty=false;const sent=sig();try{const rows=events.filter(e=>e.sequence>seq);const d=await request({action:'state',state:snapshot().state,transition,events:rows,console:{observationRuns:typeof observationRuns!=='undefined'?observationRuns:[],observationActiveId,observationViewId,exerciseId:typeof exerciseId!=='undefined'?exerciseId:null}});seq=d.beds[bed-1].instructorSeq;signature=sent}catch(e){dirty=true;status.textContent='NOT SYNCED: '+e.message}finally{busy=false}}
const status=document.createElement('div');status.style.cssText='font:11px system-ui;color:#00635e;margin-left:auto;white-space:nowrap';status.textContent='Connecting to shared session…';const feedback=document.getElementById('vlFeedback');if(feedback)feedback.append(status);else document.body.prepend(status);
['recordCase','replayCase','stopReplay','storeRecording','startExercise','reset','loadCase','preloadScript','librarySave','open','syncoOpen'].forEach(id=>{const b=document.getElementById(id);if(b){b.disabled=true;b.title='Use the shared host dashboard for this action in the pilot'}});
// Prevent local case loading/resetting/replay from replacing another device’s session.
loadLibraryBaseline=function(){status.textContent='Choose additional cases from the shared dashboard; this bed is fixed for this exercise.'};
for(const id of ['pause','quickPause']){const b=document.getElementById(id);if(b){b.onclick=null;b.addEventListener('click',async e=>{e.stopImmediatePropagation();try{await flush();hub=await request({action:'clock',running:!hub.running})}catch(err){status.textContent=err.message}},true)}}
const cycle=document.getElementById('syncoCycle');if(cycle){cycle.onclick=()=>request({action:'cycle'}).catch(e=>status.textContent=e.message)}
window.vitalPatientWindow=()=>parent.labMonitor?.();
const ventButton=document.getElementById('showSparrow'),originalVent=ventButton?.onclick;if(ventButton)ventButton.onclick=e=>{if(!parent.labMonitor?.()||parent.labMonitor().closed){status.textContent='Open the shared student monitor before showing the ventilator.';return}originalVent?.call(ventButton,e)};
for(const id of ['open','journeyOpen','journeyQuickOpen']){const button=document.getElementById(id);if(button){button.disabled=false;button.onclick=()=>parent.labOpenMonitor?.(1)}}
for(const id of ['goToReports','goToLog']){const button=document.getElementById(id);if(button)button.onclick=()=>parent.document.getElementById('debriefDialog').showModal()}
const legacy=document.getElementById('displayJourney');if(legacy)legacy.style.display='none';
const displaySetup=document.getElementById('journeySetup');if(displaySetup)displaySetup.onclick=()=>{parent.document.getElementById('connectionDetails').open=true};
async function poll(){try{
 if(dirty)await flush();const d=await request(),b=d.beds[bed-1];hub=d;lastAt=d.seconds;lastPerf=performance.now();child=parent.labMonitor?.()||null;
 if(!dirty&&!busy){applying=true;state={...b.state,silencedUntil:0};transition=b.transition;
 if(!ready){events=[];seq=counter=b.instructorSeq;observationRuns=b.console?.observationRuns||[];observationActiveId=b.console?.observationActiveId||'';observationViewId=b.console?.observationViewId||'';if(b.console?.exerciseId)exerciseId=b.console.exerciseId;observationRender();ready=true;}
 syncControls();render();signature=sig();originalSend();applying=false;}
 status.textContent='Shared course · Bed '+bed+' · '+(d.running?'Clock running':'Clock paused')+' · synchronized';
 }catch(e){status.textContent='HOST DISCONNECTED · controls held: '+e.message;state.paused=true}setTimeout(poll,300)}
// Checklist corrections may persist through their own save path without send().
document.addEventListener('click',e=>{if(ready&&e.target.closest('#instructor'))setTimeout(()=>{dirty=true;queue()},30)});
poll();
})();

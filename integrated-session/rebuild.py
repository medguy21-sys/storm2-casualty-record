from pathlib import Path
import argparse,json,re,shutil
args=argparse.Namespace(public=True)
ROOT=Path(__file__).resolve().parent; BASE=ROOT.parent; OUT=ROOT
source=(BASE/'vital-lab/index.html').read_text(encoding='utf-8')
index=source.index('const bundledLibrary=')+len('const bundledLibrary=');cases=json.JSONDecoder().raw_decode(source[index:])[0]
(OUT/'cases.json').write_text(json.dumps(cases,ensure_ascii=False),encoding='utf-8')
# Extract safe display-only asset: no instructor source scripts or checklist answers on student devices.
idx=source.index('frame.srcdoc=')+len('frame.srcdoc=');trace=json.JSONDecoder().raw_decode(source[idx:])[0].replace('<\\/script>','</script>')
trace=trace.replace('<b>BED 1 · SIM</b>','<b id="bedLabel">SIMULATED PATIENT</b>')
trace=trace.replace("const next=e.data;", "const next=e.data;document.getElementById('bedLabel').textContent='BED '+next.beds[0].number+' · SIM';")
# Missing ECG sensor hides the HR numeric too, consistent with capture provenance.
trace=trace.replace("$('hr').textContent=active?", "$('hr').textContent=active && bed.ecgAttached!==false?")
trace=trace.replace('</head>','<style>body.tile #fullscreen,body.tile #rotateDisplay,body.tile #monitorSound{display:none}</style></head>')
trace=trace.replace('</body>',"<script>if(new URLSearchParams(location.search).get('tile')==='1')document.body.classList.add('tile');</script></body>")
(OUT/'trace.html').write_text(trace,encoding='utf-8')
# Server owns automatic cuff measurement; prevent two competing clocks/cuff timers.
source=source.replace("if(!state.paused&&!playback?.held&&(state.syncoNextBP==null||state.elapsed>=state.syncoNextBP))", "if(false)")
source=source.replace("if(!playback && state.syncoNIBP?.measuring && Date.now()-state.syncoNIBP.startedAt>=5000)", "if(false)")
# Exact fallback match after inspecting the current generated adapter.
source=re.sub(r'if\(!state\.paused[^\n]{0,120}state\.elapsed>=state\.syncoNextBP\)\)', 'if(false)',source)
source=source.replace('if(!playback&&!state.paused&&(state.syncoNextBP==null||state.elapsed>=state.syncoNextBP))','if(false)')
source=re.sub(r'if\(!playback && state\.syncoNIBP\?\.measuring &&[^\n]{0,100}>=5000\)', 'if(false)',source)
pos=source.rfind('</body>');assert pos>0
source=source[:pos]+'<script src="/teacher.js?key=KEY"></script>'+source[pos:]
source=source.replace('window.VITAL_LAB_RELAY=', 'window.UNUSED_RELAY=')
# Shared monitors open from the console so the existing authenticated vent overlay has the correct opener.
source='\n'.join('function hideOverlayForField(){}' if line.startswith('function hideOverlayForField(){') else line for line in source.split('\n') if not line.startswith("document.getElementById('showSparrow').addEventListener('click'"))
# Scope legacy browser drafts/display slots to this integrated edition. Server state remains authoritative.
source=source.replace('darkwoods-mobile-', 'vital-unified-').replace('vital-lab-public-', 'vital-unified-public-')
(OUT/'console.html').write_text(source,encoding='utf-8')
doc=(BASE/'STORM2_Unified_Casualty_Record.html').read_text(encoding='utf-8')
assert doc.count("KEY='storm2_ucr_v1'")==1
doc=doc.replace("KEY='storm2_ucr_v1'","KEY=window.LabShared.key")
doc=doc.replace('STORM-2','Vital Lab').replace('STORM2_UCR_','Vital-Lab-Record_').replace('Ragged Edge Solutions','Vital Lab')
doc=doc.replace("['rr','RR','ЧД'],['spo2'", "['etco2','ETCO₂ mmHg','ETCO₂ мм рт.ст.'],['rr','RR','ЧД'],['spo2'")
doc=doc.replace("var VK=['hr','sbp','dbp','spo2','rr',", "var VK=['hr','sbp','dbp','spo2','rr','etco2',")
doc=doc.replace("<th>SpO₂</th><th>","<th>SpO₂</th><th>ETCO₂</th><th>")
doc=doc.replace("esc(x.spo2)+'</td><td>'+esc(x.hr)","esc(x.spo2)+'</td><td>'+esc(x.etco2)+'</td><td>'+esc(x.hr)")
doc=doc.replace("esc(x.time)+'</td><td>'+esc(x.role)","esc(x.time)+(x._lab?'<small style=\"display:block\">'+esc(x._lab.source==='auto-stream'?'Automatic feed':x._lab.source==='monitor-capture'?'Monitor capture':x._lab.source==='student-edited-capture'?'Edited capture':'Student-entered')+' · BP '+esc(x._lab.bpMeasuredSeconds==null?'unmeasured':Math.floor(x._lab.bpMeasuredSeconds)+'s')+'</small>':'')+'</td><td>'+esc(x.role)")
doc=doc.replace("function nowMs(){return Date.now()+(clk.applied?clk.srv:0)+clk.ref*1000;}","function nowMs(){return window.LabShared.nowMs();}")
doc=doc.replace('var d=new Date();return d.getFullYear()', 'var d=new Date(nowMs());return d.getUTCFullYear()')
doc=doc.replace('d.getMonth()', 'd.getUTCMonth()').replace('d.getDate()', 'd.getUTCDate()')
doc=doc.replace("d=new Date(),m=d.getHours()", "d=new Date(nowMs()),m=d.getUTCHours()")
doc=doc.replace('d.getHours()', 'd.getUTCHours()').replace('d.getMinutes()', 'd.getUTCMinutes()').replace('d.getSeconds()', 'd.getUTCSeconds()')
doc=doc.replace("function checkClock(){", "function checkClock(){clk.state='ok';clk.srv=0;clk.applied=false;return;")
doc=doc.replace('clearTimeout(saveT);saveT=setTimeout(sync,1500);',"clearTimeout(saveT);window.LabShared.changed(r,summary());")
doc=doc.replace('<script>','<script src="/student.js?key=KEY"></script><script src="/student-feed.js?key=KEY"></script><script>',1)
end=doc.rfind('})();\n</script>')
assert end>0
doc=doc[:end]+"window.LabShared.start({get:function(){return R()},replace:function(r){recs={};recs[r.id]=JSON.parse(JSON.stringify(r));cur=r.id;render()},metadata:function(server){var local=R();local._labFields=server._labFields||{};['meds','vitals','vent','body','stages','efx','voice','marks'].forEach(function(section){(local[section]||[]).forEach(function(row){var found=(server[section]||[]).find(function(v){return String(v.id)===String(row.id)});if(found)row._lab=found._lab})});['stamps','tq'].forEach(function(section){Object.keys(local[section]||{}).forEach(function(k){if(server[section]&&server[section][k])local[section][k]._lab=server[section][k]._lab})})},auto:function(server){var local=R(),automatic=(server.vitals||[]).filter(function(v){return v._lab&&v._lab.source==='auto-stream'}),ids=new Set(automatic.map(function(v){return String(v.id)}));local.vitals=(local.vitals||[]).filter(function(v){return !ids.has(String(v.id))}).concat(JSON.parse(JSON.stringify(automatic)));if(!document.activeElement||!document.activeElement.closest('#content input,#content textarea,#content select'))render()},summary:summary});\n"+doc[end:]
doc=doc.replace('</head>','<style>#labShared{display:flex;flex-wrap:wrap;gap:8px;align-items:center;background:#113e55;color:white;padding:10px;font:14px system-ui;position:sticky;top:0;z-index:10000}#labShared button,#labShared input,#labShared select{font:inherit;min-height:40px;padding:7px;border-radius:4px}#labShared button{background:#fff;color:#14384a;border:1px solid #8bb9c5}#labShared button:disabled{opacity:.5}#labStatus{font-weight:bold}#labClock{font-variant-numeric:tabular-nums}#app{height:calc(100dvh - 130px)}.lab-readonly #content{background:#f0f4f6}[data-ref]{display:none!important}</style></head>')
(OUT/'student.html').write_text(doc,encoding='utf-8')
# Runtime Python/JS files live alongside this rebuild script.
monitor=(ROOT/'src/monitor-template.html').read_text(encoding='utf-8').replace('OVERLAY','<script>'+ (ROOT/'src/ventilator_overlay_host.js').read_text(encoding='utf-8')+'</script>')
(OUT/'monitor.html').write_text(monitor,encoding='utf-8')
print('Built',OUT)

for name in ['display.html','observer.html']:
 shutil.copyfile(BASE/'vital-lab'/name,OUT/name)

shutil.copyfile(ROOT/'src/dashboard.html',OUT/'instructor.html')

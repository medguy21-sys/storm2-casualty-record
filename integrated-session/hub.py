"""Vital Lab shared-course pilot. Standard library only; simulated data only."""
import argparse, copy, csv, datetime, hashlib, html, io, json, mimetypes, os, secrets, socket, sqlite3, sys, threading, time, uuid, webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from camera_service import CameraManager
from comparison import clean_record, compare, record_changes

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
LOCK = threading.RLock()
KEYS = ('hr','spo2','sbp','dbp','rr','etco2')
def clone(x): return copy.deepcopy(x)
def stamp(s):
    s=int(s); return f'{s//3600:02}:{s//60%60:02}:{s%60:02}'
def blank(patient):
    return dict(id=patient,created=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),updated='',role='1',f={'name':'Patient 5-C'},stamps={},tq={},meds=[],vitals=[],vent=[],body=[],stages=[],efast={},efx=[],efastInt=30,sigs={},voice=[],marks=[])

class Hub:
    def __init__(self, data, assets=ROOT):
        self.cameras=CameraManager(Path(data).parent); self.assets=Path(assets); self.db=sqlite3.connect(data,check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS store (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, body TEXT)')
        self.cases=json.loads((self.assets/'cases.json').read_text(encoding='utf-8'))
        row=self.db.execute('SELECT body FROM store WHERE id=1').fetchone()
        self.s=json.loads(row[0]) if row else dict(id=str(uuid.uuid4()),seconds=0,running=False,startMs=int(datetime.datetime.combine(datetime.date.today(),datetime.time(8),datetime.timezone.utc).timestamp()*1000),capture=True,tokens={k:secrets.token_urlsafe(24) for k in ('admin','A','B','viewer')},beds=[None]*8)
        self.s.setdefault('traceSeconds',0)
        self.s.setdefault('documentationMode','capture' if self.s.get('capture',True) else 'manual')
        self.s.setdefault('autoChart',dict(enabled=False,intervalSeconds=60))
        for b in self.s['beds']:
            if b:b.setdefault('autoRevision',0);b.setdefault('nextAutoChart',None)
        self.s.setdefault('presentations',{id:dict(mode='Clinic',count=8,bed=1,camera='clinic1',revision=0) for id in ('vip1','vip2','vip3')})
        self.anchor=time.monotonic(); self.last_history=-1; self.last_save=0; self.cuffDeadlines={}
        if not row: self.assign(1,next((c['id'] for c in self.cases if c['id']=='storm2-d5-sc6-c'),self.cases[0]['id']))
        else:
            self.s['running']=False
            for b in self.s['beds']:
                if b and (b['state'].get('syncoNIBP') or {}).get('measuring'): b['state']['syncoNIBP']=None
            self.event('system',0,'Host restarted; clock paused. Review before resuming.')
        self.persist()
    def persist(self):
        self.db.execute('INSERT OR REPLACE INTO store VALUES(1,?)',(json.dumps(self.s),))
        if not getattr(self,'defer_commit',False):self.db.commit()
        self.last_save=time.monotonic()
    def event(self,stream,bed,message,**extra):
        extra.pop('scenarioSeconds',None);extra.pop('patientId',None);extra.pop('sessionId',None)
        e=dict(eventId=str(uuid.uuid4()),sessionId=self.s['id'],patientId=self.s['beds'][bed-1]['id'] if bed and self.s['beds'][bed-1] else None,caseId=self.s['beds'][bed-1]['case'] if bed and self.s['beds'][bed-1] else None,stream=stream,bed=bed,scenarioSeconds=round(self.s['seconds'],3),receivedUTC=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),message=message,**extra)
        self.db.execute('INSERT INTO audit(body) VALUES(?)',(json.dumps(e),)); return e
    def assign(self,n,case):
        item=next((x for x in self.cases if x['id']==case),None)
        if not item: raise ValueError('Unknown case')
        if self.s['beds'][n-1]: raise ValueError('Bed already assigned. Start a separate host data folder for another exercise.')
        pid=str(uuid.uuid4()); st=dict(patient='Patient 5-C' if case=='storm2-d5-sc6-c' else f'Patient · Bed {n}',libraryId=case,rhythm=item.get('rhythm') or 'sinus',disconnect=False,paused=True,elapsed=self.s['seconds'],silencedUntil=0,unavailable={},limits={'hr':[50,120],'spo2':[92,100],'sbp':[90,180],'rr':[8,30],'etco2':[25,50]},syncoCapnoAttached=False,syncoECGAttached=True,syncoECGLead='II',syncoNIBP=None,syncoNextBP=None)
        for k in KEYS:
            v=item['vitals'].get(k); st[k]=v if v is not None else 0
            if v is None: st['unavailable'][k]=True
        rec=blank(pid); rec['f']['name']=st['patient']
        self.s['beds'][n-1]=dict(id=pid,case=case,state=st,transition=None,writer='A',epoch=1,offer=None,revision=0,record=rec,summary='',console={},instructorSeq=0,autoRevision=0,nextAutoChart=None)
        self.event('system',n,'Patient assigned',patientId=pid,case=case,initialRecord=clone(rec))
    def bed(self,n):
        if not 1<=n<=8 or not self.s['beds'][n-1]: raise ValueError('Unassigned bed')
        return self.s['beds'][n-1]
    def cycle(self,n):
        b=self.bed(n); st=b['state']
        if (st.get('syncoNIBP') or {}).get('measuring'): return
        st['syncoNIBP']={'measuring':True,'startedAt':time.time()*1000,'seconds':self.s['seconds']}
        self.cuffDeadlines[n]=time.monotonic()+5
        self.event('monitor',n,'NIBP cycle started')
        self.event('monitor-history',n,'Displayed readings changed',readings=self.readings(b))
    def tick(self):
        now=time.monotonic(); dt=max(0,now-self.anchor); self.anchor=now
        self.s['traceSeconds']+=dt
        if self.s['running']: self.s['seconds']+=dt
        for n,b in enumerate(self.s['beds'],1):
            if not b: continue
            st=b['state']; st.update(elapsed=self.s['seconds'],paused=not self.s['running'])
            tr=b.get('transition')
            if tr:
                p=min(1,max(0,(self.s['seconds']-tr['at'])/max(.01,tr['duration'])))
                for k in KEYS:
                    if k in tr['target']: st[k]=tr['start'][k]+(tr['target'][k]-tr['start'][k])*p
                if p>=1: b['transition']=None; self.event('monitor',n,'Vital transition complete')
            if self.s['running'] and (st.get('syncoNextBP') is None or self.s['seconds']>=st['syncoNextBP']):
                self.cycle(n); st['syncoNextBP']=self.s['seconds']+300
            bp=st.get('syncoNIBP') or {}
            if bp.get('measuring') and time.monotonic()>=self.cuffDeadlines.get(n,float('inf')):
                good=not st['disconnect'] and not st['unavailable'].get('sbp') and not st['unavailable'].get('dbp') and st['sbp']>=st['dbp']
                st['syncoNIBP']=dict(measuring=False,sbp=round(st['sbp']) if good else None,dbp=round(st['dbp']) if good else None,seconds=self.s['seconds'])
                self.event('monitor',n,'NIBP measurement completed',reading=clone(st['syncoNIBP']))
                self.event('monitor-history',n,'Displayed readings changed',readings=self.readings(b))
        if self.s['running'] and self.s['documentationMode']=='stream' and self.s['autoChart']['enabled']:
            interval=self.s['autoChart']['intervalSeconds']
            for n,b in enumerate(self.s['beds'],1):
                if not b:continue
                if b.get('nextAutoChart') is None:b['nextAutoChart']=self.s['seconds']+interval
                if self.s['seconds']>=b['nextAutoChart']:
                    due=b['nextAutoChart'];self.append_observation(n,'auto-stream','host','Vital Lab automatic feed',scheduled=due);b['nextAutoChart']=self.s['seconds']+interval
        sec=int(self.s['seconds'])
        if sec!=self.last_history:
            self.last_history=sec
            for n,b in enumerate(self.s['beds'],1):
                if b: self.event('monitor-history',n,'Displayed readings',readings=self.readings(b))
        if now-self.last_save>1: self.persist()
    def append_observation(self,n,source,device,actor,scheduled=None):
        b=self.bed(n);d=self.readings(b);order=self.db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM audit').fetchone()[0];row={k:str(v) if v is not None else '' for k,v in d.items() if k in KEYS}
        row.update(id=str(uuid.uuid4()),time=stamp(self.s['startMs']/1000%86400+self.s['seconds']),role=b['record'].get('role','1'),_lab=dict(source=source,captureReadings=clone(d),createdScenarioSeconds=self.s['seconds'],documentedScenarioSeconds=self.s['seconds'],scenarioSeconds=self.s['seconds'],scheduledScenarioSeconds=scheduled,documentedEventSequence=order,captureEventSequence=order,createdEventSequence=order,bpMeasuredSeconds=d['bpMeasuredSeconds'],device=device,actor=actor))
        b['record']['vitals'].append(row)
        if source=='auto-stream':b['autoRevision']=b.get('autoRevision',0)+1
        else:b['revision']+=1
        self.event('auto-observation' if source=='auto-stream' else 'monitor-capture',n,'Automatic observation recorded' if source=='auto-stream' else 'Student captured displayed readings',device=device,actor=actor,readings=d,entryId=row['id'],entry=clone(row),revision=b['revision'],autoRevision=b.get('autoRevision',0))
        return row
    def readings(self,b):
        st=b['state']; un=st.get('unavailable',{}); d={k:None if st.get('disconnect') or un.get(k) else round(st[k]) for k in KEYS}
        if not st.get('syncoCapnoAttached'): d['rr']=d['etco2']=None
        if st.get('syncoECGAttached') is False: d['hr']=None
        bp=st.get('syncoNIBP') or {}; d['sbp']=bp.get('sbp') if not bp.get('measuring') and not st.get('disconnect') else None; d['dbp']=bp.get('dbp') if d['sbp'] is not None else None
        d['bpMeasuredSeconds']=bp.get('seconds') if d['sbp'] is not None else None
        # Match the student renderer's transient esophageal illustration.
        if d['etco2'] is not None and st.get('syncoCapnoPattern')=='esophageal':
            import math
            count=int(max(0,self.s['traceSeconds']-st.get('syncoCapnoTraceAt',0))*max(0,st['rr'])/60)
            d['etco2']=0 if count>=6 else round(d['etco2']*math.exp(-count*.9))
        return d
    def view(self,role,device=None,selected_bed=None,controls=False,known=None):
        out={k:clone(self.s[k]) for k in ('id','seconds','traceSeconds','running','startMs','capture','documentationMode','autoChart')}; out['beds']=[]
        for n,b in enumerate(self.s['beds'],1):
            if not b: out['beds'].append(None); continue
            st=b['state']; d=self.readings(b)
            safe=dict(number=n,id=b['id'],caseId=b['case'],patient=st['patient'],vitals=d,rhythm=st['rhythm'],spo2Attached=not st['disconnect'] and not st['unavailable'].get('spo2'),capnoAttached=bool(st.get('syncoCapnoAttached')) and not st['disconnect'],capnoPattern=st.get('syncoCapnoPattern','normal'),capnoPatternAt=st.get('syncoCapnoPatternAt',0),capnoBaseETCO2=st['etco2'],plethPattern=st.get('syncoPlethPattern','normal'),ecgAttached=st.get('syncoECGAttached',True) and not st['disconnect'],ecgLead=st.get('syncoECGLead','II'),nibp=clone(st.get('syncoNIBP')),nextAutoBP=st.get('syncoNextBP'),writer=b['writer'],epoch=b['epoch'],offer=clone(b['offer']),revision=b['revision'],autoRevision=b.get('autoRevision',0))
            if role in ('admin','student') and not controls and (role!='student' or selected_bed is None or selected_bed==n) and known!=(b['revision'],b.get('autoRevision',0)):
                safe.update(record=clone(b['record']),summary=b['summary'])
            safe['capnoPatternAt']=st.get('syncoCapnoTraceAt',0)
            if st['disconnect'] and safe['nibp']:
                safe['nibp']['sbp']=safe['nibp']['dbp']=None
            if role=='admin': safe.update(state=clone(st),transition=clone(b['transition']),console=clone(b['console']),instructorSeq=b['instructorSeq'])
            out['beds'].append(safe)
        if role=='admin': out.update(tokens=self.s['tokens'],cases=[dict(id=x['id'],name=x['name']) for x in self.cases])
        return out
    def act(self,role,device,p):
        action=p.get('action'); n=int(p.get('bed',1)); b=self.bed(n)
        if p.get('session')!=self.s['id']: raise ValueError('Session changed; reload before writing')
        if action in ('clock','auto-chart','documentation-mode','capture-toggle','assign','state','cycle','force-writer') and role!='admin': raise PermissionError('Instructor only')
        if action=='clock':
            self.s['running']=bool(p['running']); self.event('system',0,'Clock resumed' if self.s['running'] else 'Clock paused')
        elif action=='auto-chart':
            interval=p.get('intervalSeconds',60)
            if type(interval) is not int or not 10<=interval<=3600:raise ValueError('Choose an interval from 10 to 3600 seconds')
            self.s['autoChart']=dict(enabled=bool(p.get('enabled')),intervalSeconds=interval)
            for item in self.s['beds']:
                if item:item['nextAutoChart']=self.s['seconds']+interval
            self.event('system',0,'Automatic charting settings changed',settings=clone(self.s['autoChart']))
        elif action=='documentation-mode':
            if p.get('mode') not in ('manual','capture','stream'):raise ValueError('Unknown documentation mode')
            self.s['documentationMode']=p['mode'];self.s['capture']=p['mode']!='manual';
            if p['mode']!='stream':self.s['autoChart']['enabled']=False
            for item in self.s['beds']:
                if item:item['nextAutoChart']=None
            self.event('system',0,'Documentation mode changed: '+p['mode'])
        elif action=='capture-toggle': self.s['capture']=bool(p['enabled']);self.s['documentationMode']='capture' if p['enabled'] else 'manual'; self.event('system',0,'Monitor capture '+('enabled' if p['enabled'] else 'disabled'))
        elif action=='assign': self.assign(int(p['target']),p['case'])
        elif action=='cycle': self.cycle(n)
        elif action=='force-writer':
            if p['writer'] not in ('A','B'): raise ValueError('Unknown writer')
            b.update(writer=p['writer'],epoch=b['epoch']+1,offer=None); self.event('handover',n,'Instructor reassigned writer',to=p['writer'])
        elif action=='state':
            incoming=p['state']; before_readings=self.readings(b);old=b['state']; allowed=set(KEYS)|{'rhythm','disconnect','unavailable','limits','syncoCapnoAttached','syncoCapnoPattern','syncoCapnoPatternAt','syncoPlethPattern','syncoECGAttached','syncoECGLead','sparrow'}
            for k in KEYS:
                v=incoming.get(k)
                if not isinstance(v,(int,float)) or not 0<=v<=500: raise ValueError('Invalid vital '+k)
            if incoming.get('syncoCapnoPattern')!=old.get('syncoCapnoPattern') or incoming.get('syncoCapnoPatternAt')!=old.get('syncoCapnoPatternAt'):
                old['syncoCapnoTraceAt']=self.s['traceSeconds']
            for k in allowed:
                if k in incoming: old[k]=clone(incoming[k])
            b['transition']=clone(p.get('transition')); b['console']=clone(p.get('console',{}))
            if before_readings!=self.readings(b):self.event('monitor-history',n,'Displayed readings changed',readings=self.readings(b))
            for e in p.get('events',[]):
                seq=e.get('sequence',0)
                if seq>b['instructorSeq']:
                    b['instructorSeq']=seq; self.event('instructor',n,e.get('message','Instructor action'),observedScenarioSeconds=e.get('elapsed'),detail=e)
        elif action in ('save','capture','offer','cancel','accept'):
            if role!='student': raise PermissionError('Student device required')
            if action=='accept':
                if not b['offer'] or b['offer']['to']!=device: raise ValueError('No handover offered to this device')
                old=b['writer']; b.update(writer=device,epoch=b['epoch']+1,offer=None)
                self.event('handover',n,'Handover accepted',sender=old,receiver=device,actor=p.get('actor',device))
            else:
                if b['writer']!=device or p.get('epoch')!=b['epoch']: raise PermissionError('Writing ownership changed. Local draft retained; reload server chart.')
                if b['offer'] and action!='cancel': raise ValueError('Chart frozen while handover is pending')
                if p.get('revision')!=b['revision']: raise ValueError('Chart revision changed. Local draft retained; reload server chart.')
                if action=='save':
                    rec=p['record']
                    if not isinstance(rec,dict):raise ValueError('Invalid chart')
                    if rec.get('id')!=b['id']: raise ValueError('Patient mismatch')
                    if not isinstance(rec.get('vitals',[]),list) or any(not isinstance(v,dict) for v in rec.get('vitals',[])):raise ValueError('Invalid observations')
                    before=clone(b['record']);automatic={v['id']:v for v in before.get('vitals',[]) if v.get('_lab',{}).get('source')=='auto-stream'}
                    rec=clone(rec);rec['vitals']=[v for v in rec.get('vitals',[]) if v.get('id') not in automatic]
                    b['record']=clean_record(rec,before,self.s['seconds'],p.get('actor',device),device,self.db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM audit').fetchone()[0]);b['record']['vitals'].extend(clone(list(automatic.values()))); b['summary']=str(p.get('summary',''))[:200000]; b['revision']+=1
                    self.event('student-documentation',n,'Chart revision saved',actor=p.get('actor',device),device=device,revision=b['revision'],changes=record_changes(before,b['record']),entryScenarioSeconds=p.get('entrySeconds'),note='Documentation is not confirmation that care was performed.')
                elif action=='capture':
                    if not self.s['capture']: raise PermissionError('Instructor has disabled monitor capture')
                    self.append_observation(n,'monitor-capture',device,p.get('actor',device))
                elif action=='offer':
                    target='B' if device=='A' else 'A'; b['offer']=dict(sender=device,to=target,note=str(p.get('note',''))[:4000],scenarioSeconds=self.s['seconds']); self.event('handover',n,'Handover offered',**b['offer'])
                elif action=='cancel': b['offer']=None; self.event('handover',n,'Handover cancelled',device=device)
        else: raise ValueError('Unknown action')
        self.persist(); return self.view(role,device,selected_bed=n if role=='student' else None)
    def export(self):
        data=dict(format='Vital-Lab-unified-1',session={k:clone(v) for k,v in self.s.items() if k!='tokens'},events=[dict(seq=i,**json.loads(x)) for i,x in self.db.execute('SELECT seq,body FROM audit')],notice='Simulated exercise. Charted actions and instructor-confirmed care are separate evidence. No clinical outcome claim is inferred.')
        data['comparison']=compare(data);return data

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def reply(self,code,body,mime='application/json',filename=None):
        if not isinstance(body,bytes): body=(json.dumps(body,ensure_ascii=False) if mime=='application/json' else body).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type',mime+'; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer')
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.send_header('Content-Length',str(len(body)));
        try:self.end_headers();self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
    def auth(self,q):
        key=self.headers.get('X-Lab-Key') or q.get('key',[''])[0]
        for role,t in HUB.s['tokens'].items():
            if secrets.compare_digest(key,t):
                if role=='admin' and self.client_address[0] not in ('127.0.0.1','::1'): raise PermissionError('Instructor is available only on the host Surface')
                return ('student',role) if role in ('A','B') else (role,None)
        raise PermissionError('Use a current session link from the instructor dashboard')
    def do_GET(self):
        try:
            u=urlparse(self.path); q=parse_qs(u.query); path=u.path
            if path=='/favicon.ico':return self.reply(204,b'','image/x-icon')
            if path=='/':return self.reply(200,'<h1>Vital Lab</h1><p>Use the session link supplied by your instructor.</p>','text/html')
            role,device=self.auth(q)
            if path=='/api/camera/stream':
                if role not in ('admin','viewer'):raise PermissionError('Camera viewing is instructor/VIP only')
                return HUB.cameras.stream(self,q.get('id',[''])[0])
            with LOCK:
                HUB.tick()
                if path=='/api/cameras':
                    if role!='admin':raise PermissionError('Camera settings are instructor-only')
                    return self.reply(200,{'cameras':HUB.cameras.admin()})
                if path=='/api/inventory':return self.reply(200,{'displays':[],'error':'Use browser display detection or move the shared monitor manually.'})
                if path=='/api/read':
                    if role not in ('admin','viewer'):raise PermissionError('VIP link required')
                    v=HUB.view('viewer');return self.reply(200,dict(packet=v,ageSeconds=0,presentations=HUB.s['presentations'],cameras=HUB.cameras.catalog(),events=[]))
                if path in ('/comparison.csv','/comparison.html','/charts.csv'):
                    if role!='admin':raise PermissionError('Instructor export only')
                    data=HUB.export();return comparison_export(self,path,data)
                if path=='/api/state':
                    known=(int(q.get('revision',['-1'])[0]),int(q.get('autoRevision',['-1'])[0])) if role=='student' else None
                    return self.reply(200,HUB.view(role,device,selected_bed=int(q.get('bed',['1'])[0]) if role=='student' else None,controls=q.get('view',[''])[0]=='control' and role=='admin',known=known))
                if path.startswith('/export'):
                    if role!='admin':raise PermissionError('Instructor export only')
                    data=HUB.export()
                    if path.endswith('.json'):return self.reply(200,data,filename='Vital-Lab-combined-debrief.json')
                    if path.endswith('.csv'):
                        f=io.StringIO(newline=''); w=csv.writer(f); w.writerow(['session_id','patient_id','case_id','entry_id','event_id','sequence','stream','bed','scenario_seconds','scenario_time','received_utc','actor','message',*KEYS,'bp_measured_scenario_seconds','details_json'])
                        for e in data['events']:
                            d=e.get('readings',{})
                            # Spreadsheet-safe text: student notes are untrusted data.
                            cell=lambda x: "'"+str(x) if isinstance(x,str) and x.startswith(('=','+','-','@')) else x
                            w.writerow([cell(x) for x in [HUB.s['id'],e.get('patientId',''),e.get('caseId',''),e.get('entryId',''),e.get('eventId',''),e['seq'],e['stream'],e['bed'],e['scenarioSeconds'],stamp(e['scenarioSeconds']),e['receivedUTC'],e.get('actor',e.get('device','')),e['message'],*[d.get(k,'') for k in KEYS],d.get('bpMeasuredSeconds',''),json.dumps({k:v for k,v in e.items() if k not in ('seq','stream','bed','scenarioSeconds','receivedUTC','message')},ensure_ascii=False)]])
                        return self.reply(200,'\ufeff'+f.getvalue(),'text/csv','Vital-Lab-combined-events.csv')
                    return self.reply(200,report(data,q.get('audience',['student'])[0]),'text/html','Vital-Lab-debrief.html')
                if path in ('/instructor','/console') and role!='admin':raise PermissionError('Instructor only')
                if path=='/student' and role!='student':raise PermissionError('Student link required')
                files={'/observer':'observer.html','/display':'display.html','/instructor':'instructor.html','/console':'console.html','/student':'student.html','/monitor':'monitor.html','/trace':'trace.html','/teacher.js':'teacher.js','/student.js':'student.js','/student-feed.js':'student-feed.js','/common.js':'common.js'}
                if path not in files:raise ValueError('Not found')
                f=HUB.assets/files[path]
                body=f.read_bytes()
                if f.suffix=='.html':
                    # Tokens originate on the host; never interpolate user-supplied HTML.
                    tok=HUB.s['tokens'][device if role=='student' else role]
                    text=body.decode('utf-8').replace('key=KEY','key='+tok).replace('HOSTIP',lan_ip()).replace('__TOKEN__',HUB.s['tokens']['viewer']).replace('VIEWER_KEY',HUB.s['tokens']['viewer'])
                    if path=='/console':
                        conf=dict(key=HUB.s['tokens']['admin'],viewer=HUB.s['tokens']['viewer'],observer='http://'+lan_ip()+':'+str(self.server.server_address[1])+'/observer?key='+HUB.s['tokens']['viewer'])
                        text=text.replace('</head>','<script>window.VITAL_LAB_SHARED=true;window.VITAL_LAB_RELAY='+json.dumps(conf)+'</script></head>',1)
                    body=text.encode('utf-8')
                return self.reply(200,body,mimetypes.guess_type(str(f))[0] or 'text/plain')
        except PermissionError as e:self.reply(403,{'error':str(e)})
        except (ValueError,KeyError,FileNotFoundError) as e:self.reply(400,{'error':str(e)})
    def do_POST(self):
        try:
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'):raise PermissionError('Cross-origin write refused')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON required')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=3000000:raise ValueError('Invalid request size')
            path=urlparse(self.path).path
            if path not in ('/api/state','/api/cameras','/api/vip','/api/publish'):raise PermissionError('Unknown control endpoint')
            p=json.loads(self.rfile.read(length)); q=parse_qs(urlparse(self.path).query)
            with LOCK:
                role,device=self.auth(q); HUB.tick()
                if path!='/api/state':
                    if role!='admin':raise PermissionError('Instructor only')
                    if path=='/api/cameras':return self.reply(200,HUB.cameras.save(p))
                    if path=='/api/publish':return self.reply(200,{'ok':True,'source':'shared session owns patient state'})
                    return self.reply(200,set_vip(p))
                request=p.get('request')
                if not isinstance(request,str) or len(request)>150:raise ValueError('Request ID required')
                request=role+str(device)+request
                prev=HUB.db.execute('SELECT body FROM requests WHERE id=?',(request,)).fetchone()
                digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
                if prev:
                    if prev[0] not in ('ok',digest):raise ValueError('Request ID reused with changed content')
                    return self.reply(200,HUB.view(role,device,selected_bed=int(p.get('bed',1)) if role=='student' else None))
                before=clone(HUB.s);deadlines=clone(HUB.cuffDeadlines);HUB.db.execute('SAVEPOINT client_action');HUB.defer_commit=True
                try:
                    result=HUB.act(role,device,p);HUB.db.execute('INSERT INTO requests VALUES(?,?)',(request,digest));HUB.db.execute('RELEASE client_action');HUB.db.commit()
                except Exception:
                    HUB.db.execute('ROLLBACK TO client_action');HUB.db.execute('RELEASE client_action');HUB.s=before;HUB.cuffDeadlines=deadlines;raise
                finally:HUB.defer_commit=False
                self.reply(200,result)
        except PermissionError as e:self.reply(403,{'error':str(e)})
        except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:self.reply(409,{'error':str(e)})

def report(data,audience):
    if audience=='command':return command_report(data)
    esc=lambda x:html.escape(str(x)); admin=audience=='instructor'; s=data['session']; parts=['<!doctype html><meta charset="utf-8"><title>Vital Lab combined debrief</title><style>body{font:16px system-ui;max-width:1100px;margin:32px auto;color:#142a36}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #bccbd3;padding:8px;text-align:left;vertical-align:top}pre{white-space:pre-wrap}section{break-inside:avoid}button{padding:12px}@media print{button{display:none}}</style><button onclick="print()">Print / Save PDF</button><h1>Vital Lab · Combined debrief</h1>','<p>'+esc(data['notice'])+'</p>',f'<p>Session {esc(s["id"])} · Duration {stamp(s["seconds"])} · {"Instructor detail" if admin else "Student AAR"}</p>']
    parts.append('<p>Streams: monitor observations; student documentation; instructor-confirmed checklist marks. A missing chart entry does not establish that care was omitted. Capture copies displayed readings; it does not validate assessments.</p>')
    for n,b in enumerate(s['beds'],1):
        if not b:continue
        parts.append(f'<section><h2>Bed {n} · {esc(b["state"]["patient"])}</h2><p>Current writer: Student {b["writer"]} · Chart revision {b["revision"]}</p><h3>Student chart</h3>')
        parts.append('<h3>Recorded observations</h3><table><tr><th>Chart time</th><th>HR</th><th>SpO₂</th><th>BP</th><th>RR</th><th>ETCO₂</th><th>Source / BP age</th></tr>')
        for v in b['record'].get('vitals',[]):
            meta=v.get('_lab',{});src=meta.get('source','Student-entered');bp_at=meta.get('bpMeasuredSeconds')
            if bp_at is not None:src+=' · BP measured at '+stamp(bp_at)
            parts.append('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in [v.get('time',''),v.get('hr',''),v.get('spo2',''),str(v.get('sbp',''))+'/'+str(v.get('dbp','')),v.get('rr',''),v.get('etco2',''),src])+'</tr>')
        parts.append('</table>')
        # Complete structured sections retain all documentation, including corrections.
        for k,v in b['record'].items():
            if v and k not in ('id','created','updated','voice','vitals'):parts.append('<details><summary>'+esc({'f':'Patient, assessments and clinical fields','stamps':'Timestamped actions','tq':'Tourniquets','meds':'Documented medications / fluids / blood','vent':'Ventilation and anesthesia entries','body':'Injury map','stages':'Care stages','efx':'Serial eFAST','sigs':'Signatures','marks':'Student timeline marks'}.get(k,k))+'</summary><pre>'+esc(json.dumps(v,ensure_ascii=False,indent=2))+'</pre></details>')
        parts.append('</section>')
    parts.append(comparison_table(data))
    parts.append('<h2>Shared timeline</h2><table><tr><th>Time</th><th>Bed</th><th>Evidence stream</th><th>Entry</th></tr>')
    for e in data['events']:
        if e['stream']=='monitor-history':continue
        if not admin and e['stream']=='instructor':
            d=e.get('detail',{})
            if d.get('type') not in ('timing','intervention','observation'):continue
        msg=e['message']
        if e['stream']=='monitor-capture':msg+=' '+json.dumps(e['readings'],ensure_ascii=False)
        if e['stream']=='handover':msg+=' '+str(e.get('sender',''))+' → '+str(e.get('receiver',e.get('to','')))+' '+str(e.get('note',''))
        parts.append('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in (stamp(e['scenarioSeconds']),e['bed'],e['stream'],msg))+'</tr>')
    parts.append('</table>')
    if admin:parts.append('<p>JSON export includes immutable chart revisions, complete instructor snapshots and 1-second monitor history. Keep instructor exports separate from student handouts.</p>')
    return ''.join(parts)

def command_report(data):
    active=[b for b in data['session']['beds'] if b];comparable=[r for r in data['comparison'] if r['field_source'] in ('student-entered','student-edited') and r['charted'] is not None and r['displayed'] is not None]
    values=[('Simulated patients',len(active)),('Chart revisions',sum(e['stream']=='student-documentation' for e in data['events'])),('Monitor captures',sum(e['stream']=='monitor-capture' for e in data['events'])),('Accepted handovers',sum(e['stream']=='handover' and e['message']=='Handover accepted' for e in data['events'])),('Automatic observations',sum(e['stream']=='auto-observation' for e in data['events'])),('Comparable student-entered/edited fields',len(comparable)),('Student-entered/edited fields matching displayed readings',sum(r['status']=='match' for r in comparable))]
    return '<!doctype html><meta charset="utf-8"><title>Vital Lab · Command summary</title><style>body{font:18px system-ui;max-width:850px;margin:32px auto}td,th{padding:12px;border:1px solid #abc}table{border-collapse:collapse}</style><h1>Vital Lab · Team exercise summary</h1><p>Exercise duration '+stamp(data['session']['seconds'])+'</p><table><tr><th>Activity</th><th>Count</th></tr>'+''.join('<tr><td>'+label+'</td><td>'+str(value)+'</td></tr>' for label,value in values)+'</table><p>These measures describe exercise participation and documentation. Demonstrating improvement requires comparable baseline or repeat exercises; this report does not estimate patient outcomes.</p>'

def set_vip(p):
    target=p.get('target');mode=p.get('mode');bed=p.get('bed',1);count=p.get('count',8);camera=p.get('camera','')
    if target not in ('all','vip1','vip2','vip3') or mode not in ('Camera','Clinic','Truck','Field') or type(bed) is not int or not 1<=bed<=8 or count not in (2,4,8):raise ValueError('Invalid VIP view')
    if mode=='Camera' and camera not in {c['id'] for c in HUB.cameras.catalog()}:raise ValueError('Unknown camera')
    for id in HUB.s['presentations'] if target=='all' else [target]:
        old=HUB.s['presentations'][id];HUB.s['presentations'][id]=dict(mode=mode,bed=bed,count=count,camera=camera,revision=old['revision']+1)
    HUB.event('display',bed,'VIP presentation changed',target=target,mode=mode,camera=camera);HUB.persist()
    return dict(ok=True,presentations=HUB.s['presentations'])

def comparison_table(data):
    esc=lambda x:html.escape('' if x is None else str(x))
    out=['<h2>Charted observations compared with the monitor</h2><p>Comparison uses the student-stated chart time or the original capture. Receipt time and documentation delay are retained separately. Differences are prompts for review, not scores or proof that care was missed.</p><table><tr><th>Bed / chart time</th><th>Field</th><th>Charted</th><th>Displayed</th><th>Difference</th><th>Source / status</th></tr>']
    for r in data['comparison']:
        if r['charted'] is None and not r['charted_text'].strip():continue
        values=[str(r['bed'])+' / '+r['chart_time'],r['field'],r['charted_text'],r['displayed'],r['difference'],r['source']+' / '+r['status']]
        out.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in values)+'</tr>')
    out.append('</table>');return ''.join(out)

def comparison_export(handler,path,data):
    if path=='/comparison.html':return handler.reply(200,'<!doctype html><meta charset="utf-8"><title>Vital Lab comparison</title><style>body{font:16px system-ui;padding:24px;color:#173137}table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #abc}</style><h1>Vital Lab · Documentation comparison</h1>'+comparison_table(data),'text/html','Vital-Lab-comparison.html')
    rows=data['comparison']
    if path=='/charts.csv':
        rows=[]
        for bed,b in enumerate(data['session']['beds'],1):
            if not b:continue
            for section,value in b['record'].items():
                if section=='_labFields' or not isinstance(value,(dict,list)):continue
                for entry in value if isinstance(value,list) else [dict(value=v,field_name=k,id=section+':'+k) if not isinstance(v,dict) else dict(v,field_name=k,id=v.get('id',section+':'+k)) for k,v in value.items()]:
                    meta=(b['record'].get('_labFields',{}).get(entry.get('field_name',''),{}) if section=='f' else entry.get('_lab',{})) if isinstance(entry,dict) else {}
                    rows.append(dict(session_id=data['session']['id'],patient_id=b['id'],bed=bed,case_id=b['case'],section=section,field_name=entry.get('field_name','') if isinstance(entry,dict) else '',entry_id=entry.get('id','') if isinstance(entry,dict) else '',chart_time=entry.get('time',entry.get('t','')) if isinstance(entry,dict) else '',documented_scenario_seconds=meta.get('documentedScenarioSeconds',meta.get('scenarioSeconds')),source=meta.get('source','student-entered'),actor=meta.get('actor',''),details_json=json.dumps(entry,ensure_ascii=False)))
    columns=list(rows[0]) if rows else (['session_id','patient_id','bed','entry_id','field','charted','displayed','difference','status'] if path=='/comparison.csv' else ['session_id','patient_id','bed','section','entry_id','details_json'])
    f=io.StringIO(newline='');w=csv.writer(f);w.writerow(columns)
    for r in rows:w.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in (r.get(k,'') for k in columns)])
    return handler.reply(200,'\ufeff'+f.getvalue(),'text/csv','Vital-Lab-'+('comparison' if path=='/comparison.csv' else 'charts')+'.csv')

def lan_ip():
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('192.0.2.1',80));ip=s.getsockname()[0];s.close();return ip
    except OSError:return socket.gethostbyname(socket.gethostname())
def main():
    global HUB
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8785);ap.add_argument('--data');ap.add_argument('--no-browser',action='store_true');a=ap.parse_args()
    home=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    folder=Path(a.data) if a.data else home/'Unified-Data';folder.mkdir(parents=True,exist_ok=True)
    HUB=Hub(folder/'session.sqlite3'); server=ThreadingHTTPServer(('0.0.0.0',a.port),Handler);server.daemon_threads=True;actual_port=server.server_address[1]
    def worker():
        while True:
            time.sleep(.1)
            with LOCK:HUB.tick()
    threading.Thread(target=worker,daemon=True).start()
    url=f'http://127.0.0.1:{actual_port}/instructor?key='+HUB.s['tokens']['admin']
    print('Vital Lab integrated session · simulated data only\nKeep this host running. Close with Ctrl+C.\nInstructor: '+url+'\nStudent network address: http://'+lan_ip()+':'+str(actual_port),flush=True)
    if not a.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:
        with LOCK:HUB.tick();HUB.s['running']=False;HUB.persist()
        server.server_close()
if __name__=='__main__':main()

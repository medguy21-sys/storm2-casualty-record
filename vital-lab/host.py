"""Read-only observer relay and Windows inventory companion; physiology stays in instructor browser."""
import argparse,csv,hashlib,html,io,json,math,os,secrets,socket,sqlite3,subprocess,sys,threading,time,webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from camera_service import CameraManager
ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent));LOCK=threading.RLock()
CAMERAS={'gopro':'GoPro','patient':'Patient','clinic1':'Clinic 1','clinic2':'Clinic 2'}
def sanitize_packet(p):
 def number(v,lo=0,hi=8640000):return round(v,3) if isinstance(v,(int,float)) and not isinstance(v,bool) and lo<=v<=hi else None
 out=dict(type='state',seconds=number(p.get('seconds')) or 0,traceSeconds=number(p.get('traceSeconds')) or 0,running=p.get('running') is True,beds=[])
 for i,b in enumerate((p.get('beds') or [])[:8]):
  if not isinstance(b,dict):out['beds'].append(None);continue
  bp=b.get('nibp');bp=dict(measuring=bp.get('measuring') is True,sbp=number(bp.get('sbp'),0,300),dbp=number(bp.get('dbp'),0,300),seconds=number(bp.get('seconds'))) if isinstance(bp,dict) else None
  out['beds'].append(dict(number=i+1,caseId=str(b.get('caseId',''))[:100],patient=str(b.get('patient','Casualty '+str(i+1)))[:60],vitals={k:number((b.get('vitals') or {}).get(k),0,500) for k in ('hr','spo2','sbp','dbp','rr','etco2')},rhythm=b.get('rhythm') if b.get('rhythm') in ('sinus','af','vf','asystole') else None,spo2Attached=b.get('spo2Attached') is True,capnoAttached=b.get('capnoAttached') is True,ecgAttached=b.get('ecgAttached') is True,ecgLead=b.get('ecgLead') if b.get('ecgLead') in ('I','II','III') else 'II',plethPattern=str(b.get('plethPattern','normal'))[:40],capnoPattern=str(b.get('capnoPattern','normal'))[:40],capnoPatternAt=number(b.get('capnoPatternAt')) or 0,capnoBaseETCO2=number(b.get('capnoBaseETCO2'),0,200),nibp=bp,nextAutoBP=number(b.get('nextAutoBP')),seconds=number(b.get('seconds')) or 0,running=b.get('running') is True))
 out['beds'] += [None]*(8-len(out['beds']));return out
class Relay:
 def __init__(self,path):
  self.cameras=CameraManager(Path(path).parent);self.db=sqlite3.connect(path,check_same_thread=False);self.db.executescript('CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT);CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,body TEXT);CREATE TABLE IF NOT EXISTS latest(id INTEGER PRIMARY KEY,body TEXT);')
  self.tokens={}
  for role in ('admin','viewer'):
   row=self.db.execute('SELECT v FROM settings WHERE k=?',(role,)).fetchone();self.tokens[role]=row[0] if row else secrets.token_urlsafe(24);self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(role,self.tokens[role]))
  row=self.db.execute("SELECT v FROM settings WHERE k='vip-presentations'").fetchone();self.presentations=json.loads(row[0]) if row else {k:dict(mode='Clinic',count=8,bed=1,camera='gopro',revision=0) for k in ('vip1','vip2','vip3')}
  self.db.commit();row=self.db.execute('SELECT body FROM latest WHERE id=1').fetchone();self.packet=json.loads(row[0]) if row else None;self.received=None;self.inventory_cache=None;self.inventory_at=-999
 def publish(self,data):
  self.packet=sanitize_packet(data.get('packet',{}));self.received=time.monotonic();self.db.execute('INSERT OR REPLACE INTO latest VALUES(1,?)',(json.dumps(self.packet),))
  for e in data.get('events',[])[:2000]:
   if e.get('type') not in ('display','timing','observation'):continue
   event=dict(id=str(e.get('id',''))[:100],type=e['type'],bed=int(e.get('bed',1)),seconds=e.get('seconds',0),message=str(e.get('message',''))[:500],receivedUTC=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
   if not isinstance(event['seconds'],(int,float)):continue
   self.db.execute('INSERT OR IGNORE INTO events VALUES(?,?)',(event['id'],json.dumps(event)))
  self.db.commit()
 def set_vip(self,d):
  target=d.get('target');mode=d.get('mode');bed=d.get('bed',1);count=d.get('count',8);camera=d.get('camera','gopro')
  if target not in ('all','vip1','vip2','vip3') or mode not in ('Clinic','Truck','Field','Camera') or type(bed) is not int or not 1<=bed<=8 or type(count) is not int or count not in (2,4,8) or (mode=='Camera' and camera not in {c['id'] for c in self.cameras.catalog()}):raise ValueError('Invalid VIP view selection')
  revision=max(p.get('revision',0) for p in self.presentations.values())+1;utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
  for channel in self.presentations if target=='all' else [target]:self.presentations[channel]=dict(mode=mode,count=count,bed=bed,camera=camera,revision=revision,updatedUTC=utc)
  self.db.execute("INSERT OR REPLACE INTO settings VALUES('vip-presentations',?)",(json.dumps(self.presentations),))
  seconds=d.get('seconds',self.packet.get('seconds',0) if self.packet else 0)
  if not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or not 0<=seconds<=8640000:seconds=0
  label='Camera '+next(c['label'] for c in self.cameras.catalog() if c['id']==camera) if mode=='Camera' else str(count)+'-bed overview' if mode=='Clinic' else 'Bed '+str(bed)+' '+mode
  event=dict(id='vip-'+secrets.token_urlsafe(18),type='display',bed=bed,seconds=seconds,message='VIP view: '+target+' → '+label,receivedUTC=utc)
  self.db.execute('INSERT INTO events VALUES(?,?)',(event['id'],json.dumps(event)));self.db.commit()
  return dict(ok=True,presentations=self.presentations)
 def view(self):return dict(packet=self.packet,ageSeconds=None if self.received is None else time.monotonic()-self.received,presentations=self.presentations,cameras=self.cameras.catalog(),events=[json.loads(x) for x, in reversed(self.db.execute('SELECT body FROM events ORDER BY rowid DESC LIMIT 150').fetchall())])
 def inventory(self):
  if self.inventory_cache is not None and time.monotonic()-self.inventory_at<8:return self.inventory_cache
  try:
   p=subprocess.run(['powershell.exe','-NoProfile','-File',str(ROOT/'inventory.ps1')],capture_output=True,text=True,timeout=18,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if p.returncode:raise RuntimeError(p.stderr[:300])
   self.inventory_cache=json.loads(p.stdout.lstrip('\ufeff'))
  except Exception as e:self.inventory_cache={'displays':[],'error':str(e)[:300]}
  self.inventory_at=time.monotonic();return self.inventory_cache
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def reply(self,status,body,mime='application/json',file=None):
  if not isinstance(body,bytes):body=(json.dumps(body,ensure_ascii=False) if mime=='application/json' else body).encode('utf-8')
  self.send_response(status);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff')
  if file:self.send_header('Content-Disposition','attachment; filename="'+file+'"')
  self.end_headers();self.wfile.write(body)
 def auth(self,q):
  key=self.headers.get('X-Lab-Key') or q.get('key',[''])[0]
  for role,t in RELAY.tokens.items():
   if secrets.compare_digest(key,t):
    if role=='admin' and self.client_address[0] not in ('127.0.0.1','::1'):raise PermissionError('Instructor is host-only')
    return role
  raise PermissionError('Use the session link provided by the instructor')
 def do_GET(self):
  try:
   u=urlparse(self.path);q=parse_qs(u.query)
   if u.path in ('/src/display-template.js','/src/policy.js','/src/journey.js','/src/operator-ui.js'):
    return self.reply(200,(ROOT/u.path.lstrip('/')).read_bytes(),'text/javascript')
   if u.path=='/favicon.ico':return self.reply(204,b'','image/x-icon')
   if u.path=='/':return self.reply(200,'<h1>Vital Lab observer relay</h1><p>Use your instructor-provided link.</p>','text/html')
   role=self.auth(q)
   if u.path=='/api/cameras':
    if role!='admin':raise PermissionError('Camera settings are host-only')
    return self.reply(200,{'cameras':RELAY.cameras.admin()})
   if u.path=='/api/camera/stream':return RELAY.cameras.stream(self,q.get('id',[''])[0])
   if u.path=='/api/inventory':
    if role!='admin':raise PermissionError('Host-only inventory')
    return self.reply(200,RELAY.inventory())
   with LOCK:
    if u.path=='/api/read':return self.reply(200,RELAY.view())
    if u.path=='/observer.csv':
     f=io.StringIO(newline='');w=csv.writer(f);w.writerow(['type','bed','scenario_seconds','message','received_utc'])
     for x, in RELAY.db.execute('SELECT body FROM events ORDER BY rowid'):
      e=json.loads(x);vals=[e['type'],e['bed'],e['seconds'],e['message'],e['receivedUTC']];w.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@')) else v for v in vals])
     return self.reply(200,'\ufeff'+f.getvalue(),'text/csv','vital-lab-observer-events.csv')
   files={'/instructor':'index.html','/observer':'observer.html','/display':'display.html','/guide':'guide.html','/journey.svg':'journey.svg'}
   if u.path=='/instructor' and role!='admin':raise PermissionError('Instructor is private')
   if u.path not in files:raise ValueError('Not found')
   data=(ROOT/files[u.path]).read_text(encoding='utf-8')
   if u.path=='/instructor':
    conf=dict(key=RELAY.tokens['admin'],viewer=RELAY.tokens['viewer'],observer='http://'+LAN+':'+str(PORT)+'/observer?key='+RELAY.tokens['viewer'])
    pos=data.index('</head>');data=data[:pos]+'<script>window.VITAL_LAB_RELAY='+json.dumps(conf)+'</script>'+data[pos:]
   if u.path=='/display':data=data.replace('__TOKEN__',RELAY.tokens['viewer'])
   if u.path in ('/observer','/guide'):data=data.replace('VIEWER_KEY',RELAY.tokens['viewer'])
   self.reply(200,data,'image/svg+xml' if u.path.endswith('.svg') else 'text/html')
  except PermissionError as e:self.reply(403,{'error':str(e)})
  except (ValueError,FileNotFoundError) as e:self.reply(400,{'error':str(e)})
 def do_POST(self):
  try:
   action=urlparse(self.path).path
   if action not in ('/api/publish','/api/vip','/api/cameras'):raise PermissionError('No observer control API')
   origin=self.headers.get('Origin')
   if origin and urlparse(origin).netloc!=self.headers.get('Host'):raise PermissionError('Cross-origin write refused')
   if self.auth(parse_qs(urlparse(self.path).query))!='admin':raise PermissionError('Observers cannot publish or control patients')
   if not self.headers.get('Content-Type','').startswith('application/json'):raise ValueError('JSON required')
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=2000000:raise ValueError('Invalid body size')
   d=json.loads(self.rfile.read(n))
   with LOCK:
    if action=='/api/cameras':result=RELAY.cameras.save(d)
    elif action=='/api/vip':result=RELAY.set_vip(d)
    else:RELAY.publish(d);result={'ok':True}
   self.reply(200,result)
  except PermissionError as e:self.reply(403,{'error':str(e)})
  except (ValueError,TypeError,KeyError) as e:self.reply(409,{'error':str(e)})
def main():
 global RELAY,LAN,PORT
 ap=argparse.ArgumentParser();ap.add_argument('--check-video',action='store_true');ap.add_argument('--port',type=int,default=8782);ap.add_argument('--data');ap.add_argument('--no-browser',action='store_true');a=ap.parse_args();PORT=a.port
 if a.check_video:
  import av
  codec=av.CodecContext.create('mjpeg','w');codec.width=320;codec.height=240;codec.pix_fmt='yuvj420p';codec.open();frame=av.VideoFrame(320,240,'yuvj420p');assert bytes(codec.encode(frame)[0])[:2]==b'\xff\xd8';print('Video decoder and JPEG encoder available',flush=True);return
 home=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent;data=Path(a.data) if a.data else home/'Observer-Data';data.mkdir(parents=True,exist_ok=True);RELAY=Relay(data/'observer.sqlite3')
 try:
  s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('192.0.2.1',80));LAN=s.getsockname()[0];s.close()
 except OSError:LAN=socket.gethostbyname(socket.gethostname())
 server=ThreadingHTTPServer(('0.0.0.0',PORT),Handler);PORT=server.server_address[1];server.daemon_threads=True;url='http://127.0.0.1:'+str(PORT)+'/instructor?key='+RELAY.tokens['admin']
 print('Vital Lab Mobile · Instructor: '+url+'\nObserver: http://'+LAN+':'+str(PORT)+'/observer?key='+RELAY.tokens['viewer']+'\nKeep this host and the instructor browser running. Ctrl+C stops the observer relay; local patient display state is not reset.',flush=True)
 if not a.no_browser:webbrowser.open(url)
 try:server.serve_forever()
 except KeyboardInterrupt:server.server_close()
if __name__=='__main__':main()

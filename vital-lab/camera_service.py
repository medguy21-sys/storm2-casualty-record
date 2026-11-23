"""Shared, demand-driven RTSP decoders. Credentials never leave this host."""
import base64, ctypes, ipaddress, json, os, re, threading, time
from pathlib import Path
from urllib.parse import quote

DEFAULTS={'gopro':'GoPro','patient':'Patient','clinic1':'Clinic 1','clinic2':'Clinic 2'}
def protect(value, decrypt=False):
    if os.name!='nt':raise ValueError('Remembering passwords requires Windows; use session-only login.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    raw=base64.b64decode(value) if decrypt else value.encode()
    buffer=ctypes.create_string_buffer(raw);source=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));dest=Blob()
    crypt=ctypes.windll.crypt32
    ok=crypt.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(dest)) if decrypt else crypt.CryptProtectData(ctypes.byref(source),'Vital Lab camera',None,None,None,1,ctypes.byref(dest))
    if not ok:raise ValueError('Windows could not protect or unlock this camera password.')
    try:
        data=ctypes.string_at(dest.data,dest.size)
        return data.decode() if decrypt else base64.b64encode(data).decode()
    finally:ctypes.windll.kernel32.LocalFree(dest.data)

class Camera:
    def __init__(self, config, password=''):
        self.config=config;self.password=password;self.lock=threading.Condition();self.frame=None;self.sequence=0;self.last_frame=0;self.demand=0;self.thread=None;self.stop=threading.Event();self.status='Ready' if password else 'Login required';self.error_type=None
    def public(self):
        return dict(id=self.config['id'],label=self.config['label'],configured=bool(self.password),status=self.status,frameAge=None if not self.last_frame else round(time.monotonic()-self.last_frame,1))
    def request(self):
        if self.error_type in ('HTTPUnauthorizedError','HTTPForbiddenError'):return
        with self.lock:
            self.demand=time.monotonic()
            if self.password and (not self.thread or not self.thread.is_alive()) and not self.stop.is_set():
                self.thread=threading.Thread(target=self.decode,daemon=True);self.thread.start()
    def decode(self):
        try:
            import av
            av.logging.set_level(av.logging.PANIC)
        except ImportError:
            self.status='Video decoder not installed';return
        while not self.stop.is_set() and time.monotonic()-self.demand<15:
            container=None
            try:
                self.status='Connecting'
                c=self.config;url='rtsp://'+quote(c['username'],safe='')+':'+quote(self.password,safe='')+'@'+c['address']+':554/'+c['stream']
                container=av.open(url,options={'rtsp_transport':'tcp','fflags':'nobuffer','flags':'low_delay'},timeout=(5,5))
                encoder=None;last=0
                for frame in container.decode(video=0):
                    if self.stop.is_set() or time.monotonic()-self.demand>15:break
                    now=time.monotonic()
                    if now-last<.1:continue
                    last=now;w=min(960,frame.width);w-=w%2;h=int(frame.height*w/frame.width);h-=h%2
                    if encoder is None:
                        encoder=av.CodecContext.create('mjpeg','w');encoder.width=w;encoder.height=h;encoder.pix_fmt='yuvj420p';encoder.open()
                    picture=frame.reformat(width=w,height=h,format='yuvj420p');picture.pts=None
                    packets=encoder.encode(picture)
                    if not packets:continue
                    with self.lock:
                        self.frame=b''.join(bytes(p) for p in packets);self.sequence+=1;self.last_frame=now;self.status='Live';self.lock.notify_all()
            except Exception as exc:
                self.error_type=type(exc).__name__
                self.status='Camera login rejected — check Camera Account' if 'Unauthorized' in self.error_type else 'Connection failed — check camera login and network'
                if self.error_type in ('HTTPUnauthorizedError','HTTPForbiddenError'):break
                self.stop.wait(3)
            finally:
                if container:container.close()
        if not self.stop.is_set() and not self.error_type:self.status='Ready' if self.password else 'Login required'

class CameraManager:
    def __init__(self, folder):
        self.path=Path(folder)/'cameras-private.json';self.lock=threading.RLock();self.cameras={}
        initial=not self.path.exists()
        try:configs=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):configs=[];initial=True
        for c in configs:
            try:password=protect(c['protectedPassword'],True) if c.get('protectedPassword') else ''
            except ValueError:password=''
            self.cameras[c['id']]=Camera(c,password)
        for id,label in (DEFAULTS.items() if initial else []):
            if id not in self.cameras:self.cameras[id]=Camera(dict(id=id,label=label,address='',username='',stream='stream2'))
    def catalog(self):
        with self.lock:return [c.public() for c in self.cameras.values()]
    def admin(self):
        with self.lock:return [dict(c.public(),address=c.config['address'],username=c.config['username'],stream=c.config['stream'],remembered=bool(c.config.get('protectedPassword'))) for c in self.cameras.values()]
    def save(self,d):
        id=str(d.get('id',''));label=str(d.get('label','')).strip()
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',id) or not label or len(label)>60:raise ValueError('Choose a camera name and valid ID.')
        with self.lock:
            old=self.cameras.get(id)
            if not old and len(self.cameras)>=12:raise ValueError('Maximum 12 camera entries.')
            if d.get('remove'):
                if old:old.stop.set();del self.cameras[id]
            else:
                try:ip=ipaddress.IPv4Address(str(d.get('address','')))
                except ValueError:raise ValueError('Enter the local IPv4 address of the camera.')
                if not ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_unspecified or ip.is_link_local:raise ValueError('Use a camera on your private local network.')
                username=str(d.get('username','')).strip();password=str(d.get('password','')) or (old.password if old else '')
                if not username or not password or len(username)>128 or len(password)>256:raise ValueError('Camera Account username and password are required.')
                stream=d.get('stream','stream2')
                if stream not in ('stream1','stream2'):raise ValueError('Invalid camera stream.')
                config=dict(id=id,label=label,address=str(ip),username=username,stream=stream)
                if d.get('remember'):config['protectedPassword']=protect(password)
                if old:old.stop.set()
                self.cameras[id]=Camera(config,password)
            temporary=self.path.with_suffix('.tmp');temporary.write_text(json.dumps([c.config for c in self.cameras.values()]),encoding='utf-8');os.replace(temporary,self.path)
        return dict(ok=True,cameras=self.admin())
    def stream(self,handler,id):
        with self.lock:camera=self.cameras.get(id)
        if not camera or not camera.password:return handler.reply(404,{'error':'Camera not configured'})
        handler.send_response(200);handler.send_header('Content-Type','multipart/x-mixed-replace; boundary=vlframe');handler.send_header('Cache-Control','no-store');handler.send_header('Referrer-Policy','no-referrer');handler.end_headers()
        seq=0
        try:
            while not camera.stop.is_set():
                camera.request()
                with camera.lock:
                    camera.lock.wait_for(lambda:camera.sequence!=seq or camera.stop.is_set(),timeout=1)
                    frame=camera.frame;current=camera.sequence
                if camera.stop.is_set():break
                if frame and current!=seq:
                    seq=current;handler.wfile.write(b'--vlframe\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(frame)).encode()+b'\r\n\r\n'+frame+b'\r\n');handler.wfile.flush()
                elif time.monotonic()-camera.last_frame>3:
                    # A heartbeat detects disconnected browser clients even when a camera is offline.
                    handler.wfile.write(b'\r\n');handler.wfile.flush()
        except (OSError,ConnectionError):pass

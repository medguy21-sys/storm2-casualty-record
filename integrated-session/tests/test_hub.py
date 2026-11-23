import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import importlib.util,json,tempfile,time,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('hub',Path(__file__).resolve().parents[1]/'hub.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ASSETS=Path(__file__).resolve().parents[1]
class SharedHubTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'session.sqlite3';self.h=m.Hub(self.path,ASSETS)
 def tearDown(self):self.h.db.close();self.tmp.cleanup()
 def act(self,action,role='admin',device=None,**extra):
  b=self.h.bed(extra.get('bed',1));return self.h.act(role,device,dict(action=action,bed=1,session=self.h.s['id'],epoch=b['epoch'],revision=b['revision'],**extra))
 def test_clock_and_restart(self):
  self.act('clock',running=True);self.h.anchor-=2;self.h.tick();self.assertGreater(self.h.s['seconds'],1.9)
  self.act('clock',running=False);at=self.h.s['seconds'];self.h.anchor-=10;self.h.tick();self.assertEqual(at,self.h.s['seconds']);self.h.persist();self.h.db.close();self.h=m.Hub(self.path,ASSETS);self.assertFalse(self.h.s['running']);self.assertEqual(at,self.h.s['seconds'])
 def test_held_bp_and_sensor_capture(self):
  b=self.h.bed(1);st=b['state'];self.act('capture','student','A');self.assertEqual(b['record']['vitals'][-1]['sbp'],'')
  self.h.cycle(1);self.h.cuffDeadlines[1]-=5.1;self.h.tick();old=st['syncoNIBP']['sbp'];st['sbp']=180
  self.act('capture','student','A');self.assertEqual(b['record']['vitals'][-1]['sbp'],str(old));self.assertIsNotNone(b['record']['vitals'][-1]['_lab']['bpMeasuredSeconds'])
  st['disconnect']=True;self.act('capture','student','A');self.assertTrue(all(b['record']['vitals'][-1][k]=='' for k in m.KEYS))
 def test_handover_stale_writer_and_revisions(self):
  b=self.h.bed(1);old=b['epoch'];self.act('offer','student','A',note='Reassess after handover')
  with self.assertRaises(ValueError):self.act('capture','student','A')
  self.act('accept','student','B');self.assertEqual(b['writer'],'B')
  with self.assertRaises(PermissionError):self.h.act('student','A',dict(action='save',bed=1,session=self.h.s['id'],epoch=old,revision=b['revision'],record=b['record']))
  with self.assertRaises(ValueError):self.h.act('student','B',dict(action='save',bed=1,session=self.h.s['id'],epoch=b['epoch'],revision=-1,record=b['record']))
 def test_roles_and_capture_permission(self):
  with self.assertRaises(PermissionError):self.act('clock','student','A',running=True)
  self.act('capture-toggle',enabled=False)
  with self.assertRaises(PermissionError):self.act('capture','student','A')
  v=self.h.view('viewer');self.assertNotIn('tokens',v);self.assertNotIn('record',v['beds'][0]);self.assertNotIn('console',v['beds'][0]);self.assertNotIn('state',v['beds'][0])
 def test_multibed_isolation_and_transition(self):
  self.h.assign(2,self.h.cases[0]['id']);a=self.h.bed(1);b=self.h.bed(2);self.assertNotEqual(a['id'],b['id']);self.assertIsNot(a['record'],b['record'])
  self.act('capture','student','A');self.assertEqual(len(b['record']['vitals']),0)
  a['transition']=dict(at=0,duration=10,start={'hr':100},target={'hr':140});self.h.s['seconds']=5;self.h.tick();self.assertEqual(a['state']['hr'],120)
  self.assertEqual(len(self.h.view('viewer')['beds']),8)
 def test_audit_report_privacy(self):
  self.h.event('instructor',1,'Secret instructor coaching',detail={'type':'note'});self.h.event('instructor',1,'Observed Airway secure: Y',detail={'type':'observation'});self.act('capture','student','A')
  d=self.h.export();student=m.report(d,'student');teacher=m.report(d,'instructor');self.assertNotIn('Secret instructor coaching',student);self.assertIn('Secret instructor coaching',teacher);self.assertIn('Observed Airway secure: Y',student);self.assertIn('monitor-capture',student);self.assertNotIn(self.h.s['tokens']['admin'],json.dumps(d))
if __name__=='__main__':unittest.main(verbosity=2)

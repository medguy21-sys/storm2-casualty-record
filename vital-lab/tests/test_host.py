import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import importlib.util,tempfile,unittest,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('host',Path(__file__).resolve().parents[1]/'host.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RelayTests(unittest.TestCase):
 def test_vip_views_are_separate_and_persistent(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'vip.sqlite3';r=m.Relay(path);r.publish(dict(packet={'seconds':12,'beds':[dict(caseId='one',vitals={'hr':110})]},events=[]));before=json.dumps(r.packet)
   r.set_vip(dict(target='vip1',mode='Camera',camera='clinic1',bed=1,count=8,seconds=12));self.assertEqual(r.presentations['vip1']['camera'],'clinic1');self.assertEqual(r.presentations['vip2']['mode'],'Clinic');self.assertEqual(before,json.dumps(r.packet));self.assertTrue(all(not c['configured'] for c in r.view()['cameras']))
   with self.assertRaises(ValueError):r.set_vip(dict(target='vip2',mode='Camera',camera='arbitrary-url',bed=1,count=8))
   r.set_vip(dict(target='all',mode='Truck',camera='gopro',bed=3,count=4));self.assertTrue(all(p['bed']==3 and p['mode']=='Truck' for p in r.presentations.values()));r.db.close();r=m.Relay(path);self.assertEqual(r.presentations['vip3']['bed'],3);r.db.close()
 def test_sanitized_packet(self):
  p=m.sanitize_packet(dict(seconds=12,traceSeconds=100,running=True,token='PRIVATE',sourceText='PRIVATE SCRIPT',beds=[dict(caseId='same-patient',patient='Casualty 1',sourceText='SECRET',notes='PRIVATE',vitals={'hr':110,'spo2':93,'etco2':40},rhythm='sinus',spo2Attached=True,capnoAttached=True,ecgAttached=True)]))
  self.assertEqual(len(p['beds']),8);self.assertEqual(p['beds'][0]['vitals']['hr'],110);self.assertNotIn('PRIVATE',json.dumps(p));self.assertNotIn('SECRET',json.dumps(p))
 def test_audit_dedup_and_restart_stale(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'observer.sqlite3';r=m.Relay(path);data=dict(packet={'seconds':12,'beds':[]},events=[{'id':'a','type':'display','bed':1,'seconds':12,'message':'Display handoff'},{'id':'secret','type':'instructor-note','message':'PRIVATE'}]);r.publish(data);r.publish(data);self.assertEqual(len(r.view()['events']),1);self.assertLess(r.view()['ageSeconds'],1);r.db.close();r=m.Relay(path);self.assertIsNone(r.view()['ageSeconds']);self.assertEqual(r.packet['seconds'],12);self.assertEqual(len(r.view()['events']),1);r.db.close()
if __name__=='__main__':unittest.main(verbosity=2)

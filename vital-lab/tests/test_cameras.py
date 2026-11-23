import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json, os, tempfile, unittest
from pathlib import Path
from camera_service import CameraManager, protect
class CamerasTest(unittest.TestCase):
    def test_catalog_and_private_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            m=CameraManager(folder)
            m.save(dict(id='clinic1',label='Clinic 1',address='192.168.1.100',username='test-user',password='private-test-password'))
            self.assertTrue(next(c for c in m.catalog() if c['id']=='clinic1')['configured'])
            self.assertNotIn('private-test-password',m.path.read_text())
            self.assertNotIn('test-user',json.dumps(m.catalog()))
            self.assertNotIn('private-test-password',json.dumps(m.admin()))
            n=CameraManager(folder);self.assertFalse(next(c for c in n.catalog() if c['id']=='clinic1')['configured'])
            m.save(dict(id='new-camera',label='Clinic 3',address='192.168.1.101',username='test',password='other'))
            self.assertEqual(len(m.catalog()),5)
            m.save(dict(id='new-camera',label='Clinic 3',remove=True));self.assertEqual(len(m.catalog()),4)
            with self.assertRaises(ValueError):m.save(dict(id='bad',label='Bad',address='127.0.0.1',username='x',password='y'))
    def test_bad_login_waits_for_correction(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import sys
        from camera_service import Camera
        class HTTPUnauthorizedError(Exception):pass
        calls=[]
        def rejected(*args,**kwargs):calls.append(True);raise HTTPUnauthorizedError()
        fake=SimpleNamespace(logging=SimpleNamespace(PANIC=0,set_level=lambda level:None),open=rejected)
        camera=Camera(dict(id='test',label='Test',address='192.168.1.100',username='test',stream='stream2'),'unit-test-password')
        camera.demand=__import__('time').monotonic()
        with patch.dict(sys.modules,{'av':fake}):camera.decode();camera.request()
        self.assertEqual(len(calls),1);self.assertIn('login rejected',camera.status);self.assertIsNone(camera.thread)
    @unittest.skipUnless(os.name=='nt','Windows encryption')
    def test_windows_password_protection(self):
        value=protect('private-credential');self.assertNotIn('private-credential',value);self.assertEqual(protect(value,True),'private-credential')
        with tempfile.TemporaryDirectory() as folder:
            m=CameraManager(folder);m.save(dict(id='clinic1',label='Clinic 1',address='192.168.1.100',username='test',password='private-credential',remember=True))
            self.assertNotIn('private-credential',m.path.read_text());n=CameraManager(folder);self.assertTrue(next(c for c in n.catalog() if c['id']=='clinic1')['configured'])
if __name__=='__main__':unittest.main(verbosity=2)

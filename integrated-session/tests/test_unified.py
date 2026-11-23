import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import copy, json, tempfile, unittest
from pathlib import Path
from hub import Hub, report
from comparison import clean_record, compare
ASSETS=Path(__file__).resolve().parents[1]
class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.h=Hub(Path(self.tmp.name)/'session.sqlite3',ASSETS)
    def tearDown(self):self.h.db.close();self.tmp.cleanup()
    def act(self,action,role='admin',device=None,**kw):
        b=self.h.bed(kw.get('bed',1));return self.h.act(role,device,dict(action=action,bed=1,session=self.h.s['id'],epoch=b['epoch'],revision=b['revision'],**kw))
    def advance(self,seconds):self.h.anchor-=seconds;self.h.tick()
    def test_automatic_clock_and_stale_draft_merge(self):
        b=self.h.bed(1);draft=copy.deepcopy(b['record']);self.act('documentation-mode',mode='stream');self.act('auto-chart',enabled=True,intervalSeconds=10);self.act('clock',running=True);self.advance(10.1)
        self.assertEqual(len(b['record']['vitals']),1);self.assertEqual(b['revision'],0);self.assertEqual(b['autoRevision'],1);row=b['record']['vitals'][0];self.assertEqual(row['_lab']['source'],'auto-stream');self.assertEqual(row['sbp'],'')
        draft['f']['note']='A student was typing before the automatic observation arrived';self.act('save','student','A',record=draft,actor='Student A');self.assertEqual(len(b['record']['vitals']),1);self.assertEqual(row['id'],b['record']['vitals'][0]['id'])
        self.act('clock',running=False);self.advance(60);self.assertEqual(len(b['record']['vitals']),1)
        self.act('clock',running=True);self.advance(60);self.assertEqual(len(b['record']['vitals']),2,'A gap produces a current snapshot, not fabricated backfilled readings')
        self.act('documentation-mode',mode='manual');self.assertFalse(self.h.s['autoChart']['enabled']);self.advance(60);self.assertEqual(len(b['record']['vitals']),2)
    def test_read_only_auto_rows_cannot_be_changed_by_save(self):
        self.h.append_observation(1,'auto-stream','host','Automatic feed');b=self.h.bed(1);original=copy.deepcopy(b['record']['vitals'][0]);draft=copy.deepcopy(b['record']);draft['vitals'][0]['hr']='1';self.act('save','student','A',record=draft);self.assertEqual(b['record']['vitals'][0],original)
    def test_client_cannot_forge_source(self):
        rec=copy.deepcopy(self.h.bed(1)['record']);rec['vitals']=[dict(id='manual',time='08:00:01',hr='120',_lab=dict(source='auto-stream',actor='Someone else'))];self.act('save','student','A',record=rec,actor='Real actor');row=self.h.bed(1)['record']['vitals'][0];self.assertEqual(row['_lab']['source'],'student-entered');self.assertEqual(row['_lab']['actor'],'Real actor')
    def test_capture_corrections_and_deletions_keep_audit(self):
        self.act('capture','student','A');b=self.h.bed(1);record=copy.deepcopy(b['record']);row=record['vitals'][0];row['hr']='77';self.act('save','student','A',record=record,actor='Student A');saved=b['record']['vitals'][0];self.assertEqual(saved['_lab']['source'],'student-edited-capture');self.assertNotEqual(saved['_lab']['captureReadings']['hr'],77)
        record=copy.deepcopy(b['record']);record['vitals']=[];self.act('save','student','A',record=record);events=self.h.export()['events'];last=next(e for e in reversed(events) if e['stream']=='student-documentation');change=next(c for c in last['changes'] if c['section']=='vitals');self.assertEqual(change['before']['hr'],'77');self.assertIsNone(change['after'])
    def test_revision_based_delivery_and_roles(self):
        self.act('assign',target=2,case='vital-demo-01');v=self.h.view('student','A',selected_bed=1,known=(0,0));self.assertNotIn('record',v['beds'][0]);self.assertNotIn('record',v['beds'][1]);self.assertNotIn('record',self.h.view('admin',controls=True)['beds'][0])
        with self.assertRaises(PermissionError):self.act('auto-chart','student','A',enabled=True,intervalSeconds=10)
        with self.assertRaises(ValueError):self.act('auto-chart',enabled=True,intervalSeconds=0)
    def test_late_manual_comparison_uses_stated_time(self):
        self.h.s['seconds']=10;self.h.event('monitor-history',1,'Displayed readings',readings=dict(hr=120,spo2=95,sbp=None,dbp=None,rr=None,etco2=None,bpMeasuredSeconds=None));self.h.s['seconds']=20
        rec=copy.deepcopy(self.h.bed(1)['record']);rec['vitals']=[dict(id='manual',time='08:00:10',hr='117',spo2='unclear')];self.act('save','student','A',record=rec,actor='Student A');rows=self.h.export()['comparison'];hr=next(r for r in rows if r['field']=='hr');self.assertEqual(hr['difference'],-3);self.assertEqual(hr['documentation_delay_seconds'],10);self.assertEqual(hr['reference_scenario_seconds'],10);self.assertEqual(next(r for r in rows if r['field']=='spo2')['status'],'unusable chart value')
    def test_command_summary_does_not_credit_automatic_matches(self):
        self.h.append_observation(1,'auto-stream','host','Automatic feed');data=self.h.export();text=report(data,'command');self.assertIn('Automatic observations',text);self.assertIn('Comparable student-entered/edited fields</td><td>0',text);self.assertNotIn(data['session']['beds'][0]['id'],text)
    def test_stamp_provenance_and_duplicate_ids(self):
        rec=copy.deepcopy(self.h.bed(1)['record']);rec['stamps']={'airway:checked':dict(t='08:00:00',role='1')};rec=clean_record(rec,self.h.bed(1)['record'],2,'Student A','A');self.assertEqual(rec['stamps']['airway:checked']['_lab']['documentedScenarioSeconds'],2)
        rec['vitals']=[dict(id='same'),dict(id='same')]
        with self.assertRaises(ValueError):clean_record(rec,self.h.bed(1)['record'],2,'Student A','A')
    def test_paused_clock_comparison_does_not_use_future_changes(self):
        self.h.tick();b=self.h.bed(1);state=copy.deepcopy(b['state']);state['hr']=130
        self.act('state',state=state,events=[],console={})
        rec=copy.deepcopy(b['record']);rec['vitals']=[dict(id='paused-entry',time='08:00:00',hr='130')]
        self.act('save','student','A',record=rec,actor='Student A')
        state=copy.deepcopy(b['state']);state['hr']=70;self.act('state',state=state,events=[],console={})
        row=next(r for r in self.h.export()['comparison'] if r['entry_id']=='paused-entry' and r['field']=='hr')
        self.assertEqual(row['displayed'],130);self.assertEqual(row['difference'],0)
if __name__=='__main__':unittest.main(verbosity=2)

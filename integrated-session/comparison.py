"""Provenance and observation comparisons; documentation never proves care."""
import copy, math, uuid
from bisect import bisect_right
KEYS=('hr','spo2','sbp','dbp','rr','etco2')
SECTIONS=('meds','vitals','vent','body','stages','efx','voice','marks')
def record_changes(before,after):
    """Store changed values/entries, rather than copying every automatic row on each keystroke."""
    changes=[]
    for section in sorted(set(before)|set(after)):
        if section in ('id','created','updated','_labFields'):continue
        old,new=before.get(section),after.get(section)
        if old==new:continue
        if isinstance(old,list) and isinstance(new,list):
            a={str(v.get('id',i)):v for i,v in enumerate(old)};b={str(v.get('id',i)):v for i,v in enumerate(new)}
        elif isinstance(old,dict) and isinstance(new,dict):a,b=old,new
        else:a,b={'value':old},{'value':new}
        for key in sorted(set(a)|set(b)):
            if a.get(key)!=b.get(key):
                change=dict(section=section,entryId=key,before=copy.deepcopy(a.get(key)),after=copy.deepcopy(b.get(key)))
                if section=='f':change.update(beforeMetadata=before.get('_labFields',{}).get(key),afterMetadata=after.get('_labFields',{}).get(key))
                changes.append(change)
    return changes

def clean_record(record,before,seconds,actor,device,order=None):
    out=copy.deepcopy(record)
    if not isinstance(out.get('f',{}),dict):raise ValueError('Invalid clinical fields')
    out['_labFields']=copy.deepcopy(before.get('_labFields',{}))
    for key,value in out.get('f',{}).items():
        if key not in before.get('f',{}) or value!=before['f'][key]:
            out['_labFields'][key]=dict(source='student-entered',documentedScenarioSeconds=seconds,documentedEventSequence=order,actor=str(actor)[:100],device=device)
    for section in SECTIONS:
        rows=out.get(section,[])
        if not isinstance(rows,list):raise ValueError('Invalid chart section '+section)
        previous={str(x.get('id')):x for x in before.get(section,[]) if isinstance(x,dict)};seen=set()
        for row in rows:
            if not isinstance(row,dict):raise ValueError('Invalid chart entry')
            id=str(row.get('id') or uuid.uuid4());row['id']=id
            if id in seen:raise ValueError('Duplicate chart entry ID')
            seen.add(id);old=previous.get(id);content={k:v for k,v in row.items() if k!='_lab'}
            if old and content=={k:v for k,v in old.items() if k!='_lab'}:
                row['_lab']=copy.deepcopy(old.get('_lab',{}));continue
            meta=copy.deepcopy(old.get('_lab',{})) if old else {}
            if meta.get('source') in ('monitor-capture','student-edited-capture','auto-stream'):
                meta['editedFields']=sorted(set(meta.get('editedFields',[]))|{k for k in KEYS if row.get(k)!=old.get(k)})
                meta['source']='student-edited-capture'
            else:meta['source']='student-entered'
            meta.setdefault('createdScenarioSeconds',seconds);meta.setdefault('createdEventSequence',order)
            meta.update(documentedScenarioSeconds=seconds,documentedEventSequence=order,actor=str(actor)[:100],device=device)
            row['_lab']=meta
    for section in ('stamps','tq'):
        values=out.get(section,{})
        if not isinstance(values,dict):raise ValueError('Invalid chart section '+section)
        for key,row in list(values.items()):
            if not isinstance(row,dict):continue
            old=copy.deepcopy(before.get(section,{}).get(key,{}));row=copy.deepcopy(row)
            row.setdefault('id',section+':'+key)
            if old:old.setdefault('id',section+':'+key)
            values[key]=clean_record({'marks':[row]},{'marks':[old] if old else []},seconds,actor,device,order)['marks'][0]
    return out

def clinical_seconds(row,start_ms):
    meta=row.get('_lab',{})
    if meta.get('source') in ('monitor-capture','auto-stream'):return meta.get('scenarioSeconds'),'capture time'
    try:
        fields=str(row.get('time','')).split(':')
        if len(fields) not in (2,3):raise ValueError()
        h,m=int(fields[0]),int(fields[1]);s=int(fields[2]) if len(fields)==3 else 0
        if not(0<=h<24 and 0<=m<60 and 0<=s<60):raise ValueError()
        return (h*3600+m*60+s-int(start_ms/1000)%86400)%86400,'student-stated chart time'
    except (ValueError,TypeError):return None,'no usable chart time'

def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None

def compare(data):
    session=data['session'];events=data['events'];rows=[]
    for bed,b in enumerate(session['beds'],1):
        if not b:continue
        history=sorted((e for e in events if e.get('bed')==bed and e['stream']=='monitor-history'),key=lambda e:e['scenarioSeconds']);history_times=[e['scenarioSeconds'] for e in history]
        for entry in b['record'].get('vitals',[]):
            at,basis=clinical_seconds(entry,session['startMs']);meta=entry.get('_lab',{});reference=None
            if meta.get('source') in ('monitor-capture','student-edited-capture','auto-stream'):
                reference=meta.get('captureReadings')
            index=bisect_right(history_times,at+.001)-1 if at is not None else -1
            order=meta.get('documentedEventSequence')
            while index>=0 and order is not None and history[index].get('seq',0)>order:index-=1
            chosen=history[index] if index>=0 else None
            if reference is None and chosen and at-chosen['scenarioSeconds']<=2:reference=chosen.get('readings',{})
            for field in KEYS:
                value=number(entry.get(field));expected=number((reference or {}).get(field));delta=None if value is None or expected is None else value-expected
                status=('not charted' if str(entry.get(field,'')).strip()=='' else 'unusable chart value') if value is None else 'no comparable displayed reading' if expected is None else 'match' if abs(delta)<.001 else 'different'
                documented=meta.get('documentedScenarioSeconds',meta.get('scenarioSeconds'))
                ref_at=meta.get('scenarioSeconds') if meta.get('captureReadings') else chosen.get('scenarioSeconds') if chosen and reference is not None else None
                source=meta.get('source','student-entered');field_source='student-edited' if source=='student-edited-capture' and field in meta.get('editedFields',[]) else 'monitor-capture' if source=='student-edited-capture' else source
                rows.append(dict(session_id=session['id'],patient_id=b['id'],bed=bed,case_id=b['case'],entry_id=entry.get('id',''),field=field,chart_time=entry.get('time',''),clinical_scenario_seconds=at,documented_scenario_seconds=documented,time_basis=basis,documentation_delay_seconds=None if at is None or documented is None else round(documented-at,3),source=source,field_source=field_source,actor=meta.get('actor',''),charted_text=str(entry.get(field,'')),charted=value,displayed=expected,difference=delta,status=status,bp_measured_scenario_seconds=(reference or {}).get('bpMeasuredSeconds') if field in ('sbp','dbp') else None,reference_event_sequence=chosen.get('seq') if chosen and not meta.get('captureReadings') else meta.get('captureEventSequence',meta.get('documentedEventSequence')),reference_scenario_seconds=ref_at,reference_age_seconds=None if at is None or ref_at is None else round(at-ref_at,3),reference='original captured readings' if meta.get('captureReadings') else 'monitor history at stated time'))
    return rows

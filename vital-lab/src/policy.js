(function(root){
const rank={Field:0,Truck:1,Clinic:2};
function fingerprint(s){return [s.label||'',s.left,s.top,s.width,s.height].join('|')}
function resolve(p,screens){
 const eligible=screens.filter(s=>!s.internal||p.allowInternal);
 if(p.nativeId){const native=eligible.filter(s=>s.nativeId===p.nativeId);if(native.length===1)return native[0]}
 const candidates=eligible.filter(s=>!p.nativeId||!s.nativeId||s.nativeId===p.nativeId);
 const exact=candidates.filter(s=>fingerprint(s)===p.fingerprint);if(exact.length===1)return exact[0];
 const labelled=candidates.filter(s=>s.label&&s.label===p.label);return labelled.length===1?labelled[0]:null;
}
class Policy{
 constructor(){this.profiles=[];this.screens=[];this.auto=true;this.manualId=null;this.activeId=null;this.stage='Any';this.connectedAt=new Map();this.changedAt=-Infinity;this.pending=null;this.lossAt=null;this.revision=0;this.stableMs=1500;this.lossMs=800;this.dwellMs=2500}
 configure(p){this.profiles=p.map(x=>({...x}));this.revision++}
 discover(screens,now){this.screens=screens;for(const p of this.profiles){const s=resolve(p,screens);if(s){if(!this.connectedAt.has(p.id))this.connectedAt.set(p.id,now)}else this.connectedAt.delete(p.id)}}
 eligible(p){return p.enabled!==false&&(this.stage==='Any'||rank[p.stage]<=rank[this.stage])&&!!resolve(p,this.screens)}
 manual(id,now){this.manualId=id;return this.choose(now,true)}
 resume(now){this.manualId=null;this.auto=true;return this.choose(now)}
 choose(now,immediate=false){
  const available=this.profiles.filter(p=>this.eligible(p)).sort((a,b)=>(Number(b.priority)||0)-(Number(a.priority)||0)||a.id.localeCompare(b.id));
  const current=available.find(p=>p.id===this.activeId),manual=available.find(p=>p.id===this.manualId);
  let target=manual||(!this.auto&&current)||available[0]||null;
  if(!this.auto&&!this.manualId&&!this.activeId)target=null;
  if(target?.id===this.activeId){this.pending=null;this.lossAt=null;return null}
  const lost=this.activeId&&!current;
  if(lost){if(this.lossAt===null)this.lossAt=now;if(!immediate&&now-this.lossAt<this.lossMs)return null}
  if(target&&!immediate&&now-(this.connectedAt.get(target.id)??now)<this.stableMs)return null;
  if(current&&!immediate&&now-this.changedAt<this.dwellMs)return null;
  const previous=this.activeId;this.activeId=target?.id||null;this.changedAt=now;this.lossAt=null;this.pending=null;
  return {from:previous,to:this.activeId,profile:target,screen:target?resolve(target,this.screens):null,reason:manual?'manual override':lost?'display lost / fallback':'priority / stage'};
 }
}
const api={Policy,resolve,fingerprint};if(typeof module!=='undefined')module.exports=api;root.VitalDisplayPolicy=api;
})(globalThis);

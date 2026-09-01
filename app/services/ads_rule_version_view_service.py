"""Read-only presentation data for internal Ads rule-version controls."""
from decimal import Decimal,InvalidOperation
from app.amazon_ads.rule_tuning_models import ALLOWED_TUNING_PARAMETERS,validate_threshold_snapshot
from app.services.ads_rule_rollback_service import AdsRuleRollbackService
from app.services.ads_rule_version_resolver import AdsRuleVersionResolver

class AdsRuleVersionViewService:
 def __init__(self,repository):self.repository=repository
 @staticmethod
 def _thresholds(values):return {name:str(getattr(values,name)) for name in ALLOWED_TUNING_PARAMETERS}
 @staticmethod
 def _safe_version(row):
  fields=("rule_version_id","version_name","status","source","source_proposal_id","created_at","updated_at","activated_at")
  return {**{field:row.get(field) for field in fields},"thresholds":{name:str(value) for name,value in row.get("thresholds",{}).items() if name in ALLOWED_TUNING_PARAMETERS}}
 def active(self,seller,marketplace,profile):
  resolved=AdsRuleVersionResolver(self.repository).resolve(seller,marketplace,profile);row=self.repository.get_active_rule_version(seller,marketplace,str(profile));rollback=AdsRuleRollbackService(self.repository).get_rollback_status(seller,marketplace,str(profile))
  if not row:return {"active":False,"using_default_thresholds":True,"rule_version_id":None,"version_name":None,"status":None,"source":resolved.source,"source_proposal_id":None,"thresholds":self._thresholds(resolved.thresholds),"activated_at":None,"rollback_available":False,"rollback_candidate_rule_version_id":None}
  return {"active":True,"using_default_thresholds":False,"rule_version_id":row["rule_version_id"],"version_name":row["version_name"],"status":row["status"],"source":row["source"],"source_proposal_id":row.get("source_proposal_id"),"thresholds":self._thresholds(resolved.thresholds),"activated_at":row.get("activated_at"),"rollback_available":rollback.rollback_available,"rollback_candidate_rule_version_id":rollback.previous_rule_version_id}
 def history(self,seller,marketplace,profile,limit=100):
  current=self.active(seller,marketplace,profile);versions=[]
  for row in self.repository.list_rule_versions(seller,marketplace,str(profile),limit):
   item=self._safe_version(row);item["diff"]=self.diff_values(current["thresholds"],row.get("thresholds",{}));item["activation_eligible"]=self._eligible(seller,marketplace,profile,row);versions.append(item)
  return {"active":current,"versions":versions}
 def diff(self,seller,marketplace,profile,rule_version_id):
  row=self.repository.get_rule_version(seller,marketplace,str(profile),rule_version_id)
  if not row:return None
  current=self.active(seller,marketplace,profile)
  return {"rule_version_id":rule_version_id,"current_rule_version_id":current["rule_version_id"],"differences":self.diff_values(current["thresholds"],row.get("thresholds",{}))}
 @staticmethod
 def diff_values(current,candidate):
  output=[]
  for name in ALLOWED_TUNING_PARAMETERS:
   if name not in candidate or name not in current:continue
   try:
    old=Decimal(str(current[name]));new=Decimal(str(candidate[name]));absolute=new-old;relative=None if old==0 else absolute.copy_abs()/old.copy_abs()*Decimal("100")
   except (InvalidOperation,ValueError,TypeError):continue
   output.append({"parameter_name":name,"current_value":str(old),"candidate_value":str(new),"absolute_change":str(absolute),"relative_change_percent":str(relative) if relative is not None else None})
  return output
 def _eligible(self,seller,marketplace,profile,row):
  _,well,white,bounds=validate_threshold_snapshot(row.get("thresholds"))
  if row.get("status")!="proposed" or not (well and white and bounds):return False
  proposal_id=row.get("source_proposal_id")
  if not proposal_id:return row.get("source") not in ("tuning_proposal","rule_tuning_proposal")
  proposal=self.repository.get_rule_tuning_proposal(seller,marketplace,str(profile),proposal_id)
  return bool(proposal and proposal["status"]=="approved_for_future_rule_version")

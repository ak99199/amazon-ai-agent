import re
from datetime import date,datetime,timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from app.amazon_ads.report_models import AdsPerformanceDaily
from app.amazon_ads.rule_tuning_models import AdsRuleTuningProposal
from app.api import ads
from app.database.ads_repository import AdsPerformanceRepository
from app.services.ads_recommendation_service import AdsRecommendationService
from main import app
from tests.test_dashboard import configure_admin,login

NOW=datetime(2026,2,1,tzinfo=timezone.utc)
FULL={"target_acos_percent":"30","min_impressions_for_ctr":"100","low_ctr_percent":"0.3","min_clicks_for_cvr":"10","low_cvr_percent":"2","high_cpc_amount":"50","wasted_spend_threshold":"500"}

def setup(monkeypatch,tmp_path):
 configure_admin(monkeypatch);monkeypatch.setenv("AMAZON_SELLER_ID","seller");monkeypatch.setenv("AMAZON_MARKETPLACE_ID","market");monkeypatch.setenv("AMAZON_ADS_PROFILE_ID","profile")
 repo=AdsPerformanceRepository(tmp_path/"ads.db");monkeypatch.setattr(ads,"_services",lambda:(repo,None,None));return repo,TestClient(app)

def version(repo,version_id,status="proposed",target="30",source="manual",proposal_id=None):return repo.create_rule_version(version_id,"seller","market","profile",f"Version {version_id}",status,dict(FULL,target_acos_percent=target),source,"tester",created_at=NOW,source_proposal_id=proposal_id)

def approved_candidate(repo):
 proposal=AdsRuleTuningProposal("proposal-B","seller","market","profile","A","target_acos_percent",Decimal("30"),Decimal("25"),"decrease","TEST","test",40,"medium","proposed",{},NOW);repo.save_rule_tuning_proposal(proposal);repo.review_rule_tuning_proposal("seller","market","profile","proposal-B","approved_for_future_rule_version",NOW);version(repo,"B",target="25",source="tuning_proposal",proposal_id="proposal-B")

def csrf(client):return re.search(r'data-csrf="([^"]+)"',client.get("/dashboard").text).group(1)

def test_auth_csrf_activation_rollback_and_e2e_recommendation_flow(monkeypatch,tmp_path):
 repo,client=setup(monkeypatch,tmp_path);version(repo,"A","active");approved_candidate(repo)
 for day in range(1,15):repo.save(AdsPerformanceDaily("seller","market","profile",date(2026,1,day),"SP","campaign","Campaign",impressions=10,clicks=5,spend=Decimal("28"),orders=1,units=1,sales=Decimal("100")))
 assert client.get("/api/ads/rule-versions/active").status_code==401 and client.post("/api/ads/rule-versions/B/activate",json={"confirm":True,"expected_active_rule_version_id":"A"}).status_code==401
 assert client.post("/api/ads/rule-versions/rollback",json={"confirm":True,"expected_active_rule_version_id":"A"}).status_code==401
 login(client);assert client.get("/api/ads/rule-versions/active").json()["rule_version_id"]=="A"
 assert client.post("/api/ads/rule-versions/B/activate",json={"confirm":True,"expected_active_rule_version_id":"A"}).status_code==403 and repo.get_active_rule_version("seller","market","profile")["rule_version_id"]=="A"
 token=csrf(client);activated=client.post("/api/ads/rule-versions/B/activate",json={"confirm":True,"expected_active_rule_version_id":"A"},headers={"X-CSRF-Token":token});assert activated.status_code==200 and repo.get_active_rule_version("seller","market","profile")["rule_version_id"]=="B"
 assert repo.get_latest_rule_activation_event("seller","market","profile")["event_type"]=="RULE_VERSION_ACTIVATED"
 recommendations=AdsRecommendationService(repo).get_campaign_recommendations("seller","market","profile",window=30,reference_date=date(2026,1,14));assert "HIGH_ACOS" in {x.recommendation_code for x in recommendations} and all(x.rule_version_id=="B" for x in recommendations)
 assert client.post("/api/ads/rule-versions/rollback",json={"confirm":True,"expected_active_rule_version_id":"A"},headers={"X-CSRF-Token":token}).status_code==409 and repo.get_active_rule_version("seller","market","profile")["rule_version_id"]=="B"
 assert client.post("/api/ads/rule-versions/rollback",json={"confirm":True,"expected_active_rule_version_id":"B"}).status_code==403 and repo.get_active_rule_version("seller","market","profile")["rule_version_id"]=="B"
 rolled=client.post("/api/ads/rule-versions/rollback",json={"confirm":True,"expected_active_rule_version_id":"B"},headers={"X-CSRF-Token":token});assert rolled.status_code==200 and repo.get_active_rule_version("seller","market","profile")["rule_version_id"]=="A"
 assert repo.get_latest_rule_activation_event("seller","market","profile")["event_type"]=="RULE_VERSION_ROLLED_BACK"
 restored=AdsRecommendationService(repo).get_campaign_recommendations("seller","market","profile",window=30,reference_date=date(2026,1,14));assert "HIGH_ACOS" not in {x.recommendation_code for x in restored} and all(x.rule_version_id=="A" for x in restored)

def test_history_diff_and_safe_http_error_mapping(monkeypatch,tmp_path):
 repo,client=setup(monkeypatch,tmp_path);version(repo,"A","active");version(repo,"B",target="25");login(client);token=csrf(client)
 assert client.get("/api/ads/rule-versions").status_code==200 and client.get("/api/ads/rule-versions/B/diff").json()["differences"]
 assert client.post("/api/ads/rule-versions/missing/activate",json={"confirm":True,"expected_active_rule_version_id":"A"},headers={"X-CSRF-Token":token}).status_code==404
 assert client.post("/api/ads/rule-versions/B/activate",json={"confirm":False,"expected_active_rule_version_id":"A"},headers={"X-CSRF-Token":token}).status_code==400
 assert client.post("/api/ads/rule-versions/B/activate",json={"confirm":True,"expected_active_rule_version_id":"stale"},headers={"X-CSRF-Token":token}).status_code==409
 repo.update_rule_version_status("seller","market","profile","B","rejected",NOW)
 assert client.post("/api/ads/rule-versions/B/activate",json={"confirm":True,"expected_active_rule_version_id":"A"},headers={"X-CSRF-Token":token}).status_code==422

def test_controlled_failure_is_safe_and_contains_no_raw_details(monkeypatch,tmp_path):
 _,client=setup(monkeypatch,tmp_path);login(client)
 class Broken:
  def get_active_rule_version(self,*args):raise RuntimeError("password=secret-token")
 monkeypatch.setattr(ads,"_services",lambda:(Broken(),None,None));response=client.get("/api/ads/rule-versions/active")
 assert response.status_code==503 and "secret-token" not in response.text and "credentials" not in response.text.lower()

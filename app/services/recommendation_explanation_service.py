"""Validated optional LLM explanations for deterministic recommendations."""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from os import getenv
from app.services.listing_recommendation_service import RecommendationResult
KNOWN_ACTIONS={"KEEP_STABLE","WAIT_FOR_MORE_DATA","REVIEW_TITLE","CHECK_LISTING_STATUS","REVIEW_PRICE_VOLATILITY","REVIEW_FULFILLMENT","INVESTIGATE_RECENT_CHANGE","MONITOR_LISTING","REVIEW_LISTING_QUALITY"}
@dataclass(frozen=True)
class ActionExplanation:
    action:str; priority:str; explanation:str
@dataclass(frozen=True)
class ExplanationResult:
    asin:str; generated_at:str; headline:str; summary:str; action_explanations:tuple[ActionExplanation,...]; overall_action:str; priority:str; data_confidence:str; source:str
    def public_dict(self):
        value=asdict(self); value["action_explanations"]=[asdict(item) for item in self.action_explanations]; return value
class RecommendationExplanationService:
    def __init__(self,provider=None): self._provider=provider
    @classmethod
    def from_environment(cls):
        key=getenv("OPENAI_API_KEY")
        if not key: return cls()
        try:
            from app.llm.openai_provider import OpenAIExplanationProvider
            return cls(OpenAIExplanationProvider(key,getenv("OPENAI_MODEL") or "gpt-4o-mini"))
        except ImportError: return cls()
    def explain(self,recommendation:RecommendationResult,generated_at=None):
        fallback=self._deterministic(recommendation,generated_at)
        if not self._provider: return fallback
        try: candidate=self._provider.explain(self._payload(recommendation))
        except Exception: return fallback
        return self._validated(candidate,recommendation,generated_at) or fallback
    @staticmethod
    def _payload(value):
        return {"asin":value.asin,"overall_action":value.overall_action,"priority":value.priority,"data_confidence":value.data_confidence,"summary":value.summary,"recommendations":[{"action":item.action,"priority":item.priority,"reason":item.reason,"evidence":item.evidence,"safe_next_step":item.safe_next_step} for item in value.recommendations]}
    def _deterministic(self,value,generated_at):
        actions=tuple(ActionExplanation(item.action,item.priority,item.reason) for item in value.recommendations)
        return ExplanationResult(value.asin,(generated_at or datetime.now(timezone.utc)).isoformat(),f"{value.priority.title()} priority: {value.overall_action.replace('_',' ').title()}",value.summary,actions,value.overall_action,value.priority,value.data_confidence,"deterministic")
    def _validated(self,data,value,generated_at):
        if not isinstance(data,dict) or data.get("overall_action")!=value.overall_action or data.get("priority")!=value.priority: return None
        entries=data.get("action_explanations")
        if not isinstance(entries,list): return None
        expected=[item.action for item in value.recommendations]
        if [item.get("action") if isinstance(item,dict) else None for item in entries] != expected: return None
        if any(not isinstance(item,dict) or item.get("action") not in KNOWN_ACTIONS or item.get("priority") != source.priority or not isinstance(item.get("explanation"),str) for item,source in zip(entries,value.recommendations)): return None
        headline=data.get("headline"); summary=data.get("summary")
        if not isinstance(headline,str) or not isinstance(summary,str): return None
        return ExplanationResult(value.asin,(generated_at or datetime.now(timezone.utc)).isoformat(),headline,summary,tuple(ActionExplanation(item["action"],item["priority"],item["explanation"]) for item in entries),value.overall_action,value.priority,value.data_confidence,"llm")


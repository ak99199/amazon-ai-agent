"""Safe, internal-only models for explicit rule-version activation."""
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class AdsRuleActivationRequest:
 seller_id:str;marketplace_id:str;profile_id:str;target_rule_version_id:str;expected_active_rule_version_id:str|None;confirm:bool=False

@dataclass(frozen=True)
class AdsRuleActivationCheck:
 code:str;passed:bool;message:str

@dataclass(frozen=True)
class AdsRuleActivationResult:
 status:str;activation_id:str|None;seller_id:str;marketplace_id:str;profile_id:str;previous_rule_version_id:str|None;active_rule_version_id:str|None;checks:tuple[AdsRuleActivationCheck,...];activated_at:datetime|None

@dataclass(frozen=True)
class AdsRuleRollbackRequest:
 seller_id:str;marketplace_id:str;profile_id:str;expected_active_rule_version_id:str|None;confirm:bool=False

@dataclass(frozen=True)
class AdsRuleRollbackResult:
 status:str;rollback_id:str|None;seller_id:str;marketplace_id:str;profile_id:str;previous_active_rule_version_id:str|None;restored_rule_version_id:str|None;checks:tuple[AdsRuleActivationCheck,...];rolled_back_at:datetime|None

@dataclass(frozen=True)
class AdsRuleRollbackStatus:
 rollback_available:bool;current_rule_version_id:str|None;previous_rule_version_id:str|None

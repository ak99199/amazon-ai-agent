"""Safe, normalized Amazon Ads sync observability result."""
from dataclasses import asdict, dataclass
@dataclass(frozen=True)
class AdsSyncObservability:
 health_status:str; latest_sync:dict|None; latest_success:dict|None; latest_failure:dict|None; recent_runs:list[dict]; in_progress:bool; stale_run_detected:bool; stale_sync_id:str|None; cooldown_active:bool; cooldown_remaining_seconds:int; blocked_reason:str|None; last_error_code:str|None; last_error_message:str|None; success_rate_recent:float|None; runs_last_24h:int; runs_last_7d:int; rows_saved_recent:int; rows_failed_recent:int; last_success_age_seconds:int|None; last_attempt_age_seconds:int|None
 def public_dict(self):return asdict(self)

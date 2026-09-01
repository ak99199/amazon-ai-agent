"""Scope-isolated stale Ads run reconciliation; performs no Amazon calls."""
from dataclasses import dataclass
from datetime import timedelta

@dataclass(frozen=True)
class AdsSyncRecoveryResult:
    status:str
    recovered:bool=False

class AdsSyncRecoveryService:
    def __init__(self,repository,stale_after_hours,now):self.repository=repository;self.stale_after=timedelta(hours=stale_after_hours);self.now=now
    @staticmethod
    def _value(run,name):return run[name] if hasattr(run,"keys") else getattr(run,name)
    def inspect(self,seller,marketplace,profile):
        active=self.repository.active_sync_run(seller,marketplace,profile)
        if not active:return active,False
        started=self._value(active,"started_at")
        if isinstance(started,str):
            from datetime import datetime
            started=datetime.fromisoformat(started)
        return active,self._value(active,"status")=="running" and started<=self.now()-self.stale_after
    def reconcile(self,seller,marketplace,profile):
        try:
            active,stale=self.inspect(seller,marketplace,profile)
            if not active:return AdsSyncRecoveryResult("clear")
            if not stale:return AdsSyncRecoveryResult("active")
            changed=self.repository.finalize_stale_sync_run(self._value(active,"sync_id"),seller,marketplace,profile,self.now()-self.stale_after,self.now())
            return AdsSyncRecoveryResult("recovered" if changed else "unchanged",changed)
        except Exception:return AdsSyncRecoveryResult("unavailable")

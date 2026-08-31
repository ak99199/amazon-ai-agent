"""Feature flags for safe, opt-in Amazon Ads live reads."""
from dataclasses import dataclass
from os import getenv

class AdsLiveReadConfigurationError(ValueError): pass
@dataclass(frozen=True)
class AdsLiveReadConfig:
    live_read_enabled: bool = False
    use_mock_data: bool = True
    max_pages: int = 10
    report_max_attempts: int = 5
    report_max_rows: int = 10000
    @classmethod
    def from_environment(cls):
        def boolean(name,default):
            value=getenv(name)
            if value in (None,""): return default
            if value.lower() not in ("true","false"): raise AdsLiveReadConfigurationError(f"{name} must be true or false")
            return value.lower()=="true"
        return cls(boolean("AMAZON_ADS_LIVE_READ_ENABLED",False),boolean("AMAZON_ADS_USE_MOCK_DATA",True))

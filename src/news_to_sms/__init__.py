"""news-to-sms: fetch today's news, split it into SMS-sized pieces, send via SMS."""

from news_to_sms.config import Settings
from news_to_sms.pipeline import RunResult, run

__all__ = ["RunResult", "Settings", "run"]
__version__ = "0.1.0"

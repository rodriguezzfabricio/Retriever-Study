
from datetime import datetime
from typing import Optional

from app.core.semester_config import SEMESTER_DATES

def get_semester_end_date(semester: str) -> Optional[datetime]:
    """Returns the end date of a given semester."""
    return SEMESTER_DATES.get(semester, {}).get("end")

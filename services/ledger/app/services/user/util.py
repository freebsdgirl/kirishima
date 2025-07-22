from datetime import datetime, timedelta, time
from typing import Optional


def _get_period_range(period: str, date_str: Optional[str] = None):
    """
    Returns the start and end datetime objects for a given period of the day.
    Args:
        period (str): The period of the day. Must be one of "night", "morning", "afternoon", "evening", or "day".
        date_str (Optional[str], optional): The date in "YYYY-MM-DD" format. If not provided, uses the current date,
            or for "evening" and "day" periods, defaults to the previous day.
    Returns:
        Tuple[datetime, datetime]: A tuple containing the start and end datetime objects for the specified period.
    Raises:
        ValueError: If the provided period is not one of the accepted values.
    """
    if date_str is None:
        now = datetime.now()
        if period in ("evening", "day"):
            date = (now - timedelta(days=1)).date()
        else:
            date = now.date()
    else:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    if period == "night":
        start = datetime.combine(date, time(0, 0))
        end = datetime.combine(date, time(5, 59, 59, 999999))
    elif period == "morning":
        start = datetime.combine(date, time(6, 0))
        end = datetime.combine(date, time(11, 59, 59, 999999))
    elif period == "afternoon":
        start = datetime.combine(date, time(12, 0))
        end = datetime.combine(date, time(17, 59, 59, 999999))
    elif period == "evening":
        start = datetime.combine(date, time(18, 0))
        end = datetime.combine(date, time(23, 59, 59, 999999))
    elif period == "day":
        start = datetime.combine(date, time(0, 0))
        end = datetime.combine(date, time(23, 59, 59, 999999))
    else:
        raise ValueError("Invalid period")
    return start, end
"""Date presentation shared by form modules: ISO dates on the scenario,
``mm/dd/yyyy`` on the form face."""
import datetime


def mm_dd_yyyy(iso_date: str) -> str:
    """ISO ``YYYY-MM-DD`` -> the form's ``mm/dd/yyyy``. Loud on any other shape."""
    return datetime.date.fromisoformat(iso_date).strftime("%m/%d/%Y")

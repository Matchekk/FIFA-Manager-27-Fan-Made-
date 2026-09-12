"""Runtime projection for adopted current loans; source chronology stays intact."""
from datetime import date

def effective_current_loan_start(start: date, end: date, career_start: date, snapshot: date) -> date:
    if end < start:
        raise ValueError('Loan ends before it starts')
    if snapshot < career_start:
        raise ValueError('Snapshot precedes career start')
    # Only already-adopted current loans, never future-loan conditions, use this API.
    if career_start < start <= snapshot and end > career_start:
        return career_start
    return start

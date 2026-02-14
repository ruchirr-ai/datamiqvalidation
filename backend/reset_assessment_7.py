#!/usr/bin/env python3
"""Reset assessment 7 to pending status"""

from database import db_instance
from models.assessment import Assessment

with db_instance.get_session() as db:
    assessment = db.query(Assessment).filter(Assessment.id == 7).first()
    if assessment:
        assessment.status = 'pending'
        assessment.error_message = None
        db.commit()
        print(f"Assessment {assessment.id} reset to pending")
    else:
        print("Assessment not found")

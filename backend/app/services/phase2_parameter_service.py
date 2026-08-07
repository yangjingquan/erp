from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.configuration import CfgGlobalParameter


def get_phase2_parameter(db: Session, org_id: str, key: str, default: str) -> str:
    parameter = db.scalar(
        select(CfgGlobalParameter).where(
            CfgGlobalParameter.org_id == org_id,
            CfgGlobalParameter.parameter_key == key,
        )
    )
    if parameter is None or parameter.parameter_value is None:
        return default
    return parameter.parameter_value

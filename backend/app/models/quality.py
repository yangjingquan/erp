from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import AuditMixin, UUIDModel
class QaPlan(AuditMixin, UUIDModel):
    __tablename__="qa_plan"; org_id: Mapped[str]=mapped_column(String(36),nullable=False,index=True); name: Mapped[str]=mapped_column(String(128),nullable=False); items_json: Mapped[list]=mapped_column(JSON,default=list,nullable=False)
class QaInspection(AuditMixin, UUIDModel):
    __tablename__="qa_inspection"; org_id: Mapped[str]=mapped_column(String(36),nullable=False,index=True); inspection_type: Mapped[str]=mapped_column(String(32),nullable=False); source_type: Mapped[str]=mapped_column(String(64),nullable=False); source_id: Mapped[str]=mapped_column(String(36),nullable=False); status: Mapped[str]=mapped_column(String(32),default="draft",nullable=False); result: Mapped[str|None]=mapped_column(String(32)); results_json: Mapped[list]=mapped_column(JSON,default=list,nullable=False); disposition: Mapped[str|None]=mapped_column(String(32))
class QaNonconformity(AuditMixin, UUIDModel):
    __tablename__="qa_nonconformity"; org_id: Mapped[str]=mapped_column(String(36),nullable=False,index=True); inspection_id: Mapped[str]=mapped_column(String(36),nullable=False,index=True); description: Mapped[str]=mapped_column(String(500),nullable=False); status: Mapped[str]=mapped_column(String(32),default="open",nullable=False); __table_args__=(UniqueConstraint("org_id","inspection_id",name="uk_qa_nonconformity_inspection"),)

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import AppError
from app.core.time import local_today
from app.models.crm import CrmContact, CrmFollowUp, CrmLead, CrmOpportunity
from app.models.master_data import MdCustomer
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no

LEAD_TRANSITIONS = {"new": {"contacted", "lost"}, "contacted": {"qualified", "lost"}, "qualified": {"converted", "lost"}, "converted": set(), "lost": set()}

def create_lead(db, payload, context):
    row = CrmLead(
        org_id=context.org_id,
        lead_no=next_doc_no(db, "crm_lead", context.org_id, local_today()),
        owner_id=context.id,
        **payload,
    )
    db.add(row)
    db.flush()
    return row
def transition_lead(db, lead_id, status, context):
    row = db.scalar(select(CrmLead).where(CrmLead.id == lead_id, CrmLead.org_id == context.org_id))
    if row is None: raise AppError("线索不存在", code=404)
    if status not in LEAD_TRANSITIONS.get(row.status, set()): raise AppError("线索状态流转不合法", code=400)
    row.status = status; db.flush(); return row
def convert_lead(db, lead_id, context):
    row = db.scalar(select(CrmLead).where(CrmLead.id == lead_id, CrmLead.org_id == context.org_id))
    if row is None: raise AppError("线索不存在", code=404)
    if row.status == "converted": return {"lead_id": row.id, "customer_id": row.customer_id, "contact_id": row.contact_id, "opportunity_id": row.opportunity_id}
    if row.status != "qualified": raise AppError("只有合格线索可转化", code=400)
    customer = db.scalar(select(MdCustomer).where(MdCustomer.org_id == context.org_id, MdCustomer.name == row.name))
    if customer is None:
        customer = MdCustomer(org_id=context.org_id, code=f"CRM-{row.id[:8]}", name=row.name, owner_id=context.id); db.add(customer); db.flush()
    contact = db.scalar(select(CrmContact).where(CrmContact.org_id == context.org_id, CrmContact.phone == row.phone)) if row.phone else None
    if contact is None:
        contact = CrmContact(org_id=context.org_id, customer_id=customer.id, name=row.name, phone=row.phone, email=row.email); db.add(contact); db.flush()
    opp = CrmOpportunity(
        org_id=context.org_id,
        opportunity_no=next_doc_no(db, "crm_opportunity", context.org_id, local_today()),
        name=row.name,
        customer_id=customer.id,
        owner_id=context.id,
    ); db.add(opp); db.flush()
    row.status, row.customer_id, row.contact_id, row.opportunity_id = "converted", customer.id, contact.id, opp.id; db.flush()
    return {"lead_id": row.id, "customer_id": customer.id, "contact_id": contact.id, "opportunity_id": opp.id}
def create_opportunity(db, payload, context):
    row = CrmOpportunity(
        org_id=context.org_id,
        opportunity_no=next_doc_no(db, "crm_opportunity", context.org_id, local_today()),
        owner_id=context.id,
        **payload,
    ); db.add(row); db.flush(); return row
def transition_opportunity(db, opportunity_id, stage, context):
    row = db.scalar(select(CrmOpportunity).where(CrmOpportunity.id == opportunity_id, CrmOpportunity.org_id == context.org_id))
    if row is None: raise AppError("商机不存在", code=404)
    if stage == "lost" and not row.loss_reason: raise AppError("输单必须填写原因", code=400)
    row.stage = stage; db.flush(); return row
def add_follow_up(db, opportunity_id, payload, context):
    if db.scalar(select(CrmOpportunity).where(CrmOpportunity.id == opportunity_id, CrmOpportunity.org_id == context.org_id)) is None: raise AppError("商机不存在", code=404)
    row = CrmFollowUp(org_id=context.org_id, opportunity_id=opportunity_id, **payload); db.add(row); db.flush(); return row
def list_leads(db, context): return db.scalars(select(CrmLead).where(CrmLead.org_id == context.org_id).order_by(CrmLead.created_at.desc())).all()
def list_opportunities(db, context): return db.scalars(select(CrmOpportunity).where(CrmOpportunity.org_id == context.org_id).order_by(CrmOpportunity.created_at.desc())).all()

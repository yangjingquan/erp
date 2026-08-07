from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import AppError
from app.models.quality import QaInspection,QaNonconformity,QaPlan
def create_quality_plan(db,payload,context): row=QaPlan(org_id=context.org_id,name=payload["name"],items_json=payload["items"]);db.add(row);db.flush();return row
def create_inspection(db,inspection_type,source_type,source_id,context): row=QaInspection(org_id=context.org_id,inspection_type=inspection_type,source_type=source_type,source_id=source_id);db.add(row);db.flush();return row
def submit_inspection(db,inspection_id,results,context):
 row=db.scalar(select(QaInspection).where(QaInspection.id==inspection_id,QaInspection.org_id==context.org_id));
 if row is None: raise AppError("检验单不存在",code=404)
 if row.status!="draft": raise AppError("检验单当前不可提交",code=400)
 if not results: raise AppError("检验结果不能为空",code=400)
 row.results_json=results; row.result="passed" if all(item.get("passed",item.get("value") not in {"fail","不合格"}) for item in results) else "failed"; row.status="submitted"
 if row.result=="failed" and db.scalar(select(QaNonconformity).where(QaNonconformity.org_id==context.org_id,QaNonconformity.inspection_id==row.id)) is None: db.add(QaNonconformity(org_id=context.org_id,inspection_id=row.id,description="检验结果不合格"))
 db.flush();return row
def close_inspection(db,inspection_id,disposition,context):
 row=db.scalar(select(QaInspection).where(QaInspection.id==inspection_id,QaInspection.org_id==context.org_id));
 if row is None: raise AppError("检验单不存在",code=404)
 if row.status!="submitted" or disposition not in {"rework","accept","scrap"}: raise AppError("关闭检验单必须提交有效处置结论",code=400)
 row.disposition=disposition;row.status="closed";db.flush();return row
def create_nonconformity(db,inspection_id,payload,context): row=QaNonconformity(org_id=context.org_id,inspection_id=inspection_id,**payload);db.add(row);db.flush();return row

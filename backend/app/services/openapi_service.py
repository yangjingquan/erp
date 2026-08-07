import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.platform import SysApiClient

def _hash(secret): return hashlib.sha256(secret.encode()).hexdigest()
def create_api_client(db, payload, context):
    secret=secrets.token_urlsafe(32); row=SysApiClient(org_id=context.org_id,client_key=payload["client_key"],secret_hash=_hash(secret),scopes=payload["scopes"]);db.add(row);db.flush();return row,secret
def issue_api_token(db, client_key, client_secret, scope):
    row=db.scalar(select(SysApiClient).where(SysApiClient.client_key==client_key))
    if row is None or row.status!="active" or _hash(client_secret)!=row.secret_hash: raise AppError("API 客户端无效",code=401)
    if scope not in row.scopes: raise AppError("API scope 不足",code=403)
    now=datetime.now(timezone.utc);return jwt.encode({"type":"api","client_id":row.id,"org_id":row.org_id,"scope":scope,"iat":now,"exp":now+timedelta(minutes=30)},get_settings().jwt_secret_key,algorithm=get_settings().jwt_algorithm)
def authorize_api_token(db, token, required_scope):
    try: payload=jwt.decode(token,get_settings().jwt_secret_key,algorithms=[get_settings().jwt_algorithm])
    except jwt.PyJWTError as exc: raise AppError("API Token 无效",code=401) from exc
    row=db.get(SysApiClient,payload.get("client_id"))
    if row is None or row.status!="active": raise AppError("API 客户端已停用",code=401)
    if required_scope not in row.scopes or payload.get("scope")!=required_scope: raise AppError("API scope 不足",code=403)
    return {"org_id":row.org_id,"client_id":row.id,"scope":required_scope}

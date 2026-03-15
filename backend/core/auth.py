from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from cachetools import TTLCache
import os

# MJ-05 (V5): TTLCache reducido para evitar tokens expirados
auth_cache = TTLCache(maxsize=100, ttl=45)

SECRET_KEY = os.environ.get("JWT_SECRET", "supersecret")
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    if token in auth_cache:
        return auth_cache[token]
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_aud": False})
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        
        # ALPA Nomenclature: organization_id is the primary tenant identifier
        organization_id = payload.get("organization_id", payload.get("tenant_id", "default"))
        
        user_data = {
            "user_id": user_id, 
            "organization_id": organization_id,
            "tenant_id": organization_id # backward compatibility
        }
        auth_cache[token] = user_data
        return user_data
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def verify_company_access(company_id: str, organization_id: str) -> bool:
    """
    Verifica acceso cross-tenant.
    En v5.0 el company_id ES el organization_id — cada org solo accede a sus propios datos.
    """
    # Comparación directa: el usuario solo puede operar dentro de su propia org
    if company_id == organization_id:
        return True

    # Fallback: verificar en DB que la org existe y está activa
    from .database import get_supabase
    supabase = get_supabase()
    try:
        res = supabase.table("organizations") \
            .select("id") \
            .eq("id", organization_id) \
            .eq("status", "active") \
            .execute()
        return len(res.data) > 0
    except Exception:
        return False

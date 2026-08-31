import os,secrets
import bcrypt
from fastapi import APIRouter,Form,Request
from fastapi.responses import HTMLResponse,RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
router=APIRouter(); templates=Jinja2Templates(directory=str(Path(__file__).resolve().parents[2]/"templates"))
def auth_configured(): return all(os.getenv(key) for key in ("DASHBOARD_ADMIN_USERNAME","DASHBOARD_ADMIN_PASSWORD_HASH","SESSION_SECRET_KEY"))
def session_secret(): return os.getenv("SESSION_SECRET_KEY") or secrets.token_urlsafe(32)
def session_secure(): return os.getenv("SESSION_COOKIE_SECURE","false").lower()=="true"
def internal_enabled(): return os.getenv("ENABLE_INTERNAL_SNAPSHOT_ROUTE","false").lower()=="true"
def csrf_token(request): return request.session.setdefault("csrf_token",secrets.token_urlsafe(32))
def valid_csrf(request,token): return bool(token) and secrets.compare_digest(str(request.session.get("csrf_token","")),str(token))
def authenticate(username,password):
    if not auth_configured() or username != os.getenv("DASHBOARD_ADMIN_USERNAME"): return False
    try: return bcrypt.checkpw(password.encode(),os.getenv("DASHBOARD_ADMIN_PASSWORD_HASH","").encode())
    except (ValueError,TypeError): return False
@router.get("/login",response_class=HTMLResponse)
def login_page(request:Request): return templates.TemplateResponse(request,"login.html",{"error":None,"csrf_token":csrf_token(request)})
@router.post("/login",response_class=HTMLResponse)
def login(request:Request,username:str=Form(""),password:str=Form(""),csrf:str=Form("")):
    if not valid_csrf(request,csrf) or not authenticate(username,password): return templates.TemplateResponse(request,"login.html",{"error":"Login failed.","csrf_token":csrf_token(request)},status_code=401)
    request.session.clear(); request.session["authenticated"]=True; request.session["csrf_token"]=secrets.token_urlsafe(32)
    return RedirectResponse("/dashboard",303)
@router.post("/logout")
def logout(request:Request,csrf:str=Form("")):
    if valid_csrf(request,csrf): request.session.clear()
    return RedirectResponse("/login",303)

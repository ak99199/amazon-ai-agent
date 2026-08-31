from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse,RedirectResponse
from app.security.auth import auth_configured,internal_enabled,valid_csrf
class DashboardSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        path=request.url.path; protected=path.startswith("/dashboard") or path.startswith("/api/listings") or path.startswith("/api/portfolio") or path.startswith("/api/internal")
        if path.startswith("/api/internal") and not internal_enabled(): return JSONResponse({"detail":"Not found"},status_code=404)
        if protected:
            if not auth_configured(): return JSONResponse({"detail":"Dashboard authentication is unavailable"},status_code=503) if path.startswith("/api/") else RedirectResponse("/login",303)
            if not request.session.get("authenticated"):
                return JSONResponse({"detail":"Authentication required"},status_code=401) if path.startswith("/api/") else RedirectResponse("/login",303)
            if request.method in ("POST","PUT","PATCH","DELETE") and path.startswith("/api/internal"):
                if not valid_csrf(request,request.headers.get("X-CSRF-Token")): return JSONResponse({"detail":"Invalid request"},status_code=403)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"; response.headers["X-Frame-Options"]="DENY"; response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"; response.headers["Content-Security-Policy"]="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        if path.startswith("/dashboard") or path.startswith("/api/"): response.headers["Cache-Control"]="no-store"
        return response

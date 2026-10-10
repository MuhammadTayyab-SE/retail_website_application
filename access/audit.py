from contextvars import ContextVar

from access.models import AuditEvent

current_request = ContextVar("portal_request", default=None)


def record(action, module, target_id="", outcome="success", details=None, request=None):
    request = request or current_request.get()
    user = getattr(request, "user", None)
    authenticated = user is not None and user.is_authenticated
    return AuditEvent.objects.create(
        actor_id=user.pk if authenticated else None,
        actor_name=user.get_username() if authenticated else "",
        action=action,
        module=module,
        target_id=str(target_id),
        outcome=outcome,
        details=details or {},
    )


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = current_request.set(request)
        try:
            response = self.get_response(request)
            if request.path.startswith("/admin/") or (
                request.user.is_authenticated and request.path.startswith("/categories/")
            ):
                context = getattr(response, "context_data", None) or {}
                form = context.get("adminform")
                invalid = (
                    bool(form and form.form.errors)
                    or bool(context.get("errors"))
                    or bool(context.get("form") and context["form"].errors)
                    or (request.method == "POST" and bool(context.get("protected")))
                )
                match = request.resolver_match
                details = {
                    "route": match.url_name if match else "unknown",
                    "method": request.method,
                    "status": response.status_code,
                }
                module = "portal"
                if match and match.url_name:
                    if match.url_name.startswith("catalog_") or match.url_name in {
                        "category-photo",
                        "category-list",
                    }:
                        module = "catalog.category"
                    elif match.url_name.startswith("auth_user_"):
                        module = "auth.user"
                    elif match.url_name.startswith("access_role_"):
                        module = "access.role"
                    elif match.url_name.startswith("access_auditevent_"):
                        module = "access.auditevent"
                outcome = (
                    "denied"
                    if response.status_code in (401, 403)
                    else ("failed" if response.status_code >= 400 or invalid else "success")
                )
                if response.status_code == 302 and "/admin/login/" in response.get("Location", ""):
                    outcome = "denied"
                if (
                    match
                    and match.url_name == "login"
                    and request.method == "POST"
                    and invalid
                    and not getattr(request, "_audit_login_recorded", False)
                ):
                    record("login", "authentication", outcome="failed", request=request)
                record(
                    "view" if request.method in ("GET", "HEAD") else "request",
                    module,
                    target_id=(
                        str(match.kwargs.get("object_id", match.kwargs.get("pk", "")))[:100]
                        if match
                        else ""
                    ),
                    outcome=outcome,
                    details=details,
                    request=request,
                )
            return response
        finally:
            current_request.reset(token)

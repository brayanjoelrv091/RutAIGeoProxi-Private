import contextvars

# Variables de contexto para aislar peticiones asíncronas
current_tenant_id = contextvars.ContextVar("current_tenant_id", default=None)
is_superadmin = contextvars.ContextVar("is_superadmin", default=False)

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List

from app.shared.database import get_db
from app.shared.deps import get_current_user, require_roles
from app.modules.p1_usuarios.models import Usuario
from app.modules.p6_reportes.services import ReportService
from app.modules.p6_reportes.schemas import ReporteResponse

router = APIRouter(prefix="/reports", tags=["P6 · Reportes"])

admin_dep = require_roles("admin")

@router.get("/incidents/pdf", response_class=FileResponse)
def download_incidents_pdf(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(admin_dep)
):
    """
    CU20 — Exportar reporte de incidentes en PDF.
    """
    # En producción esto debería limitarse a admin/operador
    try:
        file_path = ReportService.generate_incidents_pdf(db, current_user.id, current_user.tenant_id)
        return FileResponse(
            path=file_path, 
            filename="reporte_incidentes.pdf",
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar PDF: {str(e)}"
        )

@router.get("/incidents/excel", response_class=FileResponse)
def download_incidents_excel(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(admin_dep)
):
    """
    CU20 — Exportar reporte de incidentes en Excel.
    """
    try:
        file_path = ReportService.generate_incidents_excel(db, current_user.id, current_user.tenant_id)
        return FileResponse(
            path=file_path,
            filename="reporte_incidentes.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar Excel: {str(e)}"
        )

@router.get("/history", response_model=List[ReporteResponse])
def get_reports_history(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(admin_dep)
):
    """
    Lista el historial de reportes generados.
    """
    from app.modules.p6_reportes.models import ReporteGenerado
    query = db.query(ReporteGenerado)
    if current_user.tenant_id is not None:
        query = query.filter(ReporteGenerado.tenant_id == current_user.tenant_id)
    return query.order_by(ReporteGenerado.fecha_generacion.desc()).all()

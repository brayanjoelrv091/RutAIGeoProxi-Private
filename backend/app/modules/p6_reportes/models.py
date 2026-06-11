from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.shared.database import Base
from app.modules.p7_seguridad_multitenant.models import Tenant  # Fix para NoReferencedTableError

class ReporteGenerado(Base):
    """
    Representa un reporte generado por el sistema (CU19-CU20).
    """
    __tablename__ = "reportes_generados"

    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String, nullable=False)
    tipo_reporte = Column(String, nullable=False)  # 'PDF', 'EXCEL'
    generado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    fecha_generacion = Column(DateTime, default=datetime.utcnow)
    ruta_archivo = Column(String, nullable=True)

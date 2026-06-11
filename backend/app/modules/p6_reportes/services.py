import os
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.shared.config import settings
from app.modules.p2_incidentes.models import Incidente
from app.modules.p6_reportes.models import ReporteGenerado

class ReportService:
    @staticmethod
    def get_report_dir() -> Path:
        report_dir = settings.UPLOAD_DIR / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir

    @classmethod
    def generate_incidents_pdf(cls, db: Session, user_id: int, tenant_id: int | None = None) -> str:
        """
        Genera un reporte PDF de todos los incidentes del tenant.
        """
        query = db.query(Incidente)
        if tenant_id is not None:
            query = query.filter(Incidente.tenant_id == tenant_id)
        incidentes = query.all()
        
        # Lazy imports para evitar errores al iniciar si no están instalados
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
        except ImportError:
            raise HTTPException(
                status_code=500, 
                detail="Módulo 'reportlab' no instalado. No se pueden generar PDFs."
            )

        report_dir = cls.get_report_dir()
        filename = f"reporte_incidentes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = report_dir / filename

        doc = SimpleDocTemplate(str(filepath), pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        # Título
        elements.append(Paragraph("Reporte de Incidentes Atendidos — RutAIGeoProxi", styles['Title']))
        elements.append(Spacer(1, 12))

        # Tabla de datos
        data = [["ID", "Título", "Estado", "Severidad", "Fecha"]]
        for inc in incidentes:
            data.append([
                str(inc.id),
                inc.titulo[:30],
                inc.estado,
                inc.severidad or "N/A",
                inc.creado_en.strftime("%Y-%m-%d %H:%M")
            ])

        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(t)
        doc.build(elements)

        # Registrar en BD
        reporte_db = ReporteGenerado(
            nombre_archivo=filename,
            tipo_reporte="PDF",
            generado_por_id=user_id,
            tenant_id=tenant_id,
            ruta_archivo=str(filepath)
        )
        db.add(reporte_db)
        db.commit()

        return str(filepath)

    @classmethod
    def generate_incidents_excel(cls, db: Session, user_id: int, tenant_id: int | None = None) -> str:
        """
        Genera un reporte Excel de los incidentes usando Pandas.
        """
        query = db.query(Incidente)
        if tenant_id is not None:
            query = query.filter(Incidente.tenant_id == tenant_id)
        incidentes = query.all()
        
        # Lazy import para evitar errores al iniciar
        try:
            import pandas as pd
        except ImportError:
            raise HTTPException(
                status_code=500, 
                detail="Módulo 'pandas' no instalado. No se pueden generar Excels."
            )

        # Convertir a DataFrame
        data = [{
            "ID": inc.id,
            "Título": inc.titulo,
            "Estado": inc.estado,
            "Severidad": inc.severidad,
            "Categoría": inc.categoria,
            "Fecha": inc.creado_en.replace(tzinfo=None) # Excel no maneja bien offsets de zona horaria a veces
        } for inc in incidentes]
        
        df = pd.DataFrame(data)
        
        report_dir = cls.get_report_dir()
        filename = f"reporte_incidentes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = report_dir / filename

        df.to_excel(filepath, index=False)

        # Registrar en BD
        reporte_db = ReporteGenerado(
            nombre_archivo=filename,
            tipo_reporte="EXCEL",
            generado_por_id=user_id,
            tenant_id=tenant_id,
            ruta_archivo=str(filepath)
        )
        db.add(reporte_db)
        db.commit()

        return str(filepath)

"""
P9 — Servicios de Analítica y Operaciones.
"""

import math
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.p2_incidentes.models import Incidente, ClasificacionIncidente
from app.modules.p4_asignacion.models import Asignacion
from app.modules.p9_analitica.models import Cotizacion, CotizacionItem
from app.modules.p9_analitica.schemas import DashboardKPIs, TiempoEstimadoOut, CotizacionCreateManual
from app.modules.p8_realtime.models import EventoEstado
from app.modules.p1_usuarios.models import Usuario

class DashboardService:
    @staticmethod
    def get_kpis(db: Session, tenant_id: int | None) -> DashboardKPIs:
        # ── MAGIA DE CU-28 ──
        # Ya no necesitamos inyectar `filter(Incidente.tenant_id == tenant_id)`
        # El evento `do_orm_execute` en database.py lo intercepta e inyecta solo.
        # Las consultas quedan 100% enfocadas en la lógica de negocio.

        # 1. Totales y Estados
        estado_counts = db.query(Incidente.estado, func.count(Incidente.id)).group_by(Incidente.estado).all()
        
        total_incidentes = sum(c for _, c in estado_counts)
        completados = sum(c for est, c in estado_counts if est == "finalizado")
        cancelados = sum(c for est, c in estado_counts if est == "cancelado")

        # 2. Distribución (Categorías y Severidad)
        cat_counts_db = db.query(Incidente.categoria, func.count(Incidente.id)).filter(Incidente.categoria.isnot(None)).group_by(Incidente.categoria).all()
        sev_counts_db = db.query(Incidente.severidad, func.count(Incidente.id)).filter(Incidente.severidad.isnot(None)).group_by(Incidente.severidad).all()
        
        cat_counts = {c: count for c, count in cat_counts_db}
        sev_counts = {s: count for s, count in sev_counts_db}

        # 3. Tiempos Promedio (Hybrid / SQLite compatible sin N+1)
        tiempos_query = db.query(
            Incidente.id,
            Incidente.estado,
            Incidente.creado_en,
            Incidente.actualizado_en,
            Asignacion.asignado_en,
            Asignacion.taller_id,
            Usuario.nombre.label("taller_nombre"),
            Cotizacion.tiempo_estimado_dias
        )\
        .outerjoin(Asignacion, Asignacion.incidente_id == Incidente.id)\
        .outerjoin(Usuario, Usuario.id == Asignacion.taller_id)\
        .outerjoin(Cotizacion, Cotizacion.incidente_id == Incidente.id).all()

        sum_asig_min = 0.0
        count_asig = 0
        
        sum_res_min = 0.0
        count_res = 0
        sla_cumplidos = 0
        
        talleres_stats = {}

        for row in tiempos_query:
            # Asignación
            if row.asignado_en and row.creado_en:
                sum_asig_min += (row.asignado_en - row.creado_en).total_seconds() / 60.0
                count_asig += 1

            # Resolución y SLA
            if row.estado == "finalizado" and row.actualizado_en and row.creado_en:
                res_diff_sec = (row.actualizado_en - row.creado_en).total_seconds()
                sum_res_min += res_diff_sec / 60.0
                count_res += 1
                
                # SLA
                if row.tiempo_estimado_dias:
                    dias_reales = res_diff_sec / 86400.0
                    if dias_reales <= row.tiempo_estimado_dias:
                        sla_cumplidos += 1
                        
                # Ranking Talleres
                if row.taller_nombre:
                    if row.taller_nombre not in talleres_stats:
                        talleres_stats[row.taller_nombre] = {"total_min": 0.0, "count": 0}
                    talleres_stats[row.taller_nombre]["total_min"] += res_diff_sec / 60.0
                    talleres_stats[row.taller_nombre]["count"] += 1

        avg_asignacion = (sum_asig_min / count_asig) if count_asig > 0 else 0.0
        avg_resolucion = (sum_res_min / count_res) if count_res > 0 else 0.0
        nivel_sla = (sla_cumplidos / count_res * 100) if count_res > 0 else 0.0

        # Taller Efficiency (Top 5)
        talleres_eficientes = [
            {"nombre": k, "avg_resolucion_min": round(v["total_min"] / v["count"], 2)}
            for k, v in talleres_stats.items() if v["count"] > 0
        ]
        talleres_eficientes.sort(key=lambda x: x["avg_resolucion_min"])

        # 4. Zonas Calientes
        zonas_query = db.query(
            Incidente.latitud, Incidente.longitud
        ).filter(Incidente.latitud.isnot(None), Incidente.longitud.isnot(None)).all()
        
        zonas_dict = {}
        for row in zonas_query:
            coord = f"{round(row.latitud, 2)}, {round(row.longitud, 2)}"
            zonas_dict[coord] = zonas_dict.get(coord, 0) + 1
            
        zonas_calientes = [{"coordenadas": k, "cantidad": v} for k, v in zonas_dict.items()]
        zonas_calientes.sort(key=lambda x: x["cantidad"], reverse=True)

        return DashboardKPIs(
            tenant_id=tenant_id,
            total_incidentes=total_incidentes,
            completados=completados,
            cancelados=cancelados,
            tiempo_promedio_asignacion_min=round(avg_asignacion, 2),
            tiempo_promedio_resolucion_min=round(avg_resolucion, 2),
            tiempo_promedio_llegada_min=0.0,
            nivel_cumplimiento_sla=round(nivel_sla, 2),
            incidentes_por_categoria=cat_counts,
            incidentes_por_severidad=sev_counts,
            talleres_mas_eficientes=talleres_eficientes[:5],
            zonas_calientes=zonas_calientes[:10],
        )


class EstimacionService:
    @staticmethod
    def calcular_tiempo_estimado(db: Session, incidente_id: int) -> TiempoEstimadoOut:
        """Calcula el tiempo estimado basado en IA/clasificación."""
        clasificacion = db.query(ClasificacionIncidente).filter(
            ClasificacionIncidente.incidente_id == incidente_id
        ).first()

        if not clasificacion:
            return TiempoEstimadoOut(
                incidente_id=incidente_id,
                tiempo_estimado_dias=2,
                rango_dias="1-3 días",
                razonamiento="Sin clasificación IA, tiempo base por defecto."
            )

        cat = clasificacion.categoria.lower()
        sev = clasificacion.severidad.lower()
        
        base = 1
        if "carroceria" in cat or "choque" in cat:
            base = 5
        elif "motor" in cat or "mecanico" in cat:
            base = 3
            
        if sev == "grave":
            base += 3
        elif sev == "critico":
            base += 5
            
        return TiempoEstimadoOut(
            incidente_id=incidente_id,
            tiempo_estimado_dias=base,
            rango_dias=f"{max(1, base-1)}-{base+2} días",
            razonamiento=f"Categoría '{cat}' y severidad '{sev}' requieren aprox {base} días."
        )


class CotizacionService:
    @staticmethod
    def generar_cotizacion_desde_ia(db: Session, incidente_id: int) -> Cotizacion:
        """Genera una cotización base usando la IA del incidente."""
        
        # Verificar que no exista ya
        existente = db.query(Cotizacion).filter(Cotizacion.incidente_id == incidente_id).first()
        if existente:
            return existente
            
        incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
        if not incidente:
            raise HTTPException(status_code=404, detail="Incidente no encontrado")
            
        clasificacion = db.query(ClasificacionIncidente).filter(
            ClasificacionIncidente.incidente_id == incidente_id
        ).first()
        
        # Cotización base
        cot = Cotizacion(
            incidente_id=incidente_id,
            tenant_id=incidente.tenant_id,
            estado="borrador"
        )
        db.add(cot)
        db.commit()
        db.refresh(cot)
        
        # Calcular items basados en IA
        items = []
        if clasificacion:
            cat = clasificacion.categoria.lower()
            sev = clasificacion.severidad.lower()
            
            # Costo base por diagnostico
            items.append(CotizacionItem(cotizacion_id=cot.id, descripcion="Diagnóstico Técnico Asistido", cantidad=1, precio_unitario=50.0))
            
            if sev == "grave" or sev == "critico":
                items.append(CotizacionItem(cotizacion_id=cot.id, descripcion="Servicio de Grúa/Remolque", cantidad=1, precio_unitario=150.0))
                items.append(CotizacionItem(cotizacion_id=cot.id, descripcion="Mano de obra especializada (Estimación)", cantidad=10, precio_unitario=40.0))
            else:
                items.append(CotizacionItem(cotizacion_id=cot.id, descripcion="Mano de obra general (Estimación)", cantidad=3, precio_unitario=35.0))
                
            if "carroceria" in cat:
                items.append(CotizacionItem(cotizacion_id=cot.id, descripcion="Repuestos Carrocería (Estimación)", cantidad=1, precio_unitario=300.0))
            elif "motor" in cat:
                items.append(CotizacionItem(cotizacion_id=cot.id, descripcion="Repuestos de Motor (Estimación)", cantidad=1, precio_unitario=500.0))
        else:
            items.append(CotizacionItem(cotizacion_id=cot.id, descripcion="Revisión General", cantidad=1, precio_unitario=80.0))
            
        for item in items:
            db.add(item)
            
        # Calcular totales
        subtotal = sum(i.cantidad * i.precio_unitario for i in items)
        iva = subtotal * 0.16 # 16% IVA
        total = subtotal + iva
        
        cot.subtotal = subtotal
        cot.iva = iva
        cot.total = total
        
        # Tiempo estimado
        est = EstimacionService.calcular_tiempo_estimado(db, incidente_id)
        cot.tiempo_estimado_dias = est.tiempo_estimado_dias
        
        db.commit()
        db.refresh(cot)
        return cot
        
    @staticmethod
    def crear_cotizacion_manual(db: Session, schema: CotizacionCreateManual, tenant_id: int) -> Cotizacion:
        """CU-30: Crear cotización manual con cálculo decimal estricto y emisión WebSocket."""
        from decimal import Decimal
        from datetime import datetime, timezone, timedelta
        from app.shared.websocket_manager import manager
        import asyncio

        # Crear cabecera
        cot = Cotizacion(
            incidente_id=schema.incidente_id,
            tenant_id=tenant_id,
            estado="enviada",
            notas=schema.notas,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        db.add(cot)
        db.flush() # Para obtener cot.id

        subtotal = Decimal("0.0")
        items_db = []
        for item in schema.items:
            subtotal += item.cantidad * item.precio_unitario
            items_db.append(CotizacionItem(
                cotizacion_id=cot.id,
                descripcion=item.descripcion,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario
            ))
            
        db.add_all(items_db)

        # Cálculo seguro en backend
        iva = subtotal * Decimal("0.16")
        total = subtotal + iva

        cot.subtotal = subtotal
        cot.iva = iva
        cot.total = total
        
        # Guardar todo
        db.commit()
        db.refresh(cot)

        # Disparar WebSocket al cliente (A4)
        room_name = f"tenant_{tenant_id}_incidente_{schema.incidente_id}"
        payload = {
            "type": "nueva_cotizacion",
            "data": {
                "cotizacion_id": cot.id,
                "total": float(cot.total),
                "expires_at": cot.expires_at.isoformat() if cot.expires_at else None
            }
        }
        # manager.broadcast_to_room es async, pero estamos en contexto síncrono
        # Dependiendo del diseño, podemos usar un background task o event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast_to_room(room_name, payload))
            else:
                loop.run_until_complete(manager.broadcast_to_room(room_name, payload))
        except Exception as e:
            print("Error disparando WebSocket:", e)

        return cot

    @staticmethod
    def responder_cotizacion(db: Session, cotizacion_id: int, respuesta: str, notas: str | None = None) -> Cotizacion:
        """CU-30: Cliente responde a cotización. Valida timeout."""
        from datetime import datetime, timezone
        from app.shared.websocket_manager import manager
        import asyncio
        
        cot = db.query(Cotizacion).filter(Cotizacion.id == cotizacion_id).first()
        if not cot:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")

        if cot.estado not in ["enviada", "borrador"]:
            raise HTTPException(status_code=400, detail=f"La cotización ya fue {cot.estado}")

        # Validar Expiración
        if cot.expires_at and datetime.now(timezone.utc) > cot.expires_at:
            cot.estado = "rechazada"
            cot.notas = "Rechazada automáticamente por Timeout (Expiró)."
            db.commit()
            raise HTTPException(status_code=400, detail="La cotización ha expirado. Solicite una nueva propuesta al taller.")

        # Actualizar
        cot.estado = respuesta.lower()
        if notas:
            cot.notas = f"[{cot.estado.upper()}] {notas}"
            
        db.commit()
        db.refresh(cot)

        # Notificar de vuelta al Taller
        room_name = f"tenant_{cot.tenant_id}_incidente_{cot.incidente_id}"
        payload = {
            "type": "respuesta_cotizacion",
            "data": {
                "cotizacion_id": cot.id,
                "estado": cot.estado
            }
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast_to_room(room_name, payload))
            else:
                loop.run_until_complete(manager.broadcast_to_room(room_name, payload))
        except Exception:
            pass

        return cot

    @staticmethod
    def get_cotizacion(db: Session, cotizacion_id: int) -> Cotizacion:
        cot = db.query(Cotizacion).filter(Cotizacion.id == cotizacion_id).first()
        if not cot:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        return cot

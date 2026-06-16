"""
P4 — Servicio de Asignación Automática (CU14).
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.p2_incidentes.models import Incidente
from app.modules.p3_talleres.models import SolicitudServicio, Taller, Tecnico
from app.modules.p4_asignacion.geoproximity import (
    GeoPoint,
    WorkshopCandidate,
    rank_workshops,
)
from app.modules.p4_asignacion.models import Asignacion


class AssignmentService:
    """Servicio de asignación automática de talleres usando geoproximidad."""

    from fastapi import BackgroundTasks
    @staticmethod
    def auto_assign(
        db: Session,
        incident_id: int,
        max_radius_km: float = 50.0,
        background_tasks: BackgroundTasks = None,
    ) -> tuple[Asignacion, list[WorkshopCandidate]]:
        """
        CU14 — Asignación automática del taller más adecuado.

        Proceso:
            1. Obtener incidente con su ubicación y categoría
            2. Buscar talleres activos con técnicos
            3. Ejecutar algoritmo de ranking (Haversine + disponibilidad + especialidad)
            4. Asignar el taller con mejor puntaje
            5. Crear solicitud de servicio automáticamente

        Returns:
            Tupla (asignación creada, lista de candidatos evaluados).
        """
        # 1. Obtener incidente
        incidente = db.query(Incidente).filter(Incidente.id == incident_id).first()
        if not incidente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incidente no encontrado",
            )

        # Validar que no haya asignación previa activa
        existing = (
            db.query(Asignacion)
            .filter(Asignacion.incidente_id == incident_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este incidente ya tiene una asignación activa",
            )

        # 2. Recopilar talleres activos
        talleres = (
            db.query(Taller)
            .filter(Taller.esta_activo.is_(True))
            .all()
        )
        if not talleres:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay talleres activos disponibles",
            )

        # Optimización: Cargar todos los técnicos de estos talleres en una sola consulta
        taller_ids = [t.id for t in talleres]
        todos_tecnicos = db.query(Tecnico).filter(Tecnico.taller_id.in_(taller_ids)).all()
        
        # Agrupar técnicos por taller
        tech_map: dict[int, list[Tecnico]] = {tid: [] for tid in taller_ids}
        for tc in todos_tecnicos:
            tech_map[tc.taller_id].append(tc)

        workshop_data: list[dict] = []
        for t in talleres:
            tecnicos = tech_map.get(t.id, [])
            disponibles = sum(1 for tc in tecnicos if tc.esta_disponible)
            workshop_data.append({
                "id": t.id,
                "nombre": t.nombre,
                "latitud": t.latitud,
                "longitud": t.longitud,
                "especialidades": t.especialidades or [],
                "tecnicos_disponibles": disponibles,
                "total_tecnicos": len(tecnicos),
                "usuario_propietario_id": t.usuario_propietario_id,
            })

        # 3. Ejecutar ranking
        incident_location = GeoPoint(
            latitud=incidente.latitud,
            longitud=incidente.longitud,
        )
        candidates = rank_workshops(
            incident_location=incident_location,
            incident_category=incidente.categoria,
            workshops=workshop_data,
            max_radius_km=max_radius_km,
        )

        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontraron talleres dentro de {max_radius_km} km del incidente",
            )

        # 4. Seleccionar el mejor candidato
        best = candidates[0]

        # Generar razonamiento detallado
        reasoning_parts = [
            f"Taller seleccionado: '{best.nombre}' (ID: {best.taller_id})",
            f"Distancia: {best.distancia_km} km (score: {best.score_distancia:.3f})",
            f"Disponibilidad: {best.tecnicos_disponibles}/{best.total_tecnicos} técnicos (score: {best.score_disponibilidad:.3f})",
            f"Especialidad match: score {best.score_especialidad:.3f}",
            f"Puntaje total: {best.puntaje_total:.4f}",
            f"Candidatos evaluados: {len(candidates)}",
        ]
        reasoning = " | ".join(reasoning_parts)

        # 5. Crear asignación
        asignacion = Asignacion(
            incidente_id=incident_id,
            taller_id=best.taller_id,
            distancia_km=best.distancia_km,
            puntaje=best.puntaje_total,
            metodo="haversine_multicriteria",
            razonamiento=reasoning,
        )
        db.add(asignacion)

        # 6. Crear solicitud de servicio automáticamente
        solicitud = SolicitudServicio(
            incidente_id=incident_id,
            taller_id=best.taller_id,
            estado="pendiente",
            notas=f"Asignación automática — Distancia: {best.distancia_km} km, Puntaje: {best.puntaje_total:.4f}",
        )
        db.add(solicitud)

        # 7. Actualizar estado del incidente
        incidente.estado = "asignado"
        incidente.tenant_id = next(t.tenant_id for t in talleres if t.id == best.taller_id)

        db.commit()
        db.refresh(asignacion)

        # 8. Notificar al Taller asignado
        owner_id = next(w["usuario_propietario_id"] for w in workshop_data if w["id"] == best.taller_id)
        from app.modules.p5_pagos.services import NotificationService
        if background_tasks:
            background_tasks.add_task(
                NotificationService.send_push_notification,
                db=db,
                user_id=owner_id,
                titulo="Nueva asignación de incidente",
                mensaje=f"Se te ha asignado el incidente #{incident_id}."
            )

        return asignacion, candidates

    @staticmethod
    def get_assignment(db: Session, incident_id: int) -> Asignacion:
        """Obtener asignación de un incidente."""
        asignacion = (
            db.query(Asignacion)
            .filter(Asignacion.incidente_id == incident_id)
            .first()
        )
        if not asignacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asignación no encontrada para este incidente",
            )
        return asignacion

    @staticmethod
    def list_nearby_workshops(db: Session, incident_id: int, max_radius_km: float = 50.0):
        from app.modules.p3_talleres.models import Taller
        incidente = db.query(Incidente).filter(Incidente.id == incident_id).first()
        if not incidente:
            raise HTTPException(status_code=404, detail="Incidente no encontrado")
            
        talleres = db.query(Taller).filter(Taller.esta_activo == True).all()
        nearby = []
        for t in talleres:
            dist = haversine(incidente.latitud, incidente.longitud, t.latitud, t.longitud)
            if dist <= max_radius_km:
                nearby.append({
                    "taller_id": t.id,
                    "nombre": t.nombre,
                    "direccion": t.direccion,
                    "distancia_km": round(dist, 2),
                    "calificacion_promedio": t.calificacion_promedio,
                    "especialidades": t.especialidades
                })
                
        # Ordenar por distancia (más cercano primero)
        nearby.sort(key=lambda x: x["distancia_km"])
        return nearby

    @staticmethod
    def manual_assign(db: Session, incident_id: int, taller_id: int, notas: str | None, background_tasks):
        from app.modules.p3_talleres.models import Taller, SolicitudServicio
        incidente = db.query(Incidente).filter(Incidente.id == incident_id).first()
        if not incidente:
            raise HTTPException(status_code=404, detail="Incidente no encontrado")
            
        if db.query(Asignacion).filter(Asignacion.incidente_id == incident_id).first():
            raise HTTPException(status_code=400, detail="El incidente ya tiene una asignación")
            
        taller = db.query(Taller).filter(Taller.id == taller_id).first()
        if not taller:
            raise HTTPException(status_code=404, detail="Taller no encontrado")
            
        dist = haversine(incidente.latitud, incidente.longitud, taller.latitud, taller.longitud)
        
        asignacion = Asignacion(
            incidente_id=incident_id,
            taller_id=taller_id,
            distancia_km=round(dist, 2),
            puntaje=100.0, # Asignación manual
            metodo="manual",
            razonamiento="Asignado manualmente por el usuario."
        )
        db.add(asignacion)
        
        solicitud = SolicitudServicio(
            incidente_id=incident_id,
            taller_id=taller_id,
            estado="pendiente",
            notas=notas
        )
        db.add(solicitud)
        
        incidente.estado = "asignado"
        incidente.tenant_id = taller.tenant_id
        db.commit()
        db.refresh(asignacion)
        
        # Notificar
        from app.modules.p5_pagos.services import NotificationService
        if background_tasks:
            background_tasks.add_task(
                NotificationService.send_push_notification,
                db=db,
                user_id=taller.usuario_propietario_id,
                titulo="Nueva asignación de incidente (Manual)",
                mensaje=f"Se te ha asignado el incidente #{incident_id}."
            )
            
        return asignacion

"""
P2 — Capa de servicios de Incidentes (CU7, CU8, CU9).
"""

import logging
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload

from app.modules.p2_incidentes.classifier import ClassificationResult, get_classifier
from app.modules.p2_incidentes.models import (
    ClasificacionIncidente,
    Incidente,
    IncidenteMedia,
)
from app.modules.p2_incidentes.schemas import IncidentCreate
from app.modules.p6_auditoria.services import AuditService
from app.shared.storage import upload_file

logger = logging.getLogger(__name__)


class IncidentService:
    """Servicio de gestión de incidentes vehiculares."""

    @staticmethod
    def _generar_secuencia_incidente(db: Session, incidente: Incidente):
        """Asigna el codigo_visual usando el ID propio de la DB (post-flush)"""
        if incidente.id:
            incidente.codigo_visual = f"INC-{incidente.id:04d}"


    @staticmethod
    async def create(
        db: Session,
        user_id: int,
        payload: IncidentCreate,
        sync_hash: str | None = None,
        local_timestamp: str | None = None,
        fotos: list[UploadFile] | None = None,
        audio: UploadFile | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> Incidente:
        """
        CU7 — Reportar incidente con fotos, audio y ubicación GPS.
        CU-23 — Deduplicación offline.
        """
        from datetime import datetime
        from fastapi import HTTPException
        
        # Obtener tenant_id del usuario
        from app.modules.p1_usuarios.models import Usuario
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        tenant_id = user.tenant_id if user else None

        # 1. Deduplicación y Manejo de Conflictos (CU-23)
        dt_local = None
        incidente = None
        if sync_hash:
            if not local_timestamp:
                raise HTTPException(status_code=400, detail="Hash corrupto o Timestamp inválido")
            try:
                dt_local = datetime.fromisoformat(local_timestamp.replace("Z", "+00:00"))
            except Exception:
                raise HTTPException(status_code=400, detail="Hash corrupto o Timestamp inválido")

            existente = db.query(Incidente).filter(Incidente.idempotency_key == sync_hash).first()
            if existente:
                if existente.creado_en_local and dt_local <= existente.creado_en_local:
                    # El registro local es más antiguo o igual al que ya tenemos, ignorar (Devolver HTTP 200/201).
                    return existente
                
                # Es más reciente: Actualizar el registro existente
                existente.titulo = payload.titulo
                existente.descripcion = payload.descripcion
                existente.latitud = payload.latitud
                existente.longitud = payload.longitud
                existente.direccion = payload.direccion
                existente.tipo_busqueda = payload.tipo_busqueda
                existente.taller_preferido_id = payload.taller_preferido_id
                existente.creado_en_local = dt_local
                incidente = existente

        if not incidente:
            # 1. Crear nuevo incidente
            incidente = Incidente(
                usuario_id=user_id,
                tenant_id=tenant_id,
                titulo=payload.titulo,
                descripcion=payload.descripcion,
                latitud=payload.latitud,
                longitud=payload.longitud,
                direccion=payload.direccion,
                estado="nuevo",
                tipo_busqueda=payload.tipo_busqueda,
                taller_preferido_id=payload.taller_preferido_id,
                idempotency_key=sync_hash,
                creado_en_local=dt_local,
            )
            db.add(incidente)

        db.flush()  # Obtener ID sin commit o actualizar BD
        
        # 1.1 Asignar código visual
        if not incidente.codigo_visual:
            IncidentService._generar_secuencia_incidente(db, incidente)
            db.flush()

        # 2. Subir fotos
        image_local_paths: list[str] = []
        temp_dirs: list[str] = []
        if fotos:
            for foto in fotos[:5]:  # Máximo 5 fotos
                url = await upload_file(foto, folder=f"incidentes/{incidente.id}/fotos")
                db.add(
                    IncidenteMedia(
                        incidente_id=incidente.id,
                        tipo_medio="foto",
                        url_archivo=url,
                    )
                )
                # Guardar copia temporal para YOLOv8
                if foto.filename:
                    temp_dir = tempfile.mkdtemp()
                    temp_dirs.append(temp_dir)
                    tmp = Path(temp_dir) / foto.filename
                    await foto.seek(0)
                    content = await foto.read()
                    tmp.write_bytes(content)
                    image_local_paths.append(str(tmp))

        # 3. Subir audio
        audio_local_path: str | None = None
        audio_temp_dir: str | None = None
        if audio:
            url = await upload_file(audio, folder=f"incidentes/{incidente.id}/audio")
            incidente.url_audio = url
            db.add(
                IncidenteMedia(
                    incidente_id=incidente.id,
                    tipo_medio="audio",
                    url_archivo=url,
                )
            )
            # Guardar copia temporal para Whisper
            if audio.filename:
                audio_temp_dir = tempfile.mkdtemp()
                tmp = Path(audio_temp_dir) / audio.filename
                await audio.seek(0)
                content = await audio.read()
                tmp.write_bytes(content)
                audio_local_path = str(tmp)

        # 4. Clasificación automática (CU8)
        try:
            classifier = get_classifier()
            result: ClassificationResult = await classifier.classify(
                text=f"{payload.titulo} {payload.descripcion or ''}",
                image_paths=image_local_paths if image_local_paths else None,
                audio_path=audio_local_path,
            )
            incidente.categoria = result.categoria
            incidente.severidad = result.severidad

            # Lógica de Incertidumbre (Requerimiento Examen 1)
            if result.confianza < 0.5:
                incidente.estado = "incierto"
            else:
                incidente.estado = "clasificado"

            db.add(
                ClasificacionIncidente(
                    incidente_id=incidente.id,
                    categoria=result.categoria,
                    severidad=result.severidad,
                    confianza=result.confianza,
                    razonamiento=result.razonamiento,
                    metodo=result.metodo,
                )
            )
        except Exception:
            logger.exception("Error en clasificación automática")
            # No falla la creación del incidente si la IA falla

        db.commit()
        db.refresh(incidente)

        # Auditoría (CU19)
        AuditService.log(
            db,
            usuario_id=user_id,
            rol="cliente",
            accion=f"Reporte de incidente #{incidente.id} ({incidente.categoria})"
        )

        # Enviar Notificación Push y WS a los talleres
        if background_tasks:
            from app.modules.p3_talleres.models import Taller
            from app.modules.p5_pagos.services import NotificationService
            from app.shared.websocket_manager import manager
            import asyncio
            
            # Si el cliente tiene tenant_id, filtramos por él, si no, tomamos todos los activos (o cercanos)
            if tenant_id:
                talleres_tenant = db.query(Taller).filter(Taller.tenant_id == tenant_id, Taller.esta_activo == True).all()
            else:
                # Cliente global: Mandar broadcast a TODOS los talleres activos (en una versión futura usar radio geo)
                talleres_tenant = db.query(Taller).filter(Taller.esta_activo == True).all()
            
            ws_payload = {
                "type": "nuevo_incidente",
                "incidente_id": incidente.id,
                "titulo": "¡Nuevo Incidente Reportado!",
                "mensaje": f"Un cliente necesita asistencia: {incidente.titulo} ({incidente.severidad})"
            }
            
            for t in talleres_tenant:
                from app.modules.p3_talleres.models import SolicitudServicio
                # Crear Solicitud de Servicio (broadcast a todos los talleres)
                solicitud = SolicitudServicio(
                    incidente_id=incidente.id,
                    taller_id=t.id,
                    estado="pendiente",
                    notas="Incidente reportado, esperando aceptación de un taller."
                )
                db.add(solicitud)
                
                # Transmisión inmediata vía WebSocket (sin DB, 100% en vivo)
                await manager.send_personal_message(ws_payload, str(t.usuario_propietario_id))
                
            db.commit() # Guardar las solicitudes generadas

            for t in talleres_tenant:
                # Push Notification y Notificación DB segura en background
                background_tasks.add_task(
                    NotificationService.send_push_notification_safe,
                    user_id=t.usuario_propietario_id,
                    titulo="¡Nuevo Incidente Reportado!",
                    mensaje=f"Un cliente necesita asistencia: {incidente.titulo} ({incidente.severidad})"
                )

        # Limpiar archivos temporales
        for p in image_local_paths:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass
        if audio_local_path:
            try:
                Path(audio_local_path).unlink(missing_ok=True)
            except OSError:
                pass
        # Limpiar directorios temporales
        for temp_dir in temp_dirs:
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
        if audio_temp_dir:
            try:
                os.rmdir(audio_temp_dir)
            except OSError:
                pass

        # 5. ASIGNACIÓN AUTOMÁTICA O PREFERENCIAL
        if incidente.estado == "clasificado":
            try:
                from app.modules.p4_asignacion.services import AssignmentService
                
                if incidente.tipo_busqueda == "preferido" and incidente.taller_preferido_id:
                    # Asignar directamente al taller preferido
                    AssignmentService.manual_assign(
                        db,
                        incidente.id,
                        incidente.taller_preferido_id,
                        notas="Asignación directa a taller preferido.",
                        background_tasks=background_tasks
                    )
                    AuditService.log(
                        db,
                        accion=f"Asignación a taller preferido para incidente #{incidente.id}",
                        rol="Sistema"
                    )
                    
                    # Calcular timeout
                    timeout_secs = 60 if incidente.severidad == "critico" else 180
                    
                    # Programar fallback
                    if background_tasks:
                        background_tasks.add_task(
                            fallback_assignment_task,
                            incidente.id,
                            timeout_secs
                        )
                else:
                    # Intentar asignar automáticamente en el radio por defecto (50km)
                    AssignmentService.auto_assign(db, incidente.id, background_tasks=background_tasks)
                    
                    # Auditoría de asignación automática
                    AuditService.log(
                        db,
                        accion=f"Asignación automática disparada para incidente #{incidente.id}",
                        rol="Sistema"
                    )
            except Exception as e:
                logger.error(f"No se pudo asignar incidente #{incidente.id}: {e}")

        return incidente

    @staticmethod
    def get_detail(db: Session, incident_id: int, user_id: int | None = None) -> Incidente:
        """
        CU9 — Ficha técnica estructurada del incidente.
        Si user_id se proporciona, valida que sea el dueño (o admin).
        """
        query = (
            db.query(Incidente)
            .options(
                joinedload(Incidente.medios),
                joinedload(Incidente.clasificacion),
            )
            .filter(Incidente.id == incident_id)
        )

        incidente = query.first()
        if not incidente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incidente no encontrado",
            )

        # Validación de propiedad (Security check)
        # Se permite si no hay user_id (pista de admin) o si coincide con el dueño
        if user_id and incidente.usuario_id != user_id:
            # Aquí podríamos verificar el rol si pasáramos el objeto usuario completo, 
            # pero por ahora el llamador (route) decide si pasa el user_id para validar.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para ver este incidente",
            )

        return incidente

    @staticmethod
    def list_by_user(db: Session, user_id: int) -> list[Incidente]:
        """Listar incidentes del usuario autenticado."""
        return (
            db.query(Incidente)
            .filter(Incidente.usuario_id == user_id)
            .order_by(Incidente.creado_en.desc())
            .all()
        )

    @staticmethod
    def list_all(db: Session, tenant_id: int | None = None) -> list[Incidente]:
        """Listar todos los incidentes (admin), filtrados por tenant si aplica."""
        from app.modules.p7_seguridad_multitenant.services import TenantFilterService
        query = db.query(Incidente)
        if tenant_id is not None:
            query = TenantFilterService.apply_tenant_filter(query, Incidente, tenant_id)
        return query.order_by(Incidente.creado_en.desc()).all()

    @staticmethod
    async def reclassify(db: Session, incident_id: int) -> ClasificacionIncidente:
        """CU8 — Re-clasificar manualmente un incidente existente."""
        incidente = (
            db.query(Incidente)
            .options(joinedload(Incidente.medios))
            .filter(Incidente.id == incident_id)
            .first()
        )
        if not incidente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incidente no encontrado",
            )

        # Recopilar datos para clasificación
        text = f"{incidente.titulo} {incidente.descripcion or ''}"

        classifier = get_classifier()
        result = await classifier.classify(text=text)

        # Actualizar o crear clasificación
        existing = (
            db.query(ClasificacionIncidente)
            .filter(ClasificacionIncidente.incidente_id == incident_id)
            .first()
        )
        if existing:
            existing.categoria = result.categoria
            existing.severidad = result.severidad
            existing.confianza = result.confianza
            existing.razonamiento = result.razonamiento
            existing.metodo = result.metodo
            clasificacion = existing
        else:
            clasificacion = ClasificacionIncidente(
                incidente_id=incident_id,
                categoria=result.categoria,
                severidad=result.severidad,
                confianza=result.confianza,
                razonamiento=result.razonamiento,
                metodo=result.metodo,
            )
            db.add(clasificacion)

        incidente.categoria = result.categoria
        incidente.severidad = result.severidad
        incidente.estado = "clasificado"
        db.commit()
        db.refresh(clasificacion)
        return clasificacion

    @staticmethod
    def get_heatmap_data(db: Session, tenant_id: int | None = None) -> list[dict]:
        """Obtener coordenadas de incidentes para renderizar heatmap."""
        from app.modules.p7_seguridad_multitenant.services import TenantFilterService
        query = db.query(Incidente.latitud, Incidente.longitud, Incidente.severidad)
        if tenant_id is not None:
            query = TenantFilterService.apply_tenant_filter(query, Incidente, tenant_id)
        incidentes = query.all()
        return [{"lat": i.latitud, "lng": i.longitud, "severidad": i.severidad} for i in incidentes]

    @staticmethod
    async def update_estado(db: Session, incident_id: int, nuevo_estado: str, tenant_id: int | None = None) -> dict:
        """CU-25: Cambiar el estado del incidente con validación y broadcast."""
        from fastapi import HTTPException
        from app.shared.websocket_manager import manager

        incidente = db.query(Incidente).filter(Incidente.id == incident_id).first()
        if not incidente:
            raise HTTPException(status_code=404, detail="Incidente no encontrado")
            
        # Validación Multi-Tenant
        if tenant_id is not None and incidente.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="No tienes permisos sobre este incidente")

        estado_actual = incidente.estado

        # Transiciones permitidas
        transiciones = {
            "pendiente": ["buscando_taller", "cancelado", "clasificado"],
            "nuevo": ["buscando_taller", "cancelado", "clasificado"],
            "clasificado": ["buscando_taller", "cancelado"],
            "buscando_taller": ["taller_asignado", "cancelado"],
            "taller_asignado": ["en_camino", "cancelado"],
            "en_camino": ["en_atencion", "cancelado"],
            "en_atencion": ["finalizado", "cancelado"],
            "finalizado": [],
            "cancelado": []
        }

        # Permitir que el Taller u Operador avance el estado lógicamente
        permitidos = transiciones.get(estado_actual, [])
        if nuevo_estado not in permitidos:
            raise HTTPException(
                status_code=400, 
                detail=f"Transición inválida: No se puede pasar de '{estado_actual}' a '{nuevo_estado}'"
            )

        # Actualizar en BD
        incidente.estado = nuevo_estado
        db.commit()
        db.refresh(incidente)

        # CU-32: ETA Dinámico cuando entra a "en_atencion"
        if nuevo_estado == "en_atencion":
            await IncidentService.calcular_eta_reparacion(db, incident_id)

        # Broadcast via WebSockets
        room_id = f"tenant_{incidente.tenant_id or 'global'}_incidente_{incident_id}"
        await manager.broadcast_to_room(
            room_id,
            {
                "type": "ESTADO_UPDATED", 
                "incidente_id": incident_id, 
                "nuevo_estado": nuevo_estado
            }
        )

        return {"status": "ok", "estado": nuevo_estado}

    @staticmethod
    async def calcular_eta_reparacion(db: Session, incidente_id: int) -> int:
        """CU-32: Calcular y notificar el ETA de reparación."""
        from sqlalchemy import func
        from app.shared.websocket_manager import manager
        
        incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
        if not incidente or not incidente.tenant_id:
            return 60

        # 1. Historial (Promedio de minutos)
        # Aproximación: extraer el historial de 'finalizado' no está directo por timestamp en este diseño simplificado,
        # así que calcularemos usando el campo de 'creado_en' vs 'actualizado_en' si la DB lo soporta.
        # Para evitar funciones específicas de DB en SQLite/Postgres mezcladas, usamos el promedio de una subquery
        # de los incidentes que están 'finalizado'
        # Usamos extract epoch en PostgreSQL, fallback a un número estático
        try:
            # Consulta SQL estricta asumiendo PostgreSQL: EXTRACT(EPOCH FROM (actualizado_en - creado_en)) / 60
            query = db.query(func.avg(
                func.extract('epoch', Incidente.actualizado_en - Incidente.creado_en) / 60
            )).filter(
                Incidente.tenant_id == incidente.tenant_id,
                Incidente.categoria == incidente.categoria,
                Incidente.estado == "finalizado"
            )
            promedio_hist = query.scalar()
            base_minutos = float(promedio_hist) if promedio_hist else 60.0
        except Exception:
            base_minutos = 60.0

        # 2. Complejidad (Multiplicador IA)
        multiplicador_ia = 1.0
        clasificacion = db.query(ClasificacionIncidente).filter(ClasificacionIncidente.incidente_id == incidente_id).first()
        if clasificacion:
            sev = clasificacion.severidad.lower() if clasificacion.severidad else ""
            if sev == "moderado": multiplicador_ia = 1.2
            elif sev == "grave": multiplicador_ia = 1.5
            elif sev == "critico": multiplicador_ia = 2.0

        # 3. Carga de Trabajo (Workload)
        workload = db.query(func.count(Incidente.id)).filter(
            Incidente.tenant_id == incidente.tenant_id,
            Incidente.estado == "en_atencion"
        ).scalar() or 0
        
        # Fórmula
        multiplicador_workload = 1.0 + (workload * 0.10)
        eta_final = int(base_minutos * multiplicador_ia * multiplicador_workload)
        
        # Guardar en BD
        incidente.tiempo_estimado_reparacion_minutos = eta_final
        db.commit()
        db.refresh(incidente)

        # Emitir WS
        room_id = f"tenant_{incidente.tenant_id}_incidente_{incidente_id}"
        await manager.broadcast_to_room(room_id, {
            "type": "tiempo_reparacion_actualizado",
            "eta_minutos": eta_final
        })
        
        return eta_final

    @staticmethod
    def _timeout_asignacion(db: Session, incidente_id: int, taller_tenant_id: int):
        """CU-31: Fallback tras 5 minutos de no respuesta del taller."""
        from app.shared.websocket_manager import manager
        import asyncio
        
        incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
        if not incidente:
            return
            
        # Si sigue en "taller_asignado", significa que el taller nunca lo aceptó (nunca pasó a "en_camino" o "proceso")
        if incidente.estado == "taller_asignado":
            incidente.estado = "buscando_taller"
            incidente.tenant_id = None  # Quitar asignación
            db.commit()
            
            # Emitir websocket al taller para que desaparezca
            room_id = f"tenant_{taller_tenant_id}"
            payload = {
                "type": "servicio_cancelado_timeout",
                "data": {"incidente_id": incidente_id}
            }
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(manager.broadcast_to_room(room_id, payload))
                else:
                    loop.run_until_complete(manager.broadcast_to_room(room_id, payload))
            except Exception:
                pass

    @staticmethod
    def asignar_taller(
        db: Session, 
        incidente_id: int, 
        taller_id: int, 
        background_tasks: BackgroundTasks
    ) -> Incidente:
        """CU-31: Asignar incidente a un taller."""
        from app.modules.p3_talleres.models import Taller
        from app.shared.websocket_manager import manager
        import asyncio
        
        incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
        if not incidente:
            raise HTTPException(status_code=404, detail="Incidente no encontrado")
            
        if incidente.estado not in ["pendiente", "buscando_taller"]:
            raise HTTPException(status_code=400, detail=f"No se puede asignar un taller en estado '{incidente.estado}'")
            
        taller = db.query(Taller).filter(Taller.id == taller_id).first()
        if not taller:
            raise HTTPException(status_code=404, detail="Taller no encontrado")
            
        # 1. Transferencia de propiedad (Tenant)
        incidente.estado = "taller_asignado"
        incidente.tenant_id = taller.tenant_id
        IncidentService._generar_secuencia_incidente(db, incidente)
        db.commit()
        db.refresh(incidente)
        
        # 2. WebSocket Push al canal del Taller (Tenant)
        room_id = f"tenant_{taller.tenant_id}"
        payload = {
            "type": "nuevo_servicio_asignado",
            "data": {
                "incidente_id": incidente.id,
                "latitud": incidente.latitud,
                "longitud": incidente.longitud,
                "titulo": incidente.titulo
            }
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast_to_room(room_id, payload))
            else:
                loop.run_until_complete(manager.broadcast_to_room(room_id, payload))
        except Exception:
            pass
            
        # 3. Fallback Machine State (5 mins)
        import time
        async def delayed_fallback():
            await asyncio.sleep(300) # 5 minutos
            # Usar una nueva sesión de DB para el background task
            from app.shared.database import SessionLocal
            db_bg = SessionLocal()
            try:
                IncidentService._timeout_asignacion(db_bg, incidente_id, taller.tenant_id)
            finally:
                db_bg.close()
                
        background_tasks.add_task(lambda: asyncio.create_task(delayed_fallback()))
        
        return incidente

    @staticmethod
    def get_tracking(db: Session, incident_id: int) -> dict:
        """Obtener la ubicación del taller y el ETA."""
        incidente = db.query(Incidente).filter(Incidente.id == incident_id).first()
        if not incidente:
            raise HTTPException(status_code=404, detail="Incidente no encontrado")
        
        return {
            "incidente_id": incidente.id,
            "estado": incidente.estado,
            "taller_latitud": incidente.taller_latitud,
            "taller_longitud": incidente.taller_longitud,
            "tiempo_llegada_estimado_minutos": incidente.tiempo_llegada_estimado_minutos,
        }

    @staticmethod
    def report_arrival(db: Session, incident_id: int, background_tasks: BackgroundTasks) -> dict:
        """El taller reporta que ha llegado al lugar del incidente."""
        from app.modules.p5_pagos.services import NotificationService
        incidente = db.query(Incidente).filter(Incidente.id == incident_id).first()
        if not incidente:
            raise HTTPException(status_code=404, detail="Incidente no encontrado")
        
        incidente.estado = "taller_en_lugar"
        db.commit()

        # Enviar Push al cliente
        background_tasks.add_task(
            NotificationService.send_push_notification,
            db=db,
            user_id=incidente.usuario_id,
            titulo="¡El taller ha llegado!",
            mensaje="El técnico ya se encuentra en tu ubicación."
        )

        return {"status": "ok", "incidente_id": incidente.id, "estado": incidente.estado}



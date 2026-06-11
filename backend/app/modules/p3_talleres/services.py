"""
P3 — Capa de servicios de Talleres (CU10, CU11, CU12, CU13).
"""

from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.modules.p2_incidentes.models import Incidente
from app.modules.p3_talleres.models import SolicitudServicio, Taller, Tecnico
from app.modules.p3_talleres.schemas import (
    TRANSICIONES_VALIDAS,
    ServiceStatusUpdate,
    TechnicianCreate,
    WorkshopCreate,
)


class WorkshopService:
    """Servicio de gestión de talleres y técnicos."""

    # ── CU10: Registrar taller ─────────────────────────────────────

    @staticmethod
    def register(db: Session, user_id: int, payload: WorkshopCreate) -> Taller:
        """CU10 — Registrar un nuevo taller."""
        from app.modules.p1_usuarios.models import Usuario
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        
        # Solo bloquear a los de rol 'taller' si ya tienen uno. Admins tienen límites por su Plan SaaS.
        if user and user.rol != "admin":
            existing = db.query(Taller).filter(Taller.usuario_propietario_id == user_id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario ya tiene un taller registrado",
                )
        
        if user and user.rol == "admin" and user.tenant_id:
            from app.modules.p7_seguridad_multitenant.models import Tenant
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant and tenant.plan:
                plan = tenant.plan.lower()
                count = db.query(Taller).filter(Taller.tenant_id == tenant.id).count()
                if plan == "gratis" and count >= 1:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Límite alcanzado. Tu plan Gratis solo permite 1 sucursal. Actualiza a Profesional."
                    )
                elif plan == "profesional" and count >= 3:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Límite alcanzado. Tu plan Profesional solo permite 3 sucursales. Actualiza a Empresarial."
                    )

        tenant_id = user.tenant_id if user else None

        # Crear cuenta de usuario para el taller
        if payload.email and payload.password:
            existente = db.query(Usuario).filter(Usuario.email == payload.email).first()
            if existente:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El correo ya está registrado por otro usuario o taller",
                )
            
            from app.shared.security import get_password_hash
            taller_user = Usuario(
                nombre=payload.nombre,
                email=payload.email,
                hashed_password=get_password_hash(payload.password),
                rol="taller",
                tenant_id=tenant_id,
                esta_activo=True
            )
            db.add(taller_user)
            db.commit()
            db.refresh(taller_user)
            
            if tenant_id:
                from app.modules.p7_seguridad_multitenant.models import TenantMembership
                membership = TenantMembership(
                    usuario_id=taller_user.id,
                    tenant_id=tenant_id,
                    rol_en_tenant="miembro"
                )
                db.add(membership)
                db.commit()
                
            propietario_id = taller_user.id
        else:
            propietario_id = user_id

        taller = Taller(
            usuario_propietario_id=propietario_id,
            tenant_id=tenant_id,
            nombre=payload.nombre,
            direccion=payload.direccion,
            latitud=payload.latitud,
            longitud=payload.longitud,
            telefono=payload.telefono,
            email=payload.email,
            especialidades=payload.especialidades,
            estado_registro="pendiente_tecnicos",
            ultimo_heartbeat=datetime.now(timezone.utc)
        )
        db.add(taller)
        db.commit()
        db.refresh(taller)
        taller.en_linea = True
        return taller

    @staticmethod
    def _is_online(taller: Taller) -> bool:
        if not taller.ultimo_heartbeat:
            return False
        delta = datetime.now(timezone.utc) - taller.ultimo_heartbeat
        return delta.total_seconds() < 120  # 2 minutos

    @staticmethod
    def get_by_id(db: Session, workshop_id: int) -> Taller:
        taller = db.query(Taller).filter(Taller.id == workshop_id).first()
        if not taller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Taller no encontrado",
            )
        taller.en_linea = WorkshopService._is_online(taller)
        return taller

    @staticmethod
    def list_by_owner(db: Session, user_id: int) -> list[Taller]:
        talleres = (
            db.query(Taller)
            .filter(Taller.usuario_propietario_id == user_id)
            .all()
        )
        for t in talleres:
            t.en_linea = WorkshopService._is_online(t)
        return talleres

    @staticmethod
    def list_all(db: Session, search_query: str = None) -> list[Taller]:
        from sqlalchemy import or_
        query = db.query(Taller).filter(Taller.esta_activo == True)
        if search_query:
            query = query.filter(or_(
                Taller.nombre.ilike(f"%{search_query}%"),
                Taller.direccion.ilike(f"%{search_query}%")
            ))
        talleres = query.all()
        for t in talleres:
            t.en_linea = WorkshopService._is_online(t)
        return talleres

    @staticmethod
    def list_tenant_workshops(db: Session, tenant_id: int) -> list[Taller]:
        """List all workshops for a given tenant, regardless of active status."""
        talleres = (
            db.query(Taller)
            .filter(Taller.tenant_id == tenant_id)
            .options(joinedload(Taller.tecnicos))
            .all()
        )
        for t in talleres:
            t.en_linea = WorkshopService._is_online(t)
        return talleres

    # ── FAVORITOS ───────────────────────────────────────────────

    @staticmethod
    def add_favorite(db: Session, user_id: int, workshop_id: int):
        from app.modules.p1_usuarios.models import Usuario
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        taller = WorkshopService.get_by_id(db, workshop_id)
        if taller not in user.talleres_favoritos:
            user.talleres_favoritos.append(taller)
            db.commit()

    @staticmethod
    def remove_favorite(db: Session, user_id: int, workshop_id: int):
        from app.modules.p1_usuarios.models import Usuario
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        taller = WorkshopService.get_by_id(db, workshop_id)
        if taller in user.talleres_favoritos:
            user.talleres_favoritos.remove(taller)
            db.commit()

    @staticmethod
    def list_favorites(db: Session, user_id: int) -> list[Taller]:
        from app.modules.p1_usuarios.models import Usuario
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        return user.talleres_favoritos if user else []

    @staticmethod
    def list_all_active(db: Session, tenant_id: int | None = None, search_query: str = None) -> list[Taller]:
        from app.modules.p7_seguridad_multitenant.services import TenantFilterService
        from sqlalchemy import or_
        query = db.query(Taller).filter(Taller.esta_activo.is_(True))
        if tenant_id is not None:
            query = TenantFilterService.apply_tenant_filter(query, Taller, tenant_id)
        if search_query:
            query = query.filter(or_(
                Taller.nombre.ilike(f"%{search_query}%"),
                Taller.direccion.ilike(f"%{search_query}%")
            ))
        talleres = query.order_by(Taller.nombre).all()
        for t in talleres:
            t.en_linea = WorkshopService._is_online(t)
        return talleres

    @staticmethod
    def buscar_talleres_cercanos(db: Session, lat: float, lng: float, radius_km: float = 50.0) -> list[Taller]:
        """CU-31: Búsqueda geoespacial usando la fórmula de Haversine nativa en DB."""
        from sqlalchemy import func
        
        # 6371 es el radio de la Tierra en kilómetros
        # Haversine formula
        distance_expr = 6371 * func.acos(
            func.cos(func.radians(lat)) * func.cos(func.radians(Taller.latitud)) *
            func.cos(func.radians(Taller.longitud) - func.radians(lng)) +
            func.sin(func.radians(lat)) * func.sin(func.radians(Taller.latitud))
        )
        
        # Seleccionar talleres activos y filtrarlos por radio
        query = (
            db.query(Taller, distance_expr.label("distancia"))
            .filter(Taller.esta_activo == True, Taller.estado_registro == "completado")
            .filter(distance_expr <= radius_km)
            .order_by(distance_expr)
            .limit(20)
        )
        
        resultados = []
        for taller, distancia in query.all():
            taller.distancia_km = round(distancia, 2)
            taller.en_linea = WorkshopService._is_online(taller)
            resultados.append(taller)
            
        return resultados

    # ── HEARTBEAT Y PERFIL ──────────────────────────────────────────

    @staticmethod
    def record_heartbeat(db: Session, user_id: int) -> bool:
        taller = db.query(Taller).filter(Taller.usuario_propietario_id == user_id).first()
        if not taller:
            return False
        taller.ultimo_heartbeat = datetime.now(timezone.utc)
        db.commit()
        return True

    @staticmethod
    def complete_registration(db: Session, user_id: int) -> Taller:
        taller = db.query(Taller).filter(Taller.usuario_propietario_id == user_id).first()
        if not taller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Taller no encontrado",
            )
        taller.estado_registro = "completado"
        db.commit()
        db.refresh(taller)
        taller.en_linea = WorkshopService._is_online(taller)
        return taller

    @staticmethod
    def get_profile(db: Session, user_id: int) -> Taller:
        taller = (
            db.query(Taller)
            .options(joinedload(Taller.tecnicos))
            .filter(Taller.usuario_propietario_id == user_id)
            .first()
        )
        if not taller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Taller no encontrado",
            )
        taller.en_linea = WorkshopService._is_online(taller)
        return taller

    # ── CU10: Registrar técnicos ───────────────────────────────────

    @staticmethod
    def add_technician(
        db: Session, workshop_id: int, owner_id: int, payload: TechnicianCreate
    ) -> Tecnico:
        """CU10 — Agregar técnico a un taller."""
        taller = db.query(Taller).filter(Taller.id == workshop_id).first()
        if not taller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Taller no encontrado",
            )
        if taller.usuario_propietario_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el propietario del taller puede agregar técnicos",
            )
        tecnico = Tecnico(
            taller_id=workshop_id,
            nombre=payload.nombre,
            telefono=payload.telefono,
            especialidad=payload.especialidad,
            latitud=payload.latitud,
            longitud=payload.longitud,
        )
        db.add(tecnico)
        db.commit()
        db.refresh(tecnico)
        return tecnico

    @staticmethod
    def list_technicians(db: Session, workshop_id: int) -> list[Tecnico]:
        return (
            db.query(Tecnico)
            .filter(Tecnico.taller_id == workshop_id)
            .order_by(Tecnico.id)
            .all()
        )

    @staticmethod
    def update_technician_availability(
        db: Session, technician_id: int, owner_id: int, available: bool
    ) -> Tecnico:
        tecnico = (
            db.query(Tecnico)
            .join(Taller, Tecnico.taller_id == Taller.id)
            .filter(
                Tecnico.id == technician_id,
                Taller.usuario_propietario_id == owner_id,
            )
            .first()
        )
        if not tecnico:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Técnico no encontrado o sin permisos",
            )
        tecnico.esta_disponible = available
        db.commit()
        db.refresh(tecnico)
        return tecnico

    # ── CU11: Recepción de solicitudes ─────────────────────────────

    @staticmethod
    def list_pending_requests(
        db: Session, workshop_id: int, owner_id: int
    ) -> list[SolicitudServicio]:
        """CU11 — Listar solicitudes pendientes de un taller."""
        taller = db.query(Taller).filter(Taller.id == workshop_id).first()
        if not taller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Taller no encontrado",
            )
        if taller.usuario_propietario_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sin permisos para ver solicitudes de este taller",
            )
        solicitudes = (
            db.query(SolicitudServicio)
            .options(
                joinedload(SolicitudServicio.incidente).joinedload(Incidente.clasificacion)
            )
            .filter(
                SolicitudServicio.taller_id == workshop_id,
                SolicitudServicio.estado.in_(["pendiente", "proceso"]),
            )
            .order_by(SolicitudServicio.creado_en.desc())
            .all()
        )

        result = []
        for s in solicitudes:
            item = {
                "id": s.id,
                "incidente_id": s.incidente_id,
                "taller_id": s.taller_id,
                "tecnico_id": s.tecnico_id,
                "estado": s.estado,
                "notas": s.notas,
                "creado_en": s.creado_en,
                "actualizado_en": s.actualizado_en,
                "titulo_incidente": s.incidente.titulo if s.incidente else None,
                "categoria_incidente": s.incidente.categoria if s.incidente else None,
                "severidad_incidente": s.incidente.severidad if s.incidente else None,
                "resumen_ia": s.incidente.clasificacion.razonamiento if s.incidente and s.incidente.clasificacion else None,
            }
            result.append(item)
        return result

    # ── CU12: Actualización de estado ──────────────────────────────

    from fastapi import BackgroundTasks
    @staticmethod
    def update_service_status(
        db: Session,
        request_id: int,
        owner_id: int,
        payload: ServiceStatusUpdate,
        background_tasks: BackgroundTasks = None,
    ) -> SolicitudServicio:
        """
        CU12 — Actualizar estado de solicitud con validación de transiciones.
        Transiciones válidas:
            pendiente → proceso | cancelado
            proceso   → atendido | cancelado
        """
        solicitud = (
            db.query(SolicitudServicio)
            .join(Taller, SolicitudServicio.taller_id == Taller.id)
            .filter(
                SolicitudServicio.id == request_id,
                Taller.usuario_propietario_id == owner_id,
            )
            .first()
        )
        if not solicitud:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud no encontrada o sin permisos",
            )

        # Validar transición de estado
        allowed = TRANSICIONES_VALIDAS.get(solicitud.estado, set())
        if payload.estado not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Transición inválida: '{solicitud.estado}' → '{payload.estado}'. "
                    f"Permitidas: {', '.join(sorted(allowed)) if allowed else 'ninguna (estado final)'}"
                ),
            )

        # Manejo de Concurrencia
        if payload.estado == "proceso":
            otra_activa = (
                db.query(SolicitudServicio)
                .filter(
                    SolicitudServicio.incidente_id == solicitud.incidente_id,
                    SolicitudServicio.id != solicitud.id,
                    SolicitudServicio.estado.in_(["proceso", "atendido"])
                )
                .first()
            )
            if otra_activa:
                solicitud.estado = "cancelado"
                solicitud.notas = (solicitud.notas or "") + " [Cancelado: Incidente ya fue aceptado por otro taller]"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Este incidente ya fue aceptado por otro taller. La solicitud ha sido cancelada."
                )

        solicitud.estado = payload.estado
        if payload.notas:
            solicitud.notas = payload.notas
        if payload.tecnico_id:
            solicitud.tecnico_id = payload.tecnico_id

        # Sincronizar estado del incidente
        if payload.estado == "proceso":
            incidente = db.query(Incidente).filter(
                Incidente.id == solicitud.incidente_id
            ).first()
            if incidente:
                incidente.estado = "en_proceso"
        elif payload.estado == "atendido":
            incidente = db.query(Incidente).filter(
                Incidente.id == solicitud.incidente_id
            ).first()
            if incidente:
                incidente.estado = "resuelto"

        db.commit()
        db.refresh(solicitud)

        # CU16 - Notificar al cliente dueño del incidente
        from app.modules.p5_pagos.services import NotificationService
        from app.shared.websockets import manager
        import asyncio

        incidente = db.query(Incidente).filter(Incidente.id == solicitud.incidente_id).first()
        if incidente:
            ws_payload = {
                "type": "estado_servicio_actualizado",
                "incidente_id": incidente.id,
                "nuevo_estado": payload.estado,
                "titulo": "Actualización de Servicio",
                "mensaje": f"Tu incidente ha cambiado al estado: {payload.estado.upper()}"
            }
            # Enviar WS directo
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.send_personal_message(ws_payload, str(incidente.usuario_id)))
            except RuntimeError:
                asyncio.run(manager.send_personal_message(ws_payload, str(incidente.usuario_id)))

            if background_tasks:
                background_tasks.add_task(
                    NotificationService.send_push_notification_safe,
                    user_id=incidente.usuario_id,
                    titulo="Actualización de Servicio",
                    mensaje=f"Tu incidente ha cambiado al estado: {payload.estado.upper()}"
                )

        return solicitud

    # ── CU13: Historial de atenciones ──────────────────────────────

    @staticmethod
    def get_service_history(
        db: Session, workshop_id: int, owner_id: int
    ) -> list[dict]:
        """CU13 — Historial de todas las atenciones del taller."""
        taller = db.query(Taller).filter(Taller.id == workshop_id).first()
        if not taller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Taller no encontrado",
            )
        if taller.usuario_propietario_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sin permisos para ver historial de este taller",
            )

        solicitudes = (
            db.query(SolicitudServicio)
            .options(
                joinedload(SolicitudServicio.incidente).joinedload(Incidente.clasificacion)
            )
            .filter(SolicitudServicio.taller_id == workshop_id)
            .order_by(SolicitudServicio.creado_en.desc())
            .all()
        )

        result = []
        for s in solicitudes:
            item = {
                "id": s.id,
                "incidente_id": s.incidente_id,
                "taller_id": s.taller_id,
                "tecnico_id": s.tecnico_id,
                "estado": s.estado,
                "notas": s.notas,
                "creado_en": s.creado_en,
                "actualizado_en": s.actualizado_en,
                "titulo_incidente": s.incidente.titulo if s.incidente else None,
                "categoria_incidente": s.incidente.categoria if s.incidente else None,
                "severidad_incidente": s.incidente.severidad if s.incidente else None,
                "resumen_ia": s.incidente.clasificacion.razonamiento if s.incidente and s.incidente.clasificacion else None,
            }
            result.append(item)
        return result

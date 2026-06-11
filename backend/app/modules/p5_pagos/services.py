import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.p1_usuarios.models import Usuario
from app.modules.p2_incidentes.models import Incidente
from app.modules.p3_talleres.models import SolicitudServicio, Taller
from app.modules.p5_pagos.models import Notificacion, Pago
from app.modules.p5_pagos.schemas import PagoCreate
from app.shared.websocket_manager import manager


class PaymentService:
    @staticmethod
    async def process_payment(
        db: Session,
        pago_in: PagoCreate,
        current_user: Usuario,
    ) -> Pago:
        """
        CU18 · Simula el procesamiento de un pago.

        Reglas:
            - El incidente debe existir.
            - Un cliente solo puede pagar sus propios incidentes.
            - Un taller no puede procesar pagos directamente.
            - Se evita duplicar pagos completados para el mismo incidente.
        """
        incidente = (
            db.query(Incidente)
            .filter(Incidente.id == pago_in.incidente_id)
            .first()
        )
        if not incidente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incidente no encontrado",
            )

        if current_user.rol == "cliente" and incidente.usuario_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puede pagar incidentes de otro usuario",
            )

        if current_user.rol not in {"admin", "cliente"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo un cliente o admin puede procesar pagos",
            )

        pago_existente = (
            db.query(Pago)
            .filter(
                Pago.incidente_id == pago_in.incidente_id,
                Pago.estado == "completado",
            )
            .first()
        )
        if pago_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este incidente ya tiene un pago completado",
            )

        monto_total = pago_in.monto
        comision = monto_total * 0.10

        from app.modules.p5_pagos.stripe_gateway import StripeGateway
        gateway_result = StripeGateway.process_payment(amount=monto_total, currency=pago_in.moneda)
        
        if not gateway_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error en pasarela de pago: {gateway_result['raw_response']}"
            )
            
        transaccion_id = gateway_result["transaction_id"] or f"TXN-{uuid.uuid4().hex[:8].upper()}"

        nuevo_pago = Pago(
            incidente_id=pago_in.incidente_id,
            monto=monto_total,
            comision_plataforma=comision,
            moneda=pago_in.moneda,
            metodo_pago=pago_in.metodo_pago,
            estado="completado",
            proveedor="stripe",
            transaccion_id=transaccion_id,
            gateway_response=gateway_result["raw_response"]
        )
        db.add(nuevo_pago)

        from app.modules.p6_auditoria.services import AuditService

        AuditService.log(
            db,
            usuario_id=current_user.id,
            rol=current_user.rol,
            accion=(
                f"Pago procesado para incidente #{pago_in.incidente_id}. "
                f"Comision 10%: {comision:.2f} {pago_in.moneda}"
            ),
        )

        recipient_ids = {incidente.usuario_id}
        workshop_owner_ids = (
            db.query(Taller.usuario_propietario_id)
            .join(SolicitudServicio, SolicitudServicio.taller_id == Taller.id)
            .filter(SolicitudServicio.incidente_id == pago_in.incidente_id)
            .distinct()
            .all()
        )
        recipient_ids.update(owner_id for (owner_id,) in workshop_owner_ids)

        message = (
            f"💰 Pago exitoso: {monto_total:.2f} {pago_in.moneda}. "
            f"Comisión App (10%): -{comision:.2f} {pago_in.moneda}. "
            f"Ganancia Taller: {monto_total - comision:.2f} {pago_in.moneda}."
        )
        for user_id in sorted(recipient_ids):
            db.add(
                Notificacion(
                    usuario_id=user_id,
                    titulo="Pago aprobado",
                    mensaje=message,
                    tipo="push",
                )
            )

        db.commit()
        db.refresh(nuevo_pago)

        payload = {
            "type": "payment_approved",
            "incidente_id": nuevo_pago.incidente_id,
            "monto": nuevo_pago.monto,
            "moneda": nuevo_pago.moneda,
            "transaccion_id": transaccion_id,
            "title": "Pago aprobado",
            "message": message,
        }
        for user_id in sorted(recipient_ids):
            await manager.send_personal_message(payload, str(user_id))
            
            # Notificación Push Real
            u = db.query(Usuario).filter(Usuario.id == user_id).first()
            if u and u.fcm_token:
                from app.shared.firebase_config import send_push_notification
                send_push_notification(
                    fcm_token=u.fcm_token,
                    title="Pago aprobado",
                    body=message,
                    data={"type": "payment_approved", "incidente_id": str(nuevo_pago.incidente_id)}
                )

        return nuevo_pago


class NotificationService:
    @staticmethod
    async def send_push_notification_safe(
        user_id: int,
        titulo: str,
        mensaje: str,
    ):
        """
        Versión segura para BackgroundTasks que crea su propia sesión de BD.
        """
        from app.shared.database import SessionLocal
        import logging
        logger = logging.getLogger(__name__)
        db = SessionLocal()
        try:
            await NotificationService.send_push_notification(db, user_id, titulo, mensaje)
        except Exception as e:
            logger.error(f"Error en send_push_notification_safe: {e}")
        finally:
            db.close()

    @staticmethod
    async def send_push_notification(
        db: Session,
        user_id: int,
        titulo: str,
        mensaje: str,
    ):
        """
        CU16 · Envia una notificacion push real (FCM) y via WebSocket.
        """
        nueva_notif = Notificacion(
            usuario_id=user_id,
            titulo=titulo,
            mensaje=mensaje,
            tipo="push",
        )
        db.add(nueva_notif)
        db.commit()

        # ── 1. Enviar vía WebSocket (Tiempo real app abierta) ──
        await manager.send_personal_message(
            {
                "type": "notification",
                "titulo": titulo,
                "mensaje": mensaje,
                "timestamp": str(nueva_notif.creado_at),
            },
            str(user_id),
        )

        # ── 2. Enviar vía FCM (Push real segundo plano) ──
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if user and user.fcm_token:
            from app.shared.firebase_config import send_push_notification
            send_push_notification(
                fcm_token=user.fcm_token,
                title=titulo,
                body=mensaje,
                data={"type": "notification", "id": str(nueva_notif.id)}
            )

        return nueva_notif

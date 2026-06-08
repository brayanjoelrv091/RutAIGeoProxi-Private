"""
P5 — Rutas de Pagos y Notificaciones (CU16, CU17, CU18).
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.shared.deps import get_current_user, get_db, get_token_credentials
from app.shared.security import jwt_payload_safe
from app.modules.p1_usuarios.models import Usuario
from app.modules.p5_pagos.schemas import PagoCreate, PagoResponse, NotificacionResponse
from app.modules.p5_pagos.services import PaymentService, NotificationService
from app.shared.websocket_manager import manager

router = APIRouter(prefix="/payments", tags=["P5 · Pagos y Notificaciones"])

@router.post("/process", response_model=PagoResponse, status_code=status.HTTP_201_CREATED)
async def process_payment(
    pago_in: PagoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    CU18 · Procesar pago en línea (Simulado). Mantenido por retrocompatibilidad.
    """
    return await PaymentService.process_payment(db, pago_in, current_user)

@router.post("/checkout-session/{incidente_id}", summary="CU-33 · Generar Stripe Checkout URL")
def create_checkout_session(
    incidente_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    from app.modules.p2_incidentes.models import Incidente
    from app.modules.p9_analitica.models import Cotizacion
    from app.modules.p5_pagos.stripe_service import StripeHostedService
    
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
        
    if current_user.rol == "cliente" and incidente.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No puedes pagar este incidente")
        
    # Validar que exista cotización aceptada
    cotizacion = db.query(Cotizacion).filter(
        Cotizacion.incidente_id == incidente_id, 
        Cotizacion.estado == "aceptada"
    ).first()
    
    if not cotizacion:
        raise HTTPException(status_code=400, detail="El incidente no tiene una cotización aceptada para cobrar")
        
    result = StripeHostedService.create_checkout_session(
        incidente_id=incidente.id,
        monto=float(cotizacion.total),
        tenant_id=incidente.tenant_id
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail="Error creando sesión de pago")
        
    # Guardar en BD como pendiente
    from app.modules.p5_pagos.models import Pago
    comision = float(cotizacion.total) * 0.10
    
    nuevo_pago = Pago(
        tenant_id=incidente.tenant_id,
        incidente_id=incidente.id,
        monto=cotizacion.total,
        comision_plataforma=comision,
        moneda="USD",
        metodo_pago="stripe_checkout",
        estado="pendiente",
        stripe_checkout_session_id=result["session_id"]
    )
    db.add(nuevo_pago)
    db.commit()
    
    return {"checkout_url": result["checkout_url"]}

from fastapi import Request

@router.post("/webhook", summary="CU-33 · Webhook Seguro de Stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    from app.modules.p5_pagos.stripe_service import StripeHostedService
    from app.modules.p5_pagos.models import Pago
    from app.modules.p2_incidentes.models import Incidente
    import json
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature")
        
    verify_result = StripeHostedService.verify_webhook_signature(payload, sig_header)
    if not verify_result["success"]:
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    event = verify_result["event"]
    
    if event.type == 'checkout.session.completed':
        session = event.data.object
        session_id = session.id
        incidente_id_str = session.metadata.get("incidente_id")
        
        if incidente_id_str:
            pago = db.query(Pago).filter(Pago.stripe_checkout_session_id == session_id).first()
            if pago and pago.estado != "completado":
                pago.estado = "completado"
                pago.transaccion_id = session.payment_intent
                pago.gateway_response = json.dumps(session.to_dict())
                
                # Actualizar Incidente
                incidente = db.query(Incidente).filter(Incidente.id == int(incidente_id_str)).first()
                if incidente:
                    incidente.estado = "pagado"
                    
                db.commit()
                
                # Enviar WebSocket al Taller y Cliente
                if incidente:
                    room_id = f"tenant_{incidente.tenant_id or 'global'}_incidente_{incidente.id}"
                    await manager.broadcast_to_room(
                        room_id,
                        {
                            "type": "pago_completado",
                            "incidente_id": incidente.id,
                            "monto": float(pago.monto)
                        }
                    )
    
    return {"status": "success"}

@router.get("/history", response_model=List[PagoResponse])
def get_payment_history(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista historial de pagos.
    """
    from app.modules.p5_pagos.models import Pago
    from app.modules.p2_incidentes.models import Incidente
    
    query = db.query(Pago)
    
    # Si es cliente, filtrar por sus incidentes
    if current_user.rol == "cliente":
        query = query.join(Incidente).filter(Incidente.usuario_id == current_user.id)
    
    # Si es taller, filtrar por sus incidentes asignados (opcional, pero buena práctica)
    # elif current_user.rol == "taller":
    #     ...
        
    return query.all()

# --- Rutas de Notificaciones ---

@router.get("/notifications", response_model=List[NotificacionResponse])
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtener las notificaciones del usuario actual.
    """
    from app.modules.p5_pagos.models import Notificacion
    return db.query(Notificacion).filter(Notificacion.usuario_id == current_user.id).order_by(Notificacion.creado_at.desc()).all()

@router.delete("/notifications/all", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_notifications(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    from app.modules.p5_pagos.models import Notificacion
    db.query(Notificacion).filter(Notificacion.usuario_id == current_user.id).delete()
    db.commit()
    return None

@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    from app.modules.p5_pagos.models import Notificacion
    notif = db.query(Notificacion).filter(
        Notificacion.id == notification_id,
        Notificacion.usuario_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    db.delete(notif)
    db.commit()
    return None

@router.websocket("/ws/notifications/{user_id}")
async def notifications_websocket(websocket: WebSocket, user_id: int):
    """
    CU16/CU17 · WebSocket para recibir notificaciones push y actualizaciones de estado.
    Requiere autenticación JWT.
    """
    # Autenticación basada en token query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Token requerido")
        return
    
    payload = jwt_payload_safe(token)
    if not payload:
        await websocket.close(code=4001, reason="Token inválido")
        return
    
    # Verificar que el user_id del path coincida con el token
    token_user_id = int(payload.get("sub"))
    if token_user_id != user_id:
        await websocket.close(code=4003, reason="User ID no coincide con token")
        return
    
    await manager.connect(websocket, str(user_id))
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, str(user_id))

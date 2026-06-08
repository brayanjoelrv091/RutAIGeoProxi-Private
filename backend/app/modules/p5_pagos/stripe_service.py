import os
import stripe
from typing import Dict, Any

# Las claves deben venir de variables de entorno en producción
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_mock_secret_key_12345")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_mock_webhook_secret_12345")

class StripeHostedService:
    """
    Servicio de integración con Stripe Checkout (CU-33).
    """

    @staticmethod
    def create_checkout_session(
        incidente_id: int, 
        monto: float, 
        moneda: str = "usd", 
        tenant_id: int = None,
        success_url: str = "rutaigeoproxi://pago/exito",
        cancel_url: str = "rutaigeoproxi://pago/cancelado"
    ) -> Dict[str, Any]:
        """
        Crea una sesión de Checkout alojada por Stripe.
        """
        try:
            # En Stripe, el monto se pasa en centavos
            monto_centavos = int(float(monto) * 100)

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': moneda,
                        'product_data': {
                            'name': f'Reparación de Incidente #{incidente_id}',
                            'description': 'Servicio gestionado a través de RutAIGeoProxi',
                        },
                        'unit_amount': monto_centavos,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'incidente_id': str(incidente_id),
                    'tenant_id': str(tenant_id) if tenant_id else ""
                }
            )

            return {
                "success": True,
                "session_id": session.id,
                "checkout_url": session.url
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def verify_webhook_signature(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """
        Verifica la firma criptográfica del Webhook de Stripe.
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
            return {"success": True, "event": event}
        except ValueError as e:
            # Invalid payload
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            return {"success": False, "error": "Invalid signature"}

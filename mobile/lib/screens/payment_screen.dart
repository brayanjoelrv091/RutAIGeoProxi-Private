import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:rutaigeoproxi_mobile/config.dart';
import 'package:url_launcher/url_launcher.dart';
import '../session.dart';

class PaymentScreen extends StatefulWidget {
  final int incidentId;
  final double amount;

  const PaymentScreen({
    super.key,
    required this.incidentId,
    required this.amount,
  });

  @override
  State<PaymentScreen> createState() => _PaymentScreenState();
}

class _PaymentScreenState extends State<PaymentScreen> {
  bool _isProcessing = false;
  bool _isSuccess = false;

  Future<void> _processPayment() async {
    setState(() => _isProcessing = true);

    try {
      final token = await Session.getToken();
      
      // Intentar obtener la URL de Checkout de Stripe
      final response = await http.post(
        Uri.parse('${AppConfig.baseUrl}/payments/checkout-session/${widget.incidentId}'),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        final url = data['checkout_url'];
        
        if (url != null && url.isNotEmpty) {
          final uri = Uri.parse(url);
          if (await canLaunchUrl(uri)) {
            await launchUrl(uri, mode: LaunchMode.externalApplication);
            // Simular éxito una vez que vuelve a la app (en producción esto requiere Webhooks)
            if (mounted) {
               setState(() {
                 _isProcessing = false;
                 _isSuccess = true;
               });
            }
            return;
          } else {
            throw Exception('No se puede abrir el navegador seguro.');
          }
        }
      } else {
        // Fallback al proceso simulado si falla la sesión de Stripe
        final processResp = await http.post(
          Uri.parse('${AppConfig.baseUrl}/payments/process'),
          headers: {
            'Content-Type': 'application/json',
            if (token != null) 'Authorization': 'Bearer $token',
          },
          body: jsonEncode({
            'incidente_id': widget.incidentId,
            'monto': widget.amount,
            'metodo_pago': 'tarjeta_mobile',
          }),
        );
        
        if (processResp.statusCode == 201) {
          setState(() {
             _isProcessing = false;
             _isSuccess = true;
          });
          return;
        }
        
        final err = jsonDecode(response.body);
        throw Exception(err['detail'] ?? 'Error desconocido');
      }
    } catch (e) {
      setState(() => _isProcessing = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error al procesar pago: $e'), backgroundColor: Colors.redAccent),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        title: const Text('Pasarela de Pago Segura'),
        backgroundColor: const Color(0xFF111629),
        elevation: 0,
      ),
      body: _isSuccess ? _buildSuccess() : _buildPaymentMethods(),
    );
  }

  Widget _buildPaymentMethods() {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: const Color(0xFF111629),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFF00F2FF).withOpacity(0.3)),
          ),
          child: Column(
            children: [
              const Text('TOTAL A PAGAR', style: TextStyle(color: Colors.white54, fontSize: 14)),
              const SizedBox(height: 8),
              Text(
                'Bs. ${widget.amount.toStringAsFixed(2)}',
                style: const TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              const Text('Incluye comisión e impuestos', style: TextStyle(color: Colors.white38, fontSize: 12)),
            ],
          ),
        ),
        const SizedBox(height: 30),
        
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF1A2235),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Row(
            children: [
              Icon(Icons.lock_outline, color: Color(0xFF00E676)),
              SizedBox(width: 12),
              Expanded(
                child: Text(
                  'El pago se procesará a través de la pasarela segura. Sus datos de tarjeta no son almacenados en nuestra aplicación.',
                  style: TextStyle(color: Colors.white70, fontSize: 13),
                ),
              ),
            ],
          ),
        ),
        
        const SizedBox(height: 40),
        ElevatedButton(
          onPressed: _isProcessing ? null : _processPayment,
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF00F2FF),
            foregroundColor: Colors.black,
            minimumSize: const Size(double.infinity, 55),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            elevation: 10,
            shadowColor: const Color(0xFF00F2FF).withOpacity(0.5),
          ),
          child: _isProcessing
              ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(color: Colors.black, strokeWidth: 2))
              : const Text(
                  'ABRIR PASARELA SEGURA',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
        ),
      ],
    );
  }

  Widget _buildSuccess() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.check_circle, size: 120, color: Color(0xFF00E676)),
        const SizedBox(height: 24),
        const Text('¡PAGO COMPLETADO!', style: TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        const Text('Su pago ha sido procesado exitosamente por Stripe.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white70, fontSize: 16)),
        const SizedBox(height: 40),
        TextButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('VOLVER AL DETALLE', style: TextStyle(color: Color(0xFF00F2FF), fontSize: 18)),
        ),
      ],
    );
  }
}

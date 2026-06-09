import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:rutaigeoproxi_mobile/config.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:rutaigeoproxi_mobile/session.dart';
import 'package:rutaigeoproxi_mobile/backend.dart';

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

  bool _esperandoEfectivo = false;
  String? _qrData;

  Future<void> _processStripe() async {
    setState(() => _isProcessing = true);
    try {
      final token = await Session.getToken();
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
            if (mounted) setState(() { _isProcessing = false; _isSuccess = true; });
            return;
          } else {
            throw Exception('No se puede abrir el navegador seguro.');
          }
        }
      }
      throw Exception('Error al conectar con Stripe');
    } catch (e) {
      setState(() => _isProcessing = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  Future<void> _processCash() async {
    setState(() => _isProcessing = true);
    final success = await Backend.requestCashPayment(widget.incidentId);
    if (success && mounted) {
      setState(() {
        _isProcessing = false;
        _esperandoEfectivo = true;
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Taller notificado. Págale en efectivo y espera su confirmación.')));
    } else {
      setState(() => _isProcessing = false);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Error al procesar pago en efectivo')));
    }
  }

  Future<void> _processQR() async {
    setState(() => _isProcessing = true);
    final data = await Backend.requestQrPayment(widget.incidentId);
    if (data != null && data['qr_data'] != null && mounted) {
      setState(() {
        _isProcessing = false;
        _qrData = data['qr_data'];
      });
    } else {
      setState(() => _isProcessing = false);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Error al generar QR')));
    }
  }

  Future<void> _simulateQrSuccess() async {
    setState(() => _isProcessing = true);
    final success = await Backend.confirmQrPayment(widget.incidentId);
    if (success && mounted) {
      setState(() {
        _isProcessing = false;
        _isSuccess = true;
        _qrData = null;
      });
    } else {
      setState(() => _isProcessing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        title: const Text('Métodos de Pago'),
        backgroundColor: const Color(0xFF111629),
        elevation: 0,
      ),
      body: _isSuccess 
          ? _buildSuccess() 
          : _esperandoEfectivo 
              ? _buildWaitingCash() 
              : _qrData != null 
                  ? _buildQrView() 
                  : _buildPaymentMethods(),
    );
  }

  Widget _buildWaitingCash() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const CircularProgressIndicator(color: Colors.orange),
            const SizedBox(height: 24),
            const Text('Esperando confirmación del taller...', style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold), textAlign: TextAlign.center),
            const SizedBox(height: 12),
            const Text('Entrega el efectivo al técnico. Una vez que lo reciba, confirmará en su aplicación y se completará el servicio.', style: TextStyle(color: Colors.white70, fontSize: 16), textAlign: TextAlign.center),
            const SizedBox(height: 40),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('CERRAR', style: TextStyle(color: Color(0xFF00F2FF), fontSize: 16)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQrView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('Escanea para Pagar', style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
              child: Icon(Icons.qr_code_2, size: 200, color: Colors.black),
            ),
            const SizedBox(height: 12),
            Text(_qrData!, style: const TextStyle(color: Colors.white38, fontSize: 10)),
            const SizedBox(height: 40),
            ElevatedButton(
              onPressed: _isProcessing ? null : _simulateQrSuccess,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF00F2FF),
                foregroundColor: Colors.black,
                minimumSize: const Size(double.infinity, 50),
              ),
              child: _isProcessing ? const CircularProgressIndicator(color: Colors.black) : const Text('Simular Pago QR Exitoso'),
            ),
            TextButton(
              onPressed: () => setState(() => _qrData = null),
              child: const Text('Cancelar', style: TextStyle(color: Colors.redAccent)),
            )
          ],
        ),
      ),
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
            ],
          ),
        ),
        const SizedBox(height: 40),
        const Text('Selecciona tu método de pago', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 20),
        
        // EFECTIVO
        _buildPaymentOption(
          icon: Icons.money,
          title: 'Efectivo',
          subtitle: 'Paga directamente al técnico',
          onTap: _processCash,
        ),
        const SizedBox(height: 16),
        
        // QR
        _buildPaymentOption(
          icon: Icons.qr_code,
          title: 'Pago con QR',
          subtitle: 'Transferencia bancaria rápida',
          onTap: _processQR,
        ),
        const SizedBox(height: 16),

        // TARJETA
        _buildPaymentOption(
          icon: Icons.credit_card,
          title: 'Tarjeta de Crédito / Débito',
          subtitle: 'Pago seguro vía Stripe',
          onTap: _processStripe,
          isPrimary: true,
        ),
      ],
    );
  }

  Widget _buildPaymentOption({required IconData icon, required String title, required String subtitle, required VoidCallback onTap, bool isPrimary = false}) {
    return InkWell(
      onTap: _isProcessing ? null : onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isPrimary ? const Color(0xFF00F2FF).withOpacity(0.1) : const Color(0xFF1A2235),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: isPrimary ? const Color(0xFF00F2FF) : Colors.transparent),
        ),
        child: Row(
          children: [
            Icon(icon, color: isPrimary ? const Color(0xFF00F2FF) : Colors.white70, size: 30),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                  Text(subtitle, style: const TextStyle(color: Colors.white54, fontSize: 12)),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: Colors.white24, size: 16),
          ],
        ),
      ),
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
        const Text('Su pago ha sido procesado exitosamente.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white70, fontSize: 16)),
        const SizedBox(height: 40),
        TextButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('VOLVER AL INICIO', style: TextStyle(color: Color(0xFF00F2FF), fontSize: 18)),
        ),
      ],
    );
  }
}

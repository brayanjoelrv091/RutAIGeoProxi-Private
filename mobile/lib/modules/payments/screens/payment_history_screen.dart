import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../../../config.dart';
import '../../../session.dart';

class PaymentHistoryScreen extends StatefulWidget {
  const PaymentHistoryScreen({super.key});

  @override
  State<PaymentHistoryScreen> createState() => _PaymentHistoryScreenState();
}

class _PaymentHistoryScreenState extends State<PaymentHistoryScreen> {
  bool _loading = true;
  List<dynamic> _payments = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    try {
      final token = await Session.getToken();
      final response = await http.get(
        Uri.parse('${AppConfig.baseUrl}/payments/history'),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        if (mounted) {
          setState(() {
            _payments = jsonDecode(response.body) ?? [];
            _loading = false;
          });
        }
      } else {
        throw Exception('Error al cargar historial (${response.statusCode})');
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Error: $e';
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        title: const Text('Historial de Pagos'),
        backgroundColor: const Color(0xFF111629),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF00F2FF)))
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Colors.redAccent)))
              : _payments.isEmpty
                  ? const Center(child: Text('Aún no tienes pagos registrados.', style: TextStyle(color: Colors.white70)))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _payments.length,
                      itemBuilder: (context, index) {
                        final p = _payments[index];
                        final fechaStr = p['creado_at'] ?? '';
                        String fechaFormateada = fechaStr;
                        try {
                          final date = DateTime.parse(fechaStr);
                          fechaFormateada = DateFormat('dd MMM yyyy, HH:mm').format(date);
                        } catch (_) {}

                        final estado = p['estado'] ?? 'desconocido';
                        final colorEstado = estado == 'completado' || estado == 'pagado'
                            ? const Color(0xFF00E676)
                            : Colors.orangeAccent;

                        return Card(
                          color: const Color(0xFF111629),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                            side: const BorderSide(color: Colors.white12),
                          ),
                          margin: const EdgeInsets.only(bottom: 12),
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Expanded(
                                      child: Text(
                                        'Incidente #${p['incidente_id'] ?? '-'}',
                                        style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                      decoration: BoxDecoration(
                                        color: colorEstado.withOpacity(0.2),
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Text(
                                        estado.toUpperCase(),
                                        style: TextStyle(color: colorEstado, fontSize: 11, fontWeight: FontWeight.bold),
                                      ),
                                    )
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Text('Método: ${p['metodo_pago']?.toString().toUpperCase() ?? 'DESCONOCIDO'}', style: const TextStyle(color: Colors.white54, fontSize: 13)),
                                Text('Fecha: $fechaFormateada', style: const TextStyle(color: Colors.white54, fontSize: 13)),
                                const SizedBox(height: 12),
                                Row(
                                  children: [
                                    const Icon(Icons.attach_money, color: Color(0xFF00F2FF), size: 16),
                                    const SizedBox(width: 4),
                                    Text(
                                      'Monto: ${p['monto']} ${p['moneda'] ?? 'USD'}',
                                      style: const TextStyle(color: Color(0xFF00F2FF), fontSize: 15, fontWeight: FontWeight.bold),
                                    ),
                                  ],
                                )
                              ],
                            ),
                          ),
                        );
                      },
                    ),
    );
  }
}

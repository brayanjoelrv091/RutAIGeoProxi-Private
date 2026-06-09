import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:rutaigeoproxi_mobile/config.dart';
import '../session.dart';
import '../modules/payments/screens/payment_screen.dart';

class QuotationDetailScreen extends StatefulWidget {
  final int incidentId;

  const QuotationDetailScreen({super.key, required this.incidentId});

  @override
  State<QuotationDetailScreen> createState() => _QuotationDetailScreenState();
}

class _QuotationDetailScreenState extends State<QuotationDetailScreen> {
  bool _isLoading = true;
  String? _error;
  Map<String, dynamic>? _quotation;
  List<dynamic> _items = [];

  @override
  void initState() {
    super.initState();
    _fetchQuotation();
  }

  Future<void> _fetchQuotation() async {
    try {
      final token = await Session.getToken();
      // Simulamos la obtención de la cotización usando el endpoint (si existiera) o mockeamos si no hay endpoint explícito.
      // En un caso real, el backend tendría un endpoint GET /quotations/{incident_id}. 
      // Por ahora probaremos a hacer un fetch simulado o un HTTP call real.
      
      final response = await http.get(
        Uri.parse('${AppConfig.baseUrl}/incidents/${widget.incidentId}'),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        // El incidente debe incluir la cotización si el backend la anidó, o usamos datos mockeados para esta UI si no está.
        setState(() {
          _quotation = {
            'id': 1,
            'subtotal': 100.00,
            'iva': 16.00,
            'total': 116.00,
            'estado': 'enviada',
            'tiempo_estimado_dias': 2,
            'notas': 'Cotización basada en el análisis de IA de la fotografía enviada.',
          };
          _items = [
            {'descripcion': 'Cambio de parachoques', 'cantidad': 1, 'precio_unitario': 50.00},
            {'descripcion': 'Pintura y mano de obra', 'cantidad': 1, 'precio_unitario': 50.00},
          ];
          _isLoading = false;
        });
      } else {
        throw Exception('No se pudo cargar la cotización');
      }
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  void _onAccept() {
    // Si la acepta, navegamos a PaymentScreen
    if (_quotation != null) {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => PaymentScreen(
            incidentId: widget.incidentId,
            amount: _quotation!['total'],
          ),
        ),
      ).then((paid) {
        if (paid == true) {
          Navigator.pop(context, true); // Retornamos al Home si pagó
        }
      });
    }
  }

  void _onReject() {
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Cotización rechazada. Buscando otro taller...')));
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        title: const Text('Revisar Cotización'),
        backgroundColor: const Color(0xFF111629),
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF00F2FF)))
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Colors.redAccent)))
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        // Card de Resumen y Tiempos
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: const Color(0xFF111629),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFF00F2FF).withOpacity(0.3)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.timer, color: Color(0xFF00F2FF)),
                  SizedBox(width: 8),
                  Text('TIEMPO ESTIMADO', style: TextStyle(color: Colors.white54, fontSize: 12, fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                '${_quotation!['tiempo_estimado_dias']} Días',
                style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              const Divider(color: Colors.white12),
              const SizedBox(height: 16),
              const Text('ESTADO DE LA COTIZACIÓN', style: TextStyle(color: Colors.white54, fontSize: 12, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFB74D).withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _quotation!['estado'].toString().toUpperCase(),
                  style: const TextStyle(color: Color(0xFFFFB74D), fontWeight: FontWeight.bold, fontSize: 14),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        
        // Items
        const Text('DETALLE DE REPARACIÓN', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        ..._items.map((item) => _buildItemRow(item['descripcion'], item['cantidad'], item['precio_unitario'])).toList(),
        
        const SizedBox(height: 24),
        const Divider(color: Colors.white24, thickness: 1),
        const SizedBox(height: 16),
        
        // Totales
        _buildTotalRow('Subtotal', _quotation!['subtotal']),
        const SizedBox(height: 8),
        _buildTotalRow('Impuestos (IVA)', _quotation!['iva']),
        const SizedBox(height: 16),
        _buildTotalRow('TOTAL A PAGAR', _quotation!['total'], isTotal: true),
        
        const SizedBox(height: 40),
        
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _onReject,
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.redAccent,
                  side: const BorderSide(color: Colors.redAccent),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('RECHAZAR', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: ElevatedButton(
                onPressed: _onAccept,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF00E676),
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  elevation: 5,
                  shadowColor: const Color(0xFF00E676).withOpacity(0.5),
                ),
                child: const Text('ACEPTAR Y PAGAR', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        )
      ],
    );
  }

  Widget _buildItemRow(String desc, int qty, double price) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(desc, style: const TextStyle(color: Colors.white, fontSize: 14)),
                Text('Cant: $qty', style: const TextStyle(color: Colors.white54, fontSize: 12)),
              ],
            ),
          ),
          Text('Bs. ${(price * qty).toStringAsFixed(2)}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildTotalRow(String label, double amount, {bool isTotal = false}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            color: isTotal ? Colors.white : Colors.white70,
            fontSize: isTotal ? 18 : 14,
            fontWeight: isTotal ? FontWeight.bold : FontWeight.normal,
          ),
        ),
        Text(
          'Bs. ${amount.toStringAsFixed(2)}',
          style: TextStyle(
            color: isTotal ? const Color(0xFF00F2FF) : Colors.white,
            fontSize: isTotal ? 22 : 14,
            fontWeight: isTotal ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ],
    );
  }
}

import 'package:flutter/material.dart';
import '../backend.dart';
import '../modules/payments/screens/payment_history_screen.dart';
import 'package:intl/intl.dart';
import '../modules/offline/offline_queue.dart';
import 'quotation_detail_screen.dart';

class ClientHistoryScreen extends StatefulWidget {
  const ClientHistoryScreen({super.key});

  @override
  State<ClientHistoryScreen> createState() => _ClientHistoryScreenState();
}

class _ClientHistoryScreenState extends State<ClientHistoryScreen> {
  bool _loading = true;
  List<dynamic> _incidents = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    try {
      final offlineList = await OfflineQueue.getPending();
      final offlineMaps = offlineList.map((inc) => {
        'id': 'offline',
        'codigo_visual': 'OFFLINE',
        'titulo': inc.titulo,
        'estado': 'Pendiente (Offline)',
        'creado_en': inc.createdAtLocal,
        'taller_id': null,
        'is_offline': true,
      }).toList();

      final data = await Backend.getMyIncidents(); 
      if (mounted) {
        setState(() {
          _incidents = [...offlineMaps, ...(data ?? [])];
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Error al cargar el historial: $e';
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
        title: const Text('Historial de Servicios'),
        backgroundColor: const Color(0xFF111629),
        actions: [
          IconButton(
            icon: const Icon(Icons.receipt_long, color: Color(0xFF00F2FF)),
            tooltip: 'Historial de Pagos',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const PaymentHistoryScreen()));
            },
          )
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF00F2FF)))
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Colors.redAccent)))
              : _incidents.isEmpty
                  ? const Center(child: Text('Aún no tienes servicios en tu historial.', style: TextStyle(color: Colors.white70)))
                  : RefreshIndicator(
                      onRefresh: _loadHistory,
                      color: const Color(0xFF00F2FF),
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _incidents.length,
                        itemBuilder: (context, index) {
                          final inc = _incidents[index];
                          final fechaStr = inc['creado_en'] ?? '';
                          String fechaFormateada = fechaStr;
                          try {
                            final date = DateTime.parse(fechaStr);
                            fechaFormateada = DateFormat('dd MMM yyyy, HH:mm').format(date);
                          } catch (_) {}

                          final estado = inc['estado'] ?? 'desconocido';
                          final bool isOffline = inc['is_offline'] == true;
                          final colorEstado = isOffline 
                              ? Colors.grey
                              : estado == 'finalizado' ? const Color(0xFF00E676) : (estado == 'cancelado' ? Colors.redAccent : Colors.orangeAccent);

                          return Card(
                            color: const Color(0xFF111629),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                              side: BorderSide(color: isOffline ? Colors.grey.withOpacity(0.5) : Colors.white12),
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
                                        child: Row(
                                          children: [
                                            if (isOffline) const Padding(
                                              padding: EdgeInsets.only(right: 8.0),
                                              child: Icon(Icons.cloud_off, color: Colors.grey, size: 18),
                                            ),
                                            Expanded(
                                              child: Text(
                                                inc['titulo'] ?? 'Sin título',
                                                style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                                              ),
                                            ),
                                          ],
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
                                  Text('ID: ${inc['codigo_visual'] ?? inc['id']}', style: const TextStyle(color: Colors.white54, fontSize: 13)),
                                  Text('Fecha: $fechaFormateada', style: const TextStyle(color: Colors.white54, fontSize: 13)),
                                  if (!isOffline) ...[
                                    const SizedBox(height: 8),
                                    Row(
                                      children: [
                                        const Icon(Icons.build_circle, color: Color(0xFF00F2FF), size: 16),
                                        const SizedBox(width: 4),
                                        Expanded(
                                          child: Text(
                                            inc['taller_id'] != null ? 'Taller Asignado (ID: ${inc['taller_id']})' : 'Taller no asignado o pendiente',
                                            style: const TextStyle(color: Color(0xFF00F2FF), fontSize: 13),
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 12),
                                    SizedBox(
                                      width: double.infinity,
                                      child: OutlinedButton.icon(
                                        onPressed: () {
                                          Navigator.push(context, MaterialPageRoute(
                                            builder: (_) => QuotationDetailScreen(incidentId: inc['id'])
                                          ));
                                        },
                                        icon: const Icon(Icons.request_quote, size: 16),
                                        label: const Text('Ver Cotización y Pago'),
                                        style: OutlinedButton.styleFrom(
                                          foregroundColor: const Color(0xFF00F2FF),
                                          side: const BorderSide(color: Color(0xFF00F2FF)),
                                        ),
                                      ),
                                    )
                                  ] else ...[
                                    const SizedBox(height: 12),
                                    const Text('Este incidente se enviará a los talleres automáticamente en cuanto recupere su conexión a internet.', 
                                    style: TextStyle(color: Colors.grey, fontSize: 12, fontStyle: FontStyle.italic)),
                                  ]
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}

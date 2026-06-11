import 'package:flutter/material.dart';
import '../backend.dart';
import 'package:intl/intl.dart';

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
      final data = await Backend.getMyIncidents(); // Asumimos que Backend tiene este método
      if (mounted) {
        setState(() {
          _incidents = data ?? [];
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
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF00F2FF)))
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Colors.redAccent)))
              : _incidents.isEmpty
                  ? const Center(child: Text('Aún no tienes servicios en tu historial.', style: TextStyle(color: Colors.white70)))
                  : ListView.builder(
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
                        final colorEstado = estado == 'finalizado' ? const Color(0xFF00E676) : (estado == 'cancelado' ? Colors.redAccent : Colors.orangeAccent);

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
                                        inc['titulo'] ?? 'Sin título',
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
                                Text('ID: ${inc['codigo_visual'] ?? inc['id']}', style: const TextStyle(color: Colors.white54, fontSize: 13)),
                                Text('Fecha: $fechaFormateada', style: const TextStyle(color: Colors.white54, fontSize: 13)),
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

library;

import 'dart:convert';

import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../../assignments/assignment_service.dart';
import '../../incidents/models/incident_model.dart';
import '../../incidents/services/incident_service.dart';
import '../../offline/offline_queue.dart' as oq;
import '../../offline/sync_manager.dart';
import 'dart:async';

class MyIncidentsScreen extends StatefulWidget {
  const MyIncidentsScreen({super.key});

  @override
  State<MyIncidentsScreen> createState() => _MyIncidentsScreenState();
}

class _MyIncidentsScreenState extends State<MyIncidentsScreen> {
  List<Incident> _incidents = [];
  bool _isAdmin = false;
  bool _loading = true;
  String _error = '';
  String _assignMsg = '';
  StreamSubscription? _syncSub;

  @override
  void initState() {
    super.initState();
    _syncSub = SyncManager().notifications.listen((msg) {
      if (mounted) _load();
    });
    _load();
  }

  @override
  void dispose() {
    _syncSub?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final token = await ApiClient.getToken();
      String? role;
      if (token != null && token.contains('.')) {
        try {
          final payloadPart = base64Url.normalize(token.split('.')[1]);
          final payload = jsonDecode(
            utf8.decode(base64Url.decode(payloadPart)),
          ) as Map<String, dynamic>;
          role = payload['role'] as String?;
        } catch (_) {}
      }

      // Load offline incidents
      final pendingOffline = await oq.OfflineQueue.getPending();
      final offlineList = pendingOffline.map((item) => Incident(
        id: -item.idempotencyKey.hashCode,
        usuarioId: 0, // Dummy value for offline display
        titulo: '${item.titulo} (Offline)',
        descripcion: item.descripcion,
        latitud: item.latitud,
        longitud: item.longitud,
        direccion: item.direccion,
        estado: 'pendiente_sync',
        creadoEn: item.createdAtLocal,
      )).toList();

      List<Incident> apiList = [];
      try {
        apiList = await IncidentService.listMyIncidents();
      } catch (e) {
        if (offlineList.isEmpty) rethrow; // Only throw if nothing to show
      }

      setState(() {
        _isAdmin = role == 'admin';
        _incidents = [...offlineList, ...apiList];
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = 'Error de conexión');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _autoAssign(int incidentId) async {
    setState(() => _assignMsg = '');
    try {
      final res = await AssignmentService.autoAssign(incidentId);
      setState(() => _assignMsg = res.message);
      await _load();
    } on ApiException catch (e) {
      setState(() => _assignMsg = e.message);
    }
  }

  Color _statusColor(String estado) {
    return switch (estado) {
      'pendiente_sync' => Colors.grey,
      'nuevo' => Colors.orange,
      'clasificado' => Colors.blue,
      'asignado' => Colors.purple,
      'en_proceso' => Colors.amber,
      'resuelto' => Colors.green,
      _ => Colors.grey,
    };
  }

  Color _severityColor(String? severity) {
    return switch (severity) {
      'leve' => const Color(0xFF66BB6A),
      'moderado' => const Color(0xFFFFA726),
      'grave' => const Color(0xFFEF5350),
      'critico' => const Color(0xFFFF1744),
      _ => Colors.grey,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111629),
        title: const Text(
          'Mis Incidentes',
          style: TextStyle(color: Color(0xFF00F2FF), letterSpacing: 1),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Color(0xFF00F2FF)),
            onPressed: _load,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.pushNamed(context, '/report').then((_) => _load()),
        backgroundColor: const Color(0xFF00F2FF),
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add_alert),
        label: const Text(
          'Reportar',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: Column(
        children: [
          if (_assignMsg.isNotEmpty)
            Container(
              color: const Color(0xFF0D3350),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                _assignMsg,
                style: const TextStyle(color: Color(0xFF00F2FF)),
                textAlign: TextAlign.center,
              ),
            ),
          if (_error.isNotEmpty)
            Container(
              color: const Color(0xFF3B0000),
              padding: const EdgeInsets.all(8),
              child: Text(
                _error,
                style: const TextStyle(color: Color(0xFFFF6B6B)),
                textAlign: TextAlign.center,
              ),
            ),
          if (_loading)
            const Expanded(
              child: Center(
                child: CircularProgressIndicator(color: Color(0xFF00F2FF)),
              ),
            )
          else
            Expanded(
              child: _incidents.isEmpty
                  ? const Center(
                      child: Text(
                        'Sin incidentes reportados',
                        style: TextStyle(color: Colors.white54),
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.all(12),
                      itemCount: _incidents.length,
                      itemBuilder: (_, index) => _IncidentCard(
                        incident: _incidents[index],
                        statusColor: _statusColor(_incidents[index].estado),
                        severityColor: _severityColor(_incidents[index].severidad),
                        onAssign: _isAdmin &&
                                _incidents[index].estado == 'clasificado'
                            ? () => _autoAssign(_incidents[index].id)
                            : null,
                        onTap: () => Navigator.pushNamed(
                          context,
                          '/incident-detail',
                          arguments: _incidents[index].id,
                        ),
                      ),
                    ),
            ),
        ],
      ),
    );
  }
}

class _IncidentCard extends StatelessWidget {
  final Incident incident;
  final Color statusColor;
  final Color severityColor;
  final VoidCallback? onAssign;
  final VoidCallback onTap;

  const _IncidentCard({
    required this.incident,
    required this.statusColor,
    required this.severityColor,
    this.onAssign,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFF111629),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFF1F2744)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    incident.titulo,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: statusColor.withValues(alpha: 0.5),
                    ),
                  ),
                  child: Text(
                    incident.estado,
                    style: TextStyle(color: statusColor, fontSize: 11),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                if (incident.categoria != null)
                  _Tag(incident.categoria!, Colors.blue),
                const SizedBox(width: 6),
                if (incident.severidad != null)
                  _Tag(incident.severidad!, severityColor),
                const Spacer(),
                Text(
                  incident.creadoEn.substring(0, 10),
                  style: const TextStyle(color: Colors.white38, fontSize: 11),
                ),
              ],
            ),
            if (onAssign != null) ...[
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: onAssign,
                  icon: const Icon(Icons.location_on, size: 14),
                  label: const Text(
                    'Asignar Taller Automaticamente',
                    style: TextStyle(fontSize: 12),
                  ),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF00F2FF),
                    side: const BorderSide(color: Color(0xFF00F2FF)),
                    padding: const EdgeInsets.symmetric(vertical: 6),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  final String text;
  final Color color;

  const _Tag(this.text, this.color);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(text, style: TextStyle(color: color, fontSize: 10)),
    );
  }
}

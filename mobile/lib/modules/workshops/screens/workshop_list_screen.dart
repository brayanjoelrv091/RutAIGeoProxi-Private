/// CU10-CU13 — Pantalla principal de Talleres.
///
/// Muestra lista de todos los talleres activos (GET /workshops/all).
/// Rol taller: puede ver sus solicitudes pendientes y acceder al historial.
/// Rol admin/taller: puede registrar un nuevo taller.
library;

import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../models/workshop_model.dart';
import '../services/workshop_service.dart';
import '../../auth/services/auth_service.dart';
import 'workshop_requests_screen.dart';
import 'workshop_history_screen.dart';
import 'workshop_technicians_screen.dart';
import '../../../screens/report_incident_screen.dart';

class WorkshopListScreen extends StatefulWidget {
  const WorkshopListScreen({super.key});

  @override
  State<WorkshopListScreen> createState() => _WorkshopListScreenState();
}

class _WorkshopListScreenState extends State<WorkshopListScreen> with SingleTickerProviderStateMixin {
  List<Workshop> _workshops = [];
  List<Workshop> _favoriteWorkshops = [];
  String? _role;
  bool _loading = true;
  String _error = '';
  TabController? _tabController;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      _role = await AuthService.getRoleFromToken();
      if (_role == 'cliente' && _tabController == null) {
        _tabController = TabController(length: 2, vsync: this);
      }
      final list = await WorkshopService.listAllWorkshops();
      List<Workshop> favs = [];
      if (_role == 'cliente') {
        try {
          favs = await WorkshopService.listMyFavorites();
        } catch (_) {}
      }
      setState(() {
        _workshops = list;
        _favoriteWorkshops = favs;
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = 'Error de conexión o servidor no disponible.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _toggleFavorite(Workshop workshop) async {
    final isFav = _favoriteWorkshops.any((w) => w.id == workshop.id);
    try {
      if (isFav) {
        await WorkshopService.removeFavorite(workshop.id);
      } else {
        await WorkshopService.addFavorite(workshop.id);
      }
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111629),
        title: const Text(
          'Talleres',
          style: TextStyle(color: Color(0xFF0096FF), letterSpacing: 1),
        ),
        bottom: _role == 'cliente' && _tabController != null ? TabBar(
          controller: _tabController,
          indicatorColor: const Color(0xFF0096FF),
          tabs: const [
            Tab(text: 'Todos'),
            Tab(text: 'Favoritos (⭐)'),
          ],
        ) : null,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Color(0xFF0096FF)),
            onPressed: _load,
          ),
        ],
      ),
      floatingActionButton: null,
      body: _role == 'cliente' && _tabController != null
          ? TabBarView(
              controller: _tabController!,
              children: [
                _buildBody(_workshops),
                _buildBody(_favoriteWorkshops),
              ],
            )
          : _buildBody(_workshops),
    );
  }

  Widget _buildBody(List<Workshop> list) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF0096FF)));
    }
    if (_error.isNotEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, color: Color(0xFFFF6B6B), size: 48),
              const SizedBox(height: 12),
              Text(_error, style: const TextStyle(color: Color(0xFFFF6B6B))),
              const SizedBox(height: 16),
              ElevatedButton(onPressed: _load, child: const Text('Reintentar')),
            ],
          ),
        ),
      );
    }
    if (list.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.store_outlined, color: Colors.white24, size: 64),
            SizedBox(height: 16),
            Text('No hay talleres disponibles aún', style: TextStyle(color: Colors.white54, fontSize: 16)),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      color: const Color(0xFF0096FF),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: list.length,
        itemBuilder: (_, i) {
          final w = list[i];
          return _WorkshopCard(
            workshop: w,
            isFavorite: _favoriteWorkshops.any((fav) => fav.id == w.id),
            onToggleFavorite: () => _toggleFavorite(w),
            onHistory: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => WorkshopHistoryScreen(workshop: w),
              ),
            ),
            onTechnicians: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => WorkshopTechniciansScreen(workshop: w),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _WorkshopCard extends StatelessWidget {
  final Workshop workshop;
  final bool isFavorite;
  final VoidCallback onToggleFavorite;
  final VoidCallback onHistory;
  final VoidCallback onTechnicians;

  const _WorkshopCard({
    required this.workshop,
    required this.isFavorite,
    required this.onToggleFavorite,
    required this.onHistory,
    required this.onTechnicians,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF111629),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: workshop.estaActivo
              ? const Color(0xFF0096FF).withValues(alpha: 0.3)
              : Colors.white12,
        ),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0096FF).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.build, color: Color(0xFF0096FF), size: 26),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              workshop.nombre,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: workshop.estaActivo
                                  ? Colors.greenAccent.withValues(alpha: 0.15)
                                  : Colors.red.withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              workshop.estaActivo ? 'Activo' : 'Inactivo',
                              style: TextStyle(
                                color: workshop.estaActivo ? Colors.greenAccent : Colors.redAccent,
                                fontSize: 11,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.location_on_outlined, color: Colors.white38, size: 13),
                          const SizedBox(width: 3),
                          Expanded(
                            child: Text(
                              workshop.direccion,
                              style: const TextStyle(color: Colors.white54, fontSize: 12),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                      if (workshop.especialidades != null && workshop.especialidades!.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Wrap(
                          spacing: 6,
                          children: workshop.especialidades!
                              .take(3)
                              .map((e) => _Chip(e))
                              .toList(),
                        ),
                      ],
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.star, color: Colors.amber, size: 14),
                          const SizedBox(width: 3),
                          Text(
                            workshop.calificacionPromedio.toStringAsFixed(1),
                            style: const TextStyle(color: Colors.white54, fontSize: 12),
                          ),
                          const Spacer(),
                          IconButton(
                            icon: Icon(
                              isFavorite ? Icons.star : Icons.star_border,
                              color: isFavorite ? Colors.amber : Colors.white54,
                              size: 24,
                            ),
                            padding: EdgeInsets.zero,
                            constraints: const BoxConstraints(),
                            onPressed: onToggleFavorite,
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // Acciones rápidas
          const Divider(color: Colors.white12, height: 1),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: onTechnicians,
                  icon: const Icon(Icons.people, size: 16),
                  label: const Text('👷 Técnicos'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF0096FF).withValues(alpha: 0.1),
                    foregroundColor: const Color(0xFF0096FF),
                    padding: const EdgeInsets.symmetric(vertical: 8),
                  ),
                ),
              ),
              const VerticalDivider(color: Colors.white12, width: 1),
              Expanded(
                child: TextButton.icon(
                  onPressed: onHistory,
                  icon: const Icon(Icons.history, size: 16),
                  label: const Text('Historial', style: TextStyle(fontSize: 12)),
                  style: TextButton.styleFrom(foregroundColor: Colors.white54),
                ),
              ),
              const VerticalDivider(color: Colors.white12, width: 1),
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => ReportIncidentScreen(
                          preselectedWorkshop: workshop,
                        ),
                      ),
                    );
                  },
                  icon: const Icon(Icons.car_crash, size: 16),
                  label: const Text('Solicitar Servicio', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF00E676),
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(vertical: 8),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  const _Chip(this.label);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: const Color(0xFF0096FF).withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: const Color(0xFF0096FF).withValues(alpha: 0.4)),
      ),
      child: Text(label, style: const TextStyle(color: Color(0xFF0096FF), fontSize: 10)),
    );
  }
}

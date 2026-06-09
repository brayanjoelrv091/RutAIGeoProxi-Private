import 'package:flutter/material.dart';
import '../backend.dart';

class TenantDashboardScreen extends StatefulWidget {
  const TenantDashboardScreen({super.key});

  @override
  State<TenantDashboardScreen> createState() => _TenantDashboardScreenState();
}

class _TenantDashboardScreenState extends State<TenantDashboardScreen> {
  Map<String, dynamic>? _dashboard;
  List<dynamic> _workshops = [];
  List<dynamic> _members = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _loading = true);
    final dash = await Backend.getTenantDashboard();
    final wks = await Backend.getTenantWorkshops();
    final mbrs = await Backend.getTenantMembers();
    
    if (!mounted) return;
    setState(() {
      _dashboard = dash;
      _workshops = wks;
      _members = mbrs;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Gestión de Empresa')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_dashboard == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Gestión de Empresa')),
        body: const Center(child: Text('Error al cargar dashboard o no tienes permisos.')),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        title: Text(_dashboard!['nombre'] ?? 'Mi Empresa'),
        backgroundColor: const Color(0xFF1A1F35),
      ),
      body: RefreshIndicator(
        onRefresh: _loadData,
        child: ListView(
          padding: const EdgeInsets.all(16.0),
          children: [
            _buildPlanCard(),
            const SizedBox(height: 20),
            const Text('Sucursales / Talleres', style: TextStyle(color: Color(0xFF00F2FF), fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            ..._workshops.map((w) => _buildWorkshopCard(w)).toList(),
            if (_workshops.isEmpty) const Text('No hay talleres registrados.', style: TextStyle(color: Colors.white54)),
            
            const SizedBox(height: 20),
            const Text('Personal (Miembros)', style: TextStyle(color: Color(0xFF00F2FF), fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            ..._members.map((m) => _buildMemberCard(m)).toList(),
            if (_members.isEmpty) const Text('No hay personal registrado.', style: TextStyle(color: Colors.white54)),
          ],
        ),
      ),
    );
  }

  Widget _buildPlanCard() {
    final plan = (_dashboard!['plan'] ?? '').toString().toUpperCase();
    final limiteT = _dashboard!['limite_talleres'].toString();
    final currentT = _dashboard!['talleres_registrados'].toString();
    final limiteU = _dashboard!['limite_usuarios'].toString();
    final currentU = _dashboard!['usuarios_registrados'].toString();
    
    return Card(
      color: const Color(0xFF1A1F35),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Plan Actual', style: TextStyle(color: Colors.white54, fontSize: 14)),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: plan == 'EMPRESARIAL' ? const Color(0xFFFFB74D) : const Color(0xFF00E676),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(plan, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                ),
              ],
            ),
            const SizedBox(height: 15),
            _buildProgressRow('Talleres', currentT, limiteT),
            const SizedBox(height: 10),
            _buildProgressRow('Usuarios', currentU, limiteU),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressRow(String title, String current, String limit) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(title, style: const TextStyle(color: Colors.white, fontSize: 16)),
        Text('$current / $limit', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildWorkshopCard(Map<String, dynamic> w) {
    final bool online = w['en_linea'] == true;
    return Card(
      color: const Color(0xFF1A1F35),
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: Icon(Icons.build_circle, color: online ? Colors.green : Colors.grey),
        title: Text(w['nombre'] ?? '', style: const TextStyle(color: Colors.white)),
        subtitle: Text(w['direccion'] ?? '', style: const TextStyle(color: Colors.white54)),
        trailing: Text(online ? 'ONLINE' : 'OFFLINE', style: TextStyle(color: online ? Colors.green : Colors.grey, fontSize: 12)),
      ),
    );
  }

  Widget _buildMemberCard(Map<String, dynamic> m) {
    return Card(
      color: const Color(0xFF1A1F35),
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: const Icon(Icons.person, color: Color(0xFF00F2FF)),
        title: Text(m['nombre'] ?? '', style: const TextStyle(color: Colors.white)),
        subtitle: Text(m['email'] ?? '', style: const TextStyle(color: Colors.white54)),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(color: Colors.white12, borderRadius: BorderRadius.circular(5)),
          child: Text((m['rol'] ?? '').toString().toUpperCase(), style: const TextStyle(color: Colors.white70, fontSize: 10)),
        ),
      ),
    );
  }
}

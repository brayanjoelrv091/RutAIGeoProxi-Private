import 'package:flutter/material.dart';

import '../backend.dart';
import 'map_explorer_screen.dart';
import 'workshop_explorer_screen.dart';
import 'quotation_detail_screen.dart';
import 'tenant_dashboard_screen.dart';
import 'support_chat_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.onLogout});

  final Future<void> Function() onLogout;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Map<String, dynamic>? _me;
  String? _error;
  bool _loading = true;

  final _brand = TextEditingController();
  final _model = TextEditingController();
  final _plate = TextEditingController();
  final _year = TextEditingController();
  String? _vehErr;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _brand.dispose();
    _model.dispose();
    _plate.dispose();
    _year.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final m = await Backend.me();
    if (!mounted) return;
    setState(() {
      _me = m;
      _loading = false;
      if (m == null) _error = 'No se pudo cargar el perfil.';
    });
  }

  Future<void> _addVehicle() async {
    final role = _me?['role'] as String?;
    if (role != 'cliente') {
      setState(() => _vehErr = 'Solo rol cliente puede gestionar vehículos.');
      return;
    }
    setState(() => _vehErr = null);
    final y = int.tryParse(_year.text.trim());
    final err = await Backend.addVehicle(
      brand: _brand.text.trim(),
      model: _model.text.trim(),
      licensePlate: _plate.text.trim(),
      year: y,
    );
    if (!mounted) return;
    if (err != null) {
      setState(() => _vehErr = err);
    } else {
      _brand.clear();
      _model.clear();
      _plate.clear();
      _year.clear();
      await _load();
    }
  }

  Future<void> _delete(int id) async {
    await Backend.deleteVehicle(id);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Inicio'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await widget.onLogout();
            },
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
                if (_me != null) ...[
                  Text('${_me!['name']}', style: Theme.of(context).textTheme.titleLarge),
                  Text('${_me!['email']}'),
                  Text('Rol: ${_me!['role']}'),
                  const SizedBox(height: 10),
                  ElevatedButton.icon(
                    onPressed: _showPasswordChangeModal,
                    icon: const Icon(Icons.lock_outline, color: Colors.black),
                    label: const Text('Cambiar Contraseña', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF00F2FF)),
                  ),
                  if (_me!['role'] == 'admin') ...[
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const TenantDashboardScreen()),
                        );
                      },
                      icon: const Icon(Icons.business, color: Colors.black),
                      label: const Text('⚙️ Gestión de Empresa (SaaS)', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF00F2FF),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => const MapExplorerScreen()),
                      );
                    },
                    icon: const Icon(Icons.explore, color: Colors.black),
                    label: const Text('🗺️ Explorar Mapa (Global)', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF00F2FF),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => const WorkshopExplorerScreen()),
                      );
                    },
                    icon: const Icon(Icons.build_circle, color: Colors.black),
                    label: const Text('🔧 Buscar Talleres (CU-31)', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF00E676),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () {
                      // Usamos ID=1 como prueba para la cotización
                      Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => const QuotationDetailScreen(incidentId: 1)),
                      );
                    },
                    icon: const Icon(Icons.request_quote, color: Colors.black),
                    label: const Text('📄 Ver Cotización de Prueba (CU-30/32)', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFFFB74D),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (_me!['role'] == 'cliente') ...[
                    const Text('Vehículos', style: TextStyle(fontWeight: FontWeight.bold)),
                    ..._vehicles(),
                    const SizedBox(height: 12),
                    const Text('Nuevo vehículo'),
                    TextField(controller: _brand, decoration: const InputDecoration(labelText: 'Marca')),
                    TextField(controller: _model, decoration: const InputDecoration(labelText: 'Modelo')),
                    TextField(controller: _plate, decoration: const InputDecoration(labelText: 'Placa')),
                    TextField(controller: _year, decoration: const InputDecoration(labelText: 'Año (opcional)'), keyboardType: TextInputType.number),
                    if (_vehErr != null) Text(_vehErr!, style: const TextStyle(color: Colors.red)),
                    FilledButton(onPressed: _addVehicle, child: const Text('Guardar')),
                  ] else
                    const Text('En Ciclo 1 los vehículos en API son solo para rol cliente.', style: TextStyle(color: Colors.black54)),
                ],
              ],
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const SupportChatScreen()),
          );
        },
        backgroundColor: const Color(0xFF00F2FF),
        foregroundColor: Colors.black,
        child: const Icon(Icons.support_agent),
        tooltip: 'Soporte en línea',
      ),
    );
  }

  List<Widget> _vehicles() {
    final list = _me!['vehicles'];
    if (list is! List || list.isEmpty) {
      return [const Text('Sin vehículos.')];
    }
    return list.map<Widget>((v) {
      final m = v as Map<String, dynamic>;
      final id = m['id'] as int;
      return ListTile(
        title: Text('${m['brand']} ${m['model']}'),
        subtitle: Text('${m['license_plate']}'),
        trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => _delete(id)),
      );
    }).toList();
  }

  void _showPasswordChangeModal() {
    final curCtrl = TextEditingController();
    final newCtrl = TextEditingController();
    bool obscureCur = true;
    bool obscureNew = true;
    bool loading = false;
    String? errorMsg;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF1A1F35),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Padding(
              padding: EdgeInsets.only(
                bottom: MediaQuery.of(context).viewInsets.bottom,
                left: 20,
                right: 20,
                top: 20,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Cambiar Contraseña', style: TextStyle(color: Color(0xFF00F2FF), fontSize: 20, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 20),
                  TextField(
                    controller: curCtrl,
                    obscureText: obscureCur,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: 'Contraseña Actual',
                      labelStyle: const TextStyle(color: Colors.white54),
                      suffixIcon: IconButton(
                        icon: Icon(obscureCur ? Icons.visibility_off : Icons.visibility, color: const Color(0xFF00F2FF)),
                        onPressed: () => setModalState(() => obscureCur = !obscureCur),
                      ),
                      filled: true,
                      fillColor: const Color(0xFF0A0E1A),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: newCtrl,
                    obscureText: obscureNew,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: 'Nueva Contraseña',
                      labelStyle: const TextStyle(color: Colors.white54),
                      helperText: 'Mínimo 8 caracteres, 1 mayúscula, 1 número',
                      helperStyle: const TextStyle(color: Colors.white38),
                      suffixIcon: IconButton(
                        icon: Icon(obscureNew ? Icons.visibility_off : Icons.visibility, color: const Color(0xFF00F2FF)),
                        onPressed: () => setModalState(() => obscureNew = !obscureNew),
                      ),
                      filled: true,
                      fillColor: const Color(0xFF0A0E1A),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                  if (errorMsg != null) ...[
                    const SizedBox(height: 10),
                    Text(errorMsg!, style: const TextStyle(color: Colors.redAccent)),
                  ],
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: ElevatedButton(
                      onPressed: loading ? null : () async {
                        final cur = curCtrl.text;
                        final neo = newCtrl.text;
                        if (cur.isEmpty || neo.isEmpty) {
                          setModalState(() => errorMsg = 'Completa todos los campos');
                          return;
                        }
                        if (neo.length < 8 || !RegExp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d\w\W]{8,}$').hasMatch(neo)) {
                          setModalState(() => errorMsg = 'Contraseña débil. Sigue las reglas.');
                          return;
                        }

                        setModalState(() { loading = true; errorMsg = null; });
                        final err = await Backend.changePassword(currentPassword: cur, newPassword: neo);
                        
                        if (!ctx.mounted) return;
                        if (err != null) {
                          setModalState(() { loading = false; errorMsg = err; });
                        } else {
                          Navigator.pop(ctx);
                          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Contraseña actualizada', style: TextStyle(color: Colors.black)), backgroundColor: Color(0xFF00F2FF)));
                        }
                      },
                      style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF00F2FF)),
                      child: loading 
                        ? const CircularProgressIndicator(color: Colors.black) 
                        : const Text('ACTUALIZAR CONTRASEÑA', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            );
          }
        );
      }
    );
  }
}

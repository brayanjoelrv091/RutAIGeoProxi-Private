/// CU10 — Pantalla de registro de nuevo taller.
///
/// POST /workshops → registra nombre, dirección, coordenadas, etc.
library;

import 'package:flutter/material.dart';

import '../../../core/api_client.dart';
import '../services/workshop_service.dart';

class RegisterWorkshopScreen extends StatefulWidget {
  const RegisterWorkshopScreen({super.key});

  @override
  State<RegisterWorkshopScreen> createState() => _RegisterWorkshopScreenState();
}

class _RegisterWorkshopScreenState extends State<RegisterWorkshopScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nombreCtrl = TextEditingController();
  final _direccionCtrl = TextEditingController();
  final _latCtrl = TextEditingController();
  final _lngCtrl = TextEditingController();
  final _telefonoCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _especialidadCtrl = TextEditingController();

  final List<String> _especialidades = [];
  bool _loading = false;

  @override
  void dispose() {
    _nombreCtrl.dispose();
    _direccionCtrl.dispose();
    _latCtrl.dispose();
    _lngCtrl.dispose();
    _telefonoCtrl.dispose();
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    _especialidadCtrl.dispose();
    super.dispose();
  }

  void _addEspecialidad() {
    final val = _especialidadCtrl.text.trim();
    if (val.isNotEmpty && !_especialidades.contains(val)) {
      setState(() => _especialidades.add(val));
      _especialidadCtrl.clear();
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);
    try {
      await WorkshopService.registerWorkshop(
        nombre: _nombreCtrl.text.trim(),
        direccion: _direccionCtrl.text.trim(),
        latitud: double.parse(_latCtrl.text.trim()),
        longitud: double.parse(_lngCtrl.text.trim()),
        telefono: _telefonoCtrl.text.trim().isNotEmpty ? _telefonoCtrl.text.trim() : null,
        email: _emailCtrl.text.trim().isNotEmpty ? _emailCtrl.text.trim() : null,
        password: _passwordCtrl.text,
        especialidades: _especialidades.isNotEmpty ? List.from(_especialidades) : null,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('✅ Taller registrado exitosamente'),
            backgroundColor: Color(0xFF00C853),
          ),
        );
        Navigator.pop(context);
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.message}')),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111629),
        title: const Text(
          'Registrar Taller',
          style: TextStyle(color: Color(0xFF0096FF)),
        ),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const _SectionHeader('Datos del Taller'),
            const SizedBox(height: 12),
            _buildField(_nombreCtrl, 'Nombre *', validator: (v) => v!.isEmpty ? 'Requerido' : null),
            const SizedBox(height: 12),
            _buildField(_direccionCtrl, 'Dirección *', validator: (v) => v!.isEmpty ? 'Requerido' : null),
            const SizedBox(height: 16),
            const _SectionHeader('Coordenadas GPS'),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _buildField(
                    _latCtrl,
                    'Latitud *',
                    hint: '-33.4500',
                    numeric: true,
                    validator: (v) {
                      if (v == null || v.isEmpty) return 'Requerido';
                      if (double.tryParse(v) == null) return 'Número inválido';
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildField(
                    _lngCtrl,
                    'Longitud *',
                    hint: '-70.6500',
                    numeric: true,
                    validator: (v) {
                      if (v == null || v.isEmpty) return 'Requerido';
                      if (double.tryParse(v) == null) return 'Número inválido';
                      return null;
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const _SectionHeader('Contacto (opcional)'),
            const SizedBox(height: 12),
            _buildField(_telefonoCtrl, 'Teléfono', hint: '+56 9 1234 5678'),
            const SizedBox(height: 12),
            _buildField(_emailCtrl, 'Email', hint: 'taller@ejemplo.com', validator: (v) => v!.isEmpty ? 'Requerido para la cuenta' : null),
            const SizedBox(height: 12),
            _buildField(_passwordCtrl, 'Contraseña *', hint: 'Mínimo 8 caracteres', obscure: true, validator: (v) => v == null || v.length < 8 ? 'Mínimo 8 caracteres' : null),
            const SizedBox(height: 16),
            const _SectionHeader('Especialidades'),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _especialidadCtrl,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: 'Agregar especialidad',
                      labelStyle: const TextStyle(color: Colors.white54),
                      filled: true,
                      fillColor: const Color(0xFF1A1F38),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide.none,
                      ),
                    ),
                    onFieldSubmitted: (_) => _addEspecialidad(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: _addEspecialidad,
                  icon: const Icon(Icons.add_circle, color: Color(0xFF0096FF), size: 30),
                ),
              ],
            ),
            if (_especialidades.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _especialidades
                    .map((e) => Chip(
                          label: Text(e, style: const TextStyle(color: Colors.white, fontSize: 12)),
                          backgroundColor: const Color(0xFF0096FF).withValues(alpha: 0.2),
                          deleteIconColor: Colors.white54,
                          onDeleted: () => setState(() => _especialidades.remove(e)),
                        ))
                    .toList(),
              ),
            ],
            const SizedBox(height: 28),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: _loading ? null : _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF0096FF),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: _loading
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text(
                        'REGISTRAR TALLER',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                      ),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildField(
    TextEditingController ctrl,
    String label, {
    String? hint,
    bool numeric = false,
    bool obscure = false,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: ctrl,
      validator: validator,
      obscureText: obscure,
      keyboardType: numeric ? TextInputType.number : TextInputType.text,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.white54),
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white24),
        filled: true,
        fillColor: const Color(0xFF1A1F38),
        errorStyle: const TextStyle(color: Color(0xFFFF6B6B)),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFF0096FF)),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFFFF6B6B)),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFFFF6B6B)),
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: const TextStyle(
        color: Color(0xFF0096FF),
        fontSize: 13,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.5,
      ),
    );
  }
}

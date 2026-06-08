import 'dart:io';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:file_picker/file_picker.dart';
import 'package:uuid/uuid.dart';
import '../backend.dart';
import '../modules/offline/offline_queue.dart';
import '../modules/offline/sync_manager.dart';
import '../session.dart';
import '../modules/workshops/models/workshop_model.dart';
import '../modules/workshops/services/workshop_service.dart';
import '../modules/offline/connectivity_monitor.dart';
import 'dart:async';

class ReportIncidentScreen extends StatefulWidget {
  const ReportIncidentScreen({super.key});

  @override
  State<ReportIncidentScreen> createState() => _ReportIncidentScreenState();
}

class _ReportIncidentScreenState extends State<ReportIncidentScreen> {
  final _formKey = GlobalKey<FormState>();
  final _titleController = TextEditingController();
  final _descriptionController = TextEditingController();
  
  bool _loading = false;
  String? _error;
  
  // Hardware States
  Position? _currentPosition;
  List<File> _imageFiles = [];
  File? _audioFile;
  
  // Audio Recorder State
  late AudioRecorder _audioRecorder;
  bool _isRecording = false;

  String _tipoBusqueda = 'general';
  int? _tallerPreferidoId;
  List<Workshop> _favoritos = [];

  // Offline Monitoring
  final ConnectivityMonitor _connectivity = ConnectivityMonitor();
  StreamSubscription? _connectivitySub;
  bool _isOnline = true;

  @override
  void initState() {
    super.initState();
    _audioRecorder = AudioRecorder();
    _loadFavorites();
    
    // Iniciar monitoreo offline proactivo
    _connectivity.startMonitoring(interval: const Duration(seconds: 3));
    _connectivitySub = _connectivity.onConnectivityChanged.listen((isOnline) {
      if (mounted) {
        setState(() => _isOnline = isOnline);
      }
    });
  }

  Future<void> _loadFavorites() async {
    try {
      final favs = await WorkshopService.listMyFavorites();
      if (mounted) setState(() => _favoritos = favs);
    } catch (_) {}
  }

  @override
  void dispose() {
    _connectivitySub?.cancel();
    _connectivity.dispose();
    _audioRecorder.dispose();
    _titleController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _getGPS() async {
    bool serviceEnabled;
    LocationPermission permission;

    serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      _showError('Los servicios de ubicación están deshabilitados.');
      return;
    }

    permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        _showError('Permisos de ubicación denegados.');
        return;
      }
    }
    
    if (permission == LocationPermission.deniedForever) {
      _showError('Los permisos de ubicación están permanentemente denegados.');
      return;
    }

    setState(() => _loading = true);
    try {
      final position = await Geolocator.getCurrentPosition();
      setState(() => _currentPosition = position);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('📍 Ubicación GPS obtenida')),
      );
    } catch (e) {
      _showError('Error al obtener GPS: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _showImageSourceActionSheet() async {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF111629),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (context) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt, color: Color(0xFF00F2FF)),
              title: const Text('Tomar Foto', style: TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.pop(context);
                _takePhoto();
              },
            ),
            ListTile(
              leading: const Icon(Icons.photo_library, color: Color(0xFF00F2FF)),
              title: const Text('Elegir de Galería', style: TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.pop(context);
                _pickFromGallery();
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _takePhoto() async {
    final ImagePicker picker = ImagePicker();
    try {
      final XFile? image = await picker.pickImage(
        source: ImageSource.camera,
        imageQuality: 80,
      );
      if (image != null) {
        setState(() => _imageFiles.add(File(image.path)));
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('📸 Fotografía capturada')),
        );
      }
    } catch (e) {
      _showError('Error al abrir cámara: $e');
    }
  }

  Future<void> _pickFromGallery() async {
    final ImagePicker picker = ImagePicker();
    try {
      final List<XFile> images = await picker.pickMultiImage(
        imageQuality: 80,
      );
      if (images.isNotEmpty) {
        setState(() {
          _imageFiles.addAll(images.map((img) => File(img.path)));
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('📸 ${images.length} foto(s) seleccionada(s)')),
        );
      }
    } catch (e) {
      _showError('Error al abrir galería: $e');
    }
  }

  Future<void> _pickAudioFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.audio,
      );
      if (result != null && result.files.single.path != null) {
        setState(() {
          _audioFile = File(result.files.single.path!);
          _isRecording = false; 
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('🎵 Archivo de audio cargado')),
        );
      }
    } catch (e) {
      _showError('Error al seleccionar audio: $e');
    }
  }

  Future<void> _toggleRecording() async {
    try {
      if (await _audioRecorder.hasPermission()) {
        if (_isRecording) {
          final path = await _audioRecorder.stop();
          setState(() {
            _isRecording = false;
            if (path != null) _audioFile = File(path);
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('🎙️ Audio guardado para Whisper')),
          );
        } else {
          final dir = await getApplicationDocumentsDirectory();
          final path = '${dir.path}/audio_${DateTime.now().millisecondsSinceEpoch}.m4a';
          await _audioRecorder.start(
            const RecordConfig(encoder: AudioEncoder.aacLc),
            path: path,
          );
          setState(() => _isRecording = true);
        }
      } else {
        _showError('Permiso de micrófono denegado.');
      }
    } catch (e) {
      _showError('Error de grabación: $e');
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: Colors.redAccent),
    );
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_currentPosition == null) {
      setState(() => _error = "Debe obtener su ubicación GPS primero.");
      return;
    }
    if (_imageFiles.isEmpty) {
      setState(() => _error = "Se requiere al menos una fotografía para la IA Roboflow.");
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    if (!_isOnline) {
      await _saveToOfflineQueue();
      return;
    }

    try {
      final res = await Backend.reportIncident(
        title: _titleController.text,
        description: _descriptionController.text.isNotEmpty ? _descriptionController.text : null,
        lat: _currentPosition!.latitude,
        lng: _currentPosition!.longitude,
        address: "Ubicación detectada por GPS",
        images: _imageFiles.isEmpty ? null : _imageFiles,
        audio: _audioFile,
        tipoBusqueda: _tipoBusqueda,
        tallerPreferidoId: _tallerPreferidoId,
      );

      if (mounted) {
        setState(() => _loading = false);
        if (res == null) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('🚨 Incidente enviado. IA procesando...'),
              backgroundColor: Color(0xFF00E676),
            ),
          );
          Navigator.pop(context);
        } else {
          // If error is network related, fallback to offline
          if (res.toLowerCase().contains('socket') || res.toLowerCase().contains('timeout') || res.toLowerCase().contains('conexión')) {
            await _saveToOfflineQueue();
          } else {
            setState(() => _error = res);
          }
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _loading = false);
        await _saveToOfflineQueue();
      }
    }
  }

  Future<List<String>> _copyFilesToPersistentStorage(List<File> files) async {
    final dir = await getApplicationDocumentsDirectory();
    final persistentPaths = <String>[];
    for (var file in files) {
      final fileName = file.path.split('/').last;
      final newPath = '${dir.path}/${const Uuid().v4()}_$fileName';
      final newFile = await file.copy(newPath);
      persistentPaths.add(newFile.path);
    }
    return persistentPaths;
  }

  Future<void> _saveToOfflineQueue() async {
    List<String>? persistentImagePaths;
    if (_imageFiles.isNotEmpty) {
      persistentImagePaths = await _copyFilesToPersistentStorage(_imageFiles);
    }

    String? persistentAudioPath;
    if (_audioFile != null) {
      final res = await _copyFilesToPersistentStorage([_audioFile!]);
      if (res.isNotEmpty) persistentAudioPath = res.first;
    }

    final offlineItem = OfflineIncident(
      idempotencyKey: const Uuid().v4(),
      titulo: _titleController.text,
      descripcion: _descriptionController.text.isNotEmpty ? _descriptionController.text : null,
      latitud: _currentPosition!.latitude,
      longitud: _currentPosition!.longitude,
      direccion: "Guardado Offline (Sin conexión)",
      createdAtLocal: DateTime.now().toUtc().toIso8601String(),
      tipoBusqueda: _tipoBusqueda,
      tallerPreferidoId: _tallerPreferidoId,
      imagePaths: persistentImagePaths,
      audioPath: persistentAudioPath,
    );

    await OfflineQueue.enqueue(offlineItem);
    
    // Trigger auto-sync attempt
    final token = await Session.getToken();
    if (token != null) {
      SyncManager().startAutoSync(token);
    }

    if (mounted) {
      setState(() => _loading = false);
      await showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          backgroundColor: const Color(0xFF111629),
          title: const Text('Reporte Guardado', style: TextStyle(color: Colors.white)),
          content: const Text(
            'Incidente guardado localmente de forma segura. Se enviará automáticamente al recuperar conexión.',
            style: TextStyle(color: Colors.white70),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('OK', style: TextStyle(color: Color(0xFF00F2FF))),
            ),
          ],
        ),
      );
      if (mounted) {
        Navigator.pop(context);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        title: const Text('Reportar Emergencia'),
        backgroundColor: const Color(0xFF111629),
      ),
      body: Column(
        children: [
          if (!_isOnline)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
              color: Colors.deepOrangeAccent,
              child: const Row(
                children: [
                  Icon(Icons.wifi_off, color: Colors.white, size: 20),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Modo Offline Activo. Su reporte será guardado localmente y enviado al reconectar.',
                      style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: Form(
                key: _formKey,
                child: ListView(
                  children: [
              const Text(
                'Describa su emergencia vehicular',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
              ),
              const SizedBox(height: 8),
              const Text(
                'La IA analizará su foto y audio para asignar el mejor taller.',
                style: TextStyle(fontSize: 13, color: Colors.white54),
              ),
              const SizedBox(height: 24),

              // Botones de Hardware (GPS y Cámara)
              Row(
                children: [
                  Expanded(
                    child: _HardwareButton(
                      icon: Icons.gps_fixed,
                      label: _currentPosition != null ? 'GPS Listo' : 'Ubicación',
                      color: _currentPosition != null ? const Color(0xFF00E676) : const Color(0xFF00F2FF),
                      onTap: _getGPS,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _HardwareButton(
                      icon: _imageFiles.isNotEmpty ? Icons.photo_library : Icons.camera_alt,
                      label: _imageFiles.isNotEmpty ? '${_imageFiles.length} Fotos' : 'Fotos',
                      color: _imageFiles.isNotEmpty ? const Color(0xFF00E676) : const Color(0xFF00F2FF),
                      onTap: _showImageSourceActionSheet,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _HardwareButton(
                      icon: _isRecording ? Icons.stop : Icons.mic,
                      label: _isRecording ? 'Grabando...' : (_audioFile != null ? 'Audio Listo' : 'Voz / Archivo'),
                      color: _isRecording ? Colors.redAccent : (_audioFile != null ? const Color(0xFF00E676) : const Color(0xFF00F2FF)),
                      onTap: _toggleRecording,
                      onLongPress: _pickAudioFile,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              
              // Sección de Miniaturas (Thumbnails)
              if (_imageFiles.isNotEmpty || _audioFile != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFF111629),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white12),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Archivos Adjuntos:', style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 12),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            ..._imageFiles.map((file) => Padding(
                              padding: const EdgeInsets.only(right: 8.0),
                              child: Stack(
                                children: [
                                  ClipRRect(
                                    borderRadius: BorderRadius.circular(8),
                                    child: Image.file(file, width: 60, height: 60, fit: BoxFit.cover),
                                  ),
                                  Positioned(
                                    top: 0, right: 0,
                                    child: GestureDetector(
                                      onTap: () => setState(() => _imageFiles.remove(file)),
                                      child: Container(
                                        padding: const EdgeInsets.all(2),
                                        decoration: const BoxDecoration(color: Colors.redAccent, shape: BoxShape.circle),
                                        child: const Icon(Icons.close, size: 14, color: Colors.white),
                                      ),
                                    ),
                                  )
                                ],
                              ),
                            )),
                            if (_audioFile != null)
                              Container(
                                width: 60, height: 60,
                                decoration: BoxDecoration(
                                  color: const Color(0xFF00F2FF).withOpacity(0.2),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Stack(
                                  alignment: Alignment.center,
                                  children: [
                                    const Icon(Icons.audio_file, color: Color(0xFF00F2FF), size: 30),
                                    Positioned(
                                      top: 0, right: 0,
                                      child: GestureDetector(
                                        onTap: () => setState(() => _audioFile = null),
                                        child: Container(
                                          padding: const EdgeInsets.all(2),
                                          decoration: const BoxDecoration(color: Colors.redAccent, shape: BoxShape.circle),
                                          child: const Icon(Icons.close, size: 14, color: Colors.white),
                                        ),
                                      ),
                                    )
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 24),

              // Tipo de búsqueda y favoritos
              const Text('Tipo de Asignación', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                value: _tipoBusqueda,
                dropdownColor: const Color(0xFF111629),
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  filled: true,
                  fillColor: const Color(0xFF111629),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                ),
                items: const [
                  DropdownMenuItem(value: 'general', child: Text('General (Todos los talleres)')),
                  DropdownMenuItem(value: 'preferido', child: Text('Taller Preferencial (Mis favoritos)')),
                ],
                onChanged: (val) {
                  setState(() {
                    _tipoBusqueda = val ?? 'general';
                    if (_tipoBusqueda != 'preferido') {
                      _tallerPreferidoId = null;
                    }
                  });
                },
              ),
              if (_tipoBusqueda == 'preferido' && _favoritos.isNotEmpty) ...[
                const SizedBox(height: 12),
                DropdownButtonFormField<int>(
                  value: _tallerPreferidoId,
                  dropdownColor: const Color(0xFF111629),
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: 'Seleccione un taller favorito',
                    labelStyle: const TextStyle(color: Colors.white54),
                    filled: true,
                    fillColor: const Color(0xFF111629),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  items: _favoritos.map((w) {
                    return DropdownMenuItem<int>(
                      value: w.id,
                      child: Text(w.nombre),
                    );
                  }).toList(),
                  onChanged: (val) => setState(() => _tallerPreferidoId = val),
                  validator: (val) => _tipoBusqueda == 'preferido' && val == null ? 'Seleccione un taller' : null,
                ),
              ],
              if (_tipoBusqueda == 'preferido' && _favoritos.isEmpty)
                const Padding(
                  padding: EdgeInsets.only(top: 8.0),
                  child: Text('No tienes talleres favoritos registrados.', style: TextStyle(color: Colors.redAccent, fontSize: 12)),
                ),

              const SizedBox(height: 32),

              TextFormField(
                controller: _titleController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: 'Título del Problema',
                  labelStyle: const TextStyle(color: Colors.white54),
                  hintText: 'Ej: Motor sobrecalentado, Llanta pinchada',
                  hintStyle: const TextStyle(color: Colors.white24),
                  filled: true,
                  fillColor: const Color(0xFF111629),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                ),
                validator: (v) => v == null || v.isEmpty ? 'Requerido' : null,
              ),
              const SizedBox(height: 16),

              TextFormField(
                controller: _descriptionController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: 'Detalles adicionales (Opcional)',
                  labelStyle: const TextStyle(color: Colors.white54),
                  filled: true,
                  fillColor: const Color(0xFF111629),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                ),
                maxLines: 3,
              ),
              const SizedBox(height: 24),

              if (_error != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.redAccent.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.redAccent),
                  ),
                  child: Text(_error!, style: const TextStyle(color: Colors.redAccent)),
                ),
              const SizedBox(height: 16),

              ElevatedButton(
                onPressed: _loading || _isRecording ? null : _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _isOnline ? const Color(0xFFFF6B6B) : const Color(0xFF6B7280),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: _loading 
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                  : Text(_isOnline ? 'ENVIAR PARA ANÁLISIS IA' : 'GUARDAR REPORTE (OFFLINE)', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, letterSpacing: 1)),
              ),
            ],
          ),
        ),
      ),
    ),
        ],
      ),
    );
  }
}

class _HardwareButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;

  const _HardwareButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      onLongPress: onLongPress,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          border: Border.all(color: color.withOpacity(0.5)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 8),
            Text(label, textAlign: TextAlign.center, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 11)),
          ],
        ),
      ),
    );
  }
}

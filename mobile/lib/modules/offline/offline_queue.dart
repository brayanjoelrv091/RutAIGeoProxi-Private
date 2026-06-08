import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// P8 · CU-21 — Cola local de incidentes offline.
///
/// Almacena incidentes en SharedPreferences cuando no hay conexión.
/// Cada incidente lleva un idempotency_key (UUID) para deduplicación.
///
/// Estructura de cada item:
/// ```json
/// {
///   "idempotency_key": "uuid-v4",
///   "titulo": "Motor recalentado",
///   "descripcion": "El motor empezó a humear",
///   "latitud": -17.783,
///   "longitud": -63.182,
///   "direccion": "Av. Roca y Coronado",
///   "created_at_local": "2026-05-29T18:00:00Z",
///   "synced": false
/// }
/// ```

class OfflineIncident {
  final String idempotencyKey;
  final String titulo;
  final String? descripcion;
  final double latitud;
  final double longitud;
  final String? direccion;
  final String createdAtLocal;
  final String tipoBusqueda;
  final int? tallerPreferidoId;
  final List<String>? imagePaths;
  final String? audioPath;
  bool isSyncPending;
  bool hasSyncError;

  OfflineIncident({
    required this.idempotencyKey,
    required this.titulo,
    this.descripcion,
    required this.latitud,
    required this.longitud,
    this.direccion,
    required this.createdAtLocal,
    this.tipoBusqueda = 'general',
    this.tallerPreferidoId,
    this.imagePaths,
    this.audioPath,
    this.isSyncPending = true,
    this.hasSyncError = false,
  });

  Map<String, dynamic> toJson() => {
    'idempotency_key': idempotencyKey,
    'titulo': titulo,
    'descripcion': descripcion,
    'latitud': latitud,
    'longitud': longitud,
    'direccion': direccion,
    'created_at_local': createdAtLocal,
    'tipo_busqueda': tipoBusqueda,
    'taller_preferido_id': tallerPreferidoId,
    'image_paths': imagePaths,
    'audio_path': audioPath,
    'is_sync_pending': isSyncPending,
    'has_sync_error': hasSyncError,
  };

  factory OfflineIncident.fromJson(Map<String, dynamic> json) => OfflineIncident(
    idempotencyKey: json['idempotency_key'],
    titulo: json['titulo'],
    descripcion: json['descripcion'],
    latitud: (json['latitud'] as num).toDouble(),
    longitud: (json['longitud'] as num).toDouble(),
    direccion: json['direccion'],
    createdAtLocal: json['created_at_local'],
    tipoBusqueda: json['tipo_busqueda'] ?? 'general',
    tallerPreferidoId: json['taller_preferido_id'],
    imagePaths: (json['image_paths'] as List<dynamic>?)?.map((e) => e as String).toList(),
    audioPath: json['audio_path'],
    isSyncPending: json['is_sync_pending'] ?? true, // Por defecto al cargar, asumimos true si no está
    hasSyncError: json['has_sync_error'] ?? false,
  );
}


class OfflineQueue {
  static const _key = 'offline_incidents_queue';

  /// Agrega un incidente a la cola offline.
  static Future<void> enqueue(OfflineIncident incident) async {
    final prefs = await SharedPreferences.getInstance();
    final queue = await getQueue();
    queue.add(incident);
    await _save(prefs, queue);
  }

  /// Obtiene todos los incidentes en la cola.
  static Future<List<OfflineIncident>> getQueue() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null || raw.isEmpty) return [];

    final List<dynamic> decoded = jsonDecode(raw);
    return decoded.map((e) => OfflineIncident.fromJson(e)).toList();
  }

  /// Obtiene solo los incidentes pendientes de sincronización (ignorando los que tienen errores de conflicto).
  static Future<List<OfflineIncident>> getPending() async {
    final queue = await getQueue();
    return queue.where((item) => item.isSyncPending && !item.hasSyncError).toList();
  }

  /// Marca un incidente como sincronizado por su idempotency_key.
  static Future<void> markSynced(String idempotencyKey) async {
    final prefs = await SharedPreferences.getInstance();
    final queue = await getQueue();

    for (final item in queue) {
      if (item.idempotencyKey == idempotencyKey) {
        item.isSyncPending = false;
      }
    }

    await _save(prefs, queue);
  }

  /// Marca un incidente con error de conflicto (ej. hash corrupto).
  static Future<void> markError(String idempotencyKey) async {
    final prefs = await SharedPreferences.getInstance();
    final queue = await getQueue();

    for (final item in queue) {
      if (item.idempotencyKey == idempotencyKey) {
        item.hasSyncError = true;
      }
    }

    await _save(prefs, queue);
  }

  /// Elimina todos los incidentes ya sincronizados.
  static Future<void> clearSynced() async {
    final prefs = await SharedPreferences.getInstance();
    final queue = await getQueue();
    final pending = queue.where((item) => item.isSyncPending).toList();
    await _save(prefs, pending);
  }

  /// Verifica si hay incidentes pendientes.
  static Future<bool> hasPending() async {
    final pending = await getPending();
    return pending.isNotEmpty;
  }

  /// Cuenta total de pendientes.
  static Future<int> pendingCount() async {
    final pending = await getPending();
    return pending.length;
  }

  /// Limpia toda la cola.
  static Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }

  static Future<void> _save(SharedPreferences prefs, List<OfflineIncident> queue) async {
    final json = jsonEncode(queue.map((e) => e.toJson()).toList());
    await prefs.setString(_key, json);
  }
}

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'offline_queue.dart';
import 'connectivity_monitor.dart';
import '../../config.dart';
import '../../backend.dart';

/// P8 · CU-22 — Sincronización automática de incidentes offline.
///
/// Flujo:
///   1. ConnectivityMonitor detecta que la conexión volvió
///   2. SyncManager obtiene la cola de pendientes
///   3. Envía batch al endpoint /realtime/incidents/offline-sync
///   4. Marca como sincronizados los exitosos
///   5. Notifica al UI del resultado
///
/// Deduplicación (CU-23):
///   El backend rechaza duplicados por idempotency_key con status 'duplicate'
///   sin generar error. El item se marca como synced igualmente.

typedef SyncCallback = void Function(SyncResult result);

class SyncResult {
  final int total;
  final int created;
  final int duplicates;
  final int errors;
  final List<SyncItemResult> items;

  SyncResult({
    required this.total,
    required this.created,
    required this.duplicates,
    required this.errors,
    required this.items,
  });

  factory SyncResult.fromJson(Map<String, dynamic> json) => SyncResult(
    total: json['total'] ?? 0,
    created: json['created'] ?? 0,
    duplicates: json['duplicates'] ?? 0,
    errors: json['errors'] ?? 0,
    items: (json['results'] as List<dynamic>?)
        ?.map((e) => SyncItemResult.fromJson(e))
        .toList() ?? [],
  );

  factory SyncResult.empty() => SyncResult(
    total: 0, created: 0, duplicates: 0, errors: 0, items: [],
  );

  bool get hasErrors => errors > 0;
  bool get allSucceeded => errors == 0 && total > 0;
}

class SyncItemResult {
  final String idempotencyKey;
  final String status; // created | duplicate | error
  final int? incidentId;
  final String message;

  SyncItemResult({
    required this.idempotencyKey,
    required this.status,
    this.incidentId,
    required this.message,
  });

  factory SyncItemResult.fromJson(Map<String, dynamic> json) => SyncItemResult(
    idempotencyKey: json['idempotency_key'],
    status: json['status'],
    incidentId: json['incident_id'],
    message: json['message'],
  );
}


class SyncManager {
  static final SyncManager _instance = SyncManager._internal();
  factory SyncManager() => _instance;

  final ConnectivityMonitor _connectivity;
  StreamSubscription? _connectivitySub;
  bool _isSyncing = false;
  SyncCallback? onSyncComplete;

  final _notificationsController = StreamController<String>.broadcast();
  Stream<String> get notifications => _notificationsController.stream;

  SyncManager._internal() : _connectivity = ConnectivityMonitor();

  /// Inicia el listener de conectividad para auto-sync.
  void startAutoSync(String token) {
    _connectivitySub?.cancel();
    _connectivitySub = _connectivity.onConnectivityChanged.listen((isOnline) {
      if (isOnline && !_isSyncing) {
        syncNow(token);
      }
    });
    if (_connectivity.isOnline && !_isSyncing) {
      syncNow(token);
    }
  }

  /// Detiene el auto-sync.
  void stopAutoSync() {
    _connectivitySub?.cancel();
    _connectivitySub = null;
  }

  /// Sincroniza manualmente la cola de pendientes.
  Future<SyncResult> syncNow(String token) async {
    if (_isSyncing) return SyncResult.empty();

    final pending = await OfflineQueue.getPending();
    if (pending.isEmpty) return SyncResult.empty();

    _isSyncing = true;

    try {
      final results = <SyncItemResult>[];
      int created = 0;
      int errors = 0;
      bool abort = false;

      for (final item in pending) {
        if (!_connectivity.isOnline) {
          print('[SyncManager] Red desconectada, abortando sincronización.');
          abort = true;
          break;
        }

        bool success = false;
        String? lastError;

        for (int attempt = 1; attempt <= 3; attempt++) {
          if (!_connectivity.isOnline) {
            abort = true;
            break;
          }

          try {
            final error = await Backend.reportIncident(
              title: item.titulo,
              description: item.descripcion,
              lat: item.latitud,
              lng: item.longitud,
              address: item.direccion,
              tipoBusqueda: item.tipoBusqueda,
              tallerPreferidoId: item.tallerPreferidoId,
              syncHash: item.idempotencyKey,
              localTimestamp: item.createdAtLocal,
              images: item.imagePaths?.map((p) => File(p)).toList(),
              audio: item.audioPath != null ? File(item.audioPath!) : null,
            );

            if (error == null) {
              await OfflineQueue.markSynced(item.idempotencyKey);
              created++;
              success = true;
              results.add(SyncItemResult(
                idempotencyKey: item.idempotencyKey,
                status: 'created',
                message: 'Sincronizado correctamente',
              ));
              break; // Éxito, salir de los reintentos
            } else {
              lastError = error;
              print('[SyncManager] Error subiendo ${item.idempotencyKey} (Intento $attempt): $error');
              if (error.contains('Hash corrupto')) {
                await OfflineQueue.markError(item.idempotencyKey);
                _notificationsController.add('Conflicto: Incidente corrupto o duplicado. Reporte marcado con error.');
                break; // No reintentar si el hash/timestamp es inválido
              }
            }
          } catch (e) {
            lastError = e.toString();
            print('[SyncManager] Excepción subiendo ${item.idempotencyKey} (Intento $attempt): $e');
          }

          if (attempt < 3 && !abort) {
            await Future.delayed(Duration(seconds: 2 * attempt)); // Exponential backoff: 2s, 4s
          }
        }

        if (abort) break;

        if (!success) {
          errors++;
          results.add(SyncItemResult(
            idempotencyKey: item.idempotencyKey,
            status: 'error',
            message: lastError ?? 'Error desconocido',
          ));
        }
      }

      await OfflineQueue.clearSynced();

      final result = SyncResult(
        total: pending.length,
        created: created,
        duplicates: 0,
        errors: errors,
        items: results,
      );

      if (abort) {
        _notificationsController.add('Sincronización pausada por caída de red.');
      } else if (errors == 0 && created > 0) {
        _notificationsController.add('Tus incidentes pendientes han sido sincronizados con éxito');
      } else if (errors > 0 && created == 0) {
        _notificationsController.add('No se pudo sincronizar tu reporte pendiente. Se intentará más tarde');
      }

      onSyncComplete?.call(result);
      return result;
    } catch (e) {
      print('[SyncManager] Error crítico de sincronización: $e');
      return SyncResult.empty();
    } finally {
      _isSyncing = false;
    }
  }

  void dispose() {
    stopAutoSync();
  }
}

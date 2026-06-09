/// Servicio de Talleres Flutter (P3 — CU10-CU13).
library;

import '../../../core/api_client.dart';
import '../models/workshop_model.dart';

class WorkshopService {
  // ── CU10 — Listar talleres ────────────────────────────────────────

  static Future<List<Workshop>> listAllWorkshops() async {
    return ApiClient.get<List<Workshop>>(
      '/workshops/all',
      fromJson: (j) => (j as List<dynamic>)
          .map((e) => Workshop.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  static Future<List<Workshop>> listMyWorkshops() async {
    return ApiClient.get<List<Workshop>>(
      '/workshops',
      fromJson: (j) => (j as List<dynamic>)
          .map((e) => Workshop.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  // ── CU FAVORITOS ───────────────────────────────────────────────

  static Future<void> addFavorite(int workshopId) async {
    await ApiClient.post<dynamic>(
      '/workshops/$workshopId/favorite',
      fromJson: (j) => j,
    );
  }

  static Future<void> removeFavorite(int workshopId) async {
    await ApiClient.delete<dynamic>(
      '/workshops/$workshopId/favorite',
      fromJson: (j) => j,
    );
  }

  static Future<List<Workshop>> listMyFavorites() async {
    return ApiClient.get<List<Workshop>>(
      '/workshops/me/favorite-workshops',
      fromJson: (j) => (j as List<dynamic>)
          .map((e) => Workshop.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  static Future<Workshop> registerWorkshop({
    required String nombre,
    required String direccion,
    required double latitud,
    required double longitud,
    String? telefono,
    String? email,
    required String password,
    List<String>? especialidades,
  }) async {
    return ApiClient.post<Workshop>(
      '/workshops',
      body: {
        'nombre': nombre,
        'direccion': direccion,
        'latitud': latitud,
        'longitud': longitud,
        'password': password,
        ...?telefono == null ? null : {'telefono': telefono},
        ...?email == null ? null : {'email': email},
        ...?especialidades == null ? null : {'especialidades': especialidades},
      },
      fromJson: (j) => Workshop.fromJson(j as Map<String, dynamic>),
    );
  }

  // ── ESTADO ONLINE Y TÉCNICOS ──────────────────────────────────────

  static Future<bool> getOnlineStatus(int workshopId) async {
    final res = await ApiClient.get<Map<String, dynamic>>(
      '/workshops/$workshopId/online-status',
      fromJson: (j) => j as Map<String, dynamic>,
    );
    return res['en_linea'] as bool? ?? false;
  }

  static Future<List<Technician>> listTechnicians(int workshopId) async {
    return ApiClient.get<List<Technician>>(
      '/workshops/$workshopId/technicians',
      fromJson: (j) => (j as List<dynamic>)
          .map((e) => Technician.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  // ── CU11 — Listar solicitudes ─────────────────────────────────────

  static Future<List<ServiceRequest>> listPendingRequests(int workshopId) async {
    return ApiClient.get<List<ServiceRequest>>(
      '/workshops/$workshopId/requests',
      fromJson: (j) => (j as List<dynamic>)
          .map((e) => ServiceRequest.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  // ── CU12 — Actualizar estado ──────────────────────────────────────

  static Future<ServiceRequest> updateStatus(
    int requestId,
    String estado, {
    String? notas,
    int? tecnicoId,
  }) async {
    return ApiClient.patch<ServiceRequest>(
      '/workshops/requests/$requestId/status',
      body: {
        'estado': estado,
        ...?notas == null ? null : {'notas': notas},
        ...?tecnicoId == null ? null : {'tecnico_id': tecnicoId},
      },
      fromJson: (j) => ServiceRequest.fromJson(j as Map<String, dynamic>),
    );
  }

  // ── CU13 — Historial de atenciones ───────────────────────────────

  static Future<List<ServiceHistory>> getHistory(int workshopId) async {
    return ApiClient.get<List<ServiceHistory>>(
      '/workshops/$workshopId/history',
      fromJson: (j) => (j as List<dynamic>)
          .map((e) => ServiceHistory.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

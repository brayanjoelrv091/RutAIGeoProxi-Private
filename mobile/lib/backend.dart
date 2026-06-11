import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'config.dart';
import 'session.dart';

class Backend {
  static Uri _uri(String path) => Uri.parse('${AppConfig.baseUrl}$path');

  static Future<Map<String, String>> _headers({
    bool jsonBody = false,
    bool withAuth = true,
  }) async {
    final headers = <String, String>{};
    if (jsonBody) headers['Content-Type'] = 'application/json';
    if (withAuth) {
      final token = await Session.getToken();
      if (token != null) headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  static Future<String?> login(String email, String password) async {
    try {
      final response = await http.post(
        _uri('/auth/login'),
        headers: await _headers(jsonBody: true, withAuth: false),
        body: jsonEncode({'email': email, 'password': password}),
      ).timeout(const Duration(seconds: 60));
      if (response.statusCode != 200) return response.body;
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final token = data['access_token'] as String?;
      if (token != null) await Session.setToken(token);
      return null;
    } catch (e) {
      return 'Error de conexión. Revisa tu internet o intenta de nuevo (el servidor puede estar despertando).';
    }
  }

  static Future<String?> register(
    String name,
    String email,
    String password,
  ) async {
    try {
      final response = await http.post(
        _uri('/auth/register'),
        headers: await _headers(jsonBody: true, withAuth: false),
        body: jsonEncode({
          'nombre': name,
          'email': email,
          'password': password,
          'rol': 'cliente',
        }),
      ).timeout(const Duration(seconds: 60));
      if (response.statusCode == 201) return null;
      try {
        final error = jsonDecode(response.body);
        if (error is Map && error['detail'] != null) {
          return error['detail'].toString();
        }
      } catch (_) {}
      return 'Error ${response.statusCode}';
    } catch (e) {
      return 'Error de conexión. Revisa tu internet o intenta de nuevo.';
    }
  }

  static Future<void> logout() async {
    final token = await Session.getToken();
    if (token == null) return;
    await http.post(_uri('/auth/logout'), headers: await _headers());
    await Session.setToken(null);
  }

  static Future<Map<String, dynamic>?> me() async {
    final response = await http.get(_uri('/me'), headers: await _headers());
    if (response.statusCode != 200) return null;

    final raw = jsonDecode(response.body) as Map<String, dynamic>;
    final vehiculos = (raw['vehiculos'] as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(
          (vehicle) => <String, dynamic>{
            ...vehicle,
            'brand': vehicle['marca'],
            'model': vehicle['modelo'],
            'license_plate': vehicle['placa'],
          },
        )
        .toList();

    return {
      ...raw,
      'name': raw['nombre'],
      'role': raw['rol'],
      'vehicles': vehiculos,
    };
  }

  static Future<String?> addVehicle({
    required String brand,
    required String model,
    required String licensePlate,
    int? year,
  }) async {
    final body = <String, dynamic>{
      'marca': brand,
      'modelo': model,
      'placa': licensePlate,
    };
    if (year != null) body['anio'] = year;

    final response = await http.post(
      _uri('/me/vehicles'),
      headers: await _headers(jsonBody: true),
      body: jsonEncode(body),
    );
    if (response.statusCode == 201) return null;
    try {
      final error = jsonDecode(response.body);
      if (error is Map && error['detail'] != null) {
        return error['detail'].toString();
      }
    } catch (_) {}
    return 'Error ${response.statusCode}';
  }

  static Future<void> deleteVehicle(int id) async {
    await http.delete(_uri('/me/vehicles/$id'), headers: await _headers());
  }

  static Future<String?> forgotPassword(String email) async {
    final response = await http.post(
      _uri('/auth/forgot-password'),
      headers: await _headers(jsonBody: true, withAuth: false),
      body: jsonEncode({'email': email}),
    );
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return data['debug_token']?.toString() ?? 'OK';
    }
    try {
      final error = jsonDecode(response.body);
      if (error is Map && error['detail'] != null) {
        return error['detail'].toString();
      }
    } catch (_) {}
    return 'Error ${response.statusCode}';
  }

  static Future<String?> resetPassword(
    String token,
    String newPassword,
  ) async {
    final response = await http.post(
      _uri('/auth/reset-password'),
      headers: await _headers(jsonBody: true, withAuth: false),
      body: jsonEncode({'token': token, 'new_password': newPassword}),
    );
    if (response.statusCode == 204) return null;
    try {
      final error = jsonDecode(response.body);
      if (error is Map && error['detail'] != null) {
        return error['detail'].toString();
      }
    } catch (_) {}
    return 'Error ${response.statusCode}';
  }

  static Future<String?> reportIncident({
    required String title,
    String? description,
    required double lat,
    required double lng,
    String? address,
    List<File>? images,
    File? audio,
    String tipoBusqueda = 'general',
    int? tallerPreferidoId,
    String? syncHash,
    String? localTimestamp,
  }) async {
    final request = http.MultipartRequest('POST', _uri('/incidents'));
    request.headers.addAll(await _headers(withAuth: true));

    request.fields['titulo'] = title;
    request.fields['latitud'] = lat.toString();
    request.fields['longitud'] = lng.toString();
    request.fields['tipo_busqueda'] = tipoBusqueda;
    if (tallerPreferidoId != null) {
      request.fields['taller_preferido_id'] = tallerPreferidoId.toString();
    }
    if (syncHash != null) {
      request.fields['sync_hash'] = syncHash;
    }
    if (localTimestamp != null) {
      request.fields['local_timestamp'] = localTimestamp;
    }
    if (description != null && description.isNotEmpty) {
      request.fields['descripcion'] = description;
    }
    if (address != null && address.isNotEmpty) {
      request.fields['direccion'] = address;
    }

    if (images != null) {
      for (var img in images) {
        request.files.add(
          await http.MultipartFile.fromPath(
            'fotos',
            img.path,
            contentType: MediaType('image', 'jpeg'),
          ),
        );
      }
    }
    if (audio != null) {
      request.files.add(
        await http.MultipartFile.fromPath(
          'audio',
          audio.path,
          contentType: MediaType('audio', 'm4a'), // o el formato que grabe el plugin
        ),
      );
    }

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 201 || response.statusCode == 200) return null;
    try {
      final error = jsonDecode(response.body);
      final detail = error['detail'];
      if (detail is List) {
        final messages = detail.map((err) {
          if (err is Map) {
            final msg = err['msg']?.toString();
            final loc = err['loc'] as List?;
            final fieldName = loc != null && loc.isNotEmpty ? loc.last.toString() : '';
            if (msg != null) {
              if (fieldName.isNotEmpty) {
                return 'Campo "$fieldName": $msg';
              }
              return msg;
            }
          }
          return err.toString();
        }).join('\n');
        return messages;
      }
      final detailStr = detail?.toString();
      if (response.statusCode == 400 && detailStr != null && detailStr.contains('Hash corrupto')) {
        return detailStr;
      }
      return detailStr ?? 'Error ${response.statusCode}';
    } catch (_) {}
    return 'Error ${response.statusCode}';
  }

  static Future<void> updateFcmToken(String fcmToken) async {
    try {
      await http.patch(
        _uri('/me/fcm-token'),
        headers: await _headers(jsonBody: true),
        body: jsonEncode({'fcm_token': fcmToken}),
      );
    } catch (_) {
      // Silenciar errores de token
    }
  }

  static Future<String?> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final response = await http.patch(
      _uri('/me/password'),
      headers: await _headers(jsonBody: true),
      body: jsonEncode({
        'current_password': currentPassword,
        'new_password': newPassword,
      }),
    );
    if (response.statusCode == 200) return null;
    try {
      final data = jsonDecode(response.body);
      return data['detail']?.toString() ?? 'Error al cambiar contraseña';
    } catch (_) {}
    return 'Error ${response.statusCode}';
  }

  static Future<Map<String, dynamic>?> getTenantDashboard() async {
    try {
      final response = await http.get(_uri('/tenants/me/dashboard'), headers: await _headers());
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<List<dynamic>> getTenantWorkshops() async {
    try {
      final response = await http.get(_uri('/tenants/me/workshops'), headers: await _headers());
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  static Future<List<dynamic>> getTenantMembers() async {
    try {
      final response = await http.get(_uri('/tenants/me/members'), headers: await _headers());
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return [];
  }

  // --- Incidentes ---
  static Future<List<dynamic>?> getMyIncidents() async {
    try {
      final response = await http.get(_uri('/incidents'), headers: await _headers());
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as List<dynamic>;
      }
    } catch (_) {}
    return null;
  }

  // --- Tracking y Llegada ---

  static Future<Map<String, dynamic>?> getIncidentTracking(int incidentId) async {
    try {
      final response = await http.get(_uri('/incidents/$incidentId/tracking'), headers: await _headers());
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<bool> reportArrival(int incidentId) async {
    try {
      final response = await http.post(_uri('/incidents/$incidentId/llegada-taller'), headers: await _headers());
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<bool> updateLocation(double lat, double lng) async {
    try {
      final response = await http.post(
        _uri('/workshops/me/location'),
        headers: await _headers(jsonBody: true),
        body: jsonEncode({'latitud': lat, 'longitud': lng}),
      );
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  // --- Pagos (Efectivo y QR) ---

  static Future<bool> requestCashPayment(int incidentId) async {
    try {
      final response = await http.post(_uri('/payments/cash/$incidentId'), headers: await _headers());
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<bool> confirmCashPayment(int incidentId) async {
    try {
      final response = await http.post(_uri('/payments/confirm-cash/$incidentId'), headers: await _headers());
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }

  static Future<Map<String, dynamic>?> requestQrPayment(int incidentId) async {
    try {
      final response = await http.post(_uri('/payments/qr/$incidentId'), headers: await _headers());
      if (response.statusCode == 200) return jsonDecode(response.body);
    } catch (_) {}
    return null;
  }

  static Future<bool> confirmQrPayment(int incidentId) async {
    try {
      final response = await http.post(_uri('/payments/confirm-qr/$incidentId'), headers: await _headers());
      return response.statusCode == 200;
    } catch (_) {}
    return false;
  }
}

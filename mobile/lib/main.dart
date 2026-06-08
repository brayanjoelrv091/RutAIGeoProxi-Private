/// main.dart — Entry point del monolito modular RutAIGeoProxi Mobile.
///
/// Rutas:
///   /              → Splash / Auth gate
///   /login         → Pantalla de login (CU1)
///   /register      → Registro (CU3)
///   /forgot-password → Recuperar contraseña (CU4)
///   /home          → Dashboard principal
///   /vehicles      → Mis vehículos (CU6)
///   /incidents     → Mis incidentes (CU7 lista)
///   /report        → Reportar incidente (CU7)
///   /incident-detail → Ficha técnica (CU9)
///   /workshops     → Talleres (CU10-CU13)
///   /tracking      → Tracking en tiempo real (CU15)
///   /notifications → Centro de notificaciones (CU16/CU17)
///   /payment       → Pasarela de pago (CU18)
library;

import 'dart:convert';
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'backend.dart';
import 'core/api_client.dart';
import 'modules/auth/services/auth_service.dart';
import 'modules/auth/screens/login_screen.dart';
import 'modules/auth/screens/register_screen.dart';
import 'modules/auth/screens/forgot_password_screen.dart';
import 'modules/incidents/screens/incident_detail_screen.dart';
import 'modules/incidents/screens/my_incidents_screen.dart';
import 'modules/notifications/screens/notifications_screen.dart';
import 'modules/notifications/services/notification_service.dart';
import 'modules/payments/screens/payment_screen.dart';
import 'modules/tracking/screens/tracking_screen.dart';
import 'modules/vehicles/screens/my_vehicles_screen.dart';
import 'modules/workshops/screens/workshop_list_screen.dart';
import 'modules/auth/screens/profile_screen.dart';
import 'screens/report_incident_screen.dart';
import 'modules/offline/sync_manager.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  
  FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);
  
  runApp(const RutAIGeoProxiApp());
}

final GlobalKey<ScaffoldMessengerState> rootScaffoldMessengerKey = GlobalKey<ScaffoldMessengerState>();

class RutAIGeoProxiApp extends StatefulWidget {
  const RutAIGeoProxiApp({super.key});

  @override
  State<RutAIGeoProxiApp> createState() => _RutAIGeoProxiAppState();
}

class _RutAIGeoProxiAppState extends State<RutAIGeoProxiApp> {
  StreamSubscription? _syncSub;

  @override
  void initState() {
    super.initState();
    _syncSub = SyncManager().notifications.listen((message) {
      rootScaffoldMessengerKey.currentState?.showSnackBar(
        SnackBar(
          content: Text(message, style: const TextStyle(fontWeight: FontWeight.bold)),
          backgroundColor: message.contains('éxito') ? const Color(0xFF00E676) : const Color(0xFFFF6B6B),
          behavior: SnackBarBehavior.floating,
          margin: const EdgeInsets.only(top: 50, left: 20, right: 20),
          duration: const Duration(seconds: 4),
          dismissDirection: DismissDirection.up,
        ),
      );
    });
  }

  @override
  void dispose() {
    _syncSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      scaffoldMessengerKey: rootScaffoldMessengerKey,
      title: 'RutAIGeoProxi',
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(),
      home: const _AuthGate(),
      routes: {
        '/login': (_) => const _LoginWrapper(),
        '/register': (_) => const RegisterScreen(),
        '/forgot-password': (_) => const ForgotPasswordScreen(),
        '/home': (_) => const _HomeWrapper(),
        '/vehicles': (_) => const MyVehiclesScreen(),
        '/incidents': (_) => const MyIncidentsScreen(),
        '/report': (_) => const ReportIncidentScreen(),
        '/incident-detail': (_) => const IncidentDetailScreen(),
        '/workshops': (_) => const WorkshopListScreen(),
        '/notifications': (_) => const NotificationsScreen(),
        '/profile': (_) => const ProfileScreen(),
      },
      // Rutas con parámetros (onGenerateRoute)
      onGenerateRoute: (settings) {
        if (settings.name == '/tracking') {
          final args = settings.arguments as Map<String, dynamic>?;
          return MaterialPageRoute(
            builder: (_) => TrackingScreen(
              incidentId: args?['incidentId'] as int? ?? 0,
              role: args?['role'] as String? ?? 'cliente',
            ),
          );
        }
        if (settings.name == '/payment') {
          final args = settings.arguments as Map<String, dynamic>?;
          return MaterialPageRoute(
            builder: (_) => PaymentScreen(
              incidentId: args?['incidentId'] as int? ?? 0,
              amount: (args?['amount'] as num?)?.toDouble() ?? 0.0,
            ),
          );
        }
        return null;
      },
    );
  }

  ThemeData _buildTheme() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.dark(
        primary: const Color(0xFF00F2FF),
        secondary: const Color(0xFF0096FF),
        surface: const Color(0xFF111629),
        error: const Color(0xFFFF6B6B),
      ),
      scaffoldBackgroundColor: const Color(0xFF0A0E1A),
      fontFamily: 'Roboto',
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF111629),
        foregroundColor: Color(0xFF00F2FF),
        elevation: 0,
        titleTextStyle: TextStyle(
          color: Color(0xFF00F2FF),
          fontSize: 18,
          letterSpacing: 1,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF00F2FF),
          foregroundColor: Colors.black,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: const Color(0xFF111629),
        selectedColor: const Color(0xFF00F2FF),
        labelStyle: const TextStyle(color: Colors.white),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    );
  }
}

// ── Auth Gate ──────────────────────────────────────────────────────────

class _AuthGate extends StatefulWidget {
  const _AuthGate();

  @override
  State<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<_AuthGate> {
  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check() async {
    await Future.delayed(const Duration(milliseconds: 300));
    if (!mounted) return;
    final token = await ApiClient.getToken();
    if (!mounted) return;
    if (token != null && token.isNotEmpty) {
      Navigator.pushReplacementNamed(context, '/home');
    } else {
      Navigator.pushReplacementNamed(context, '/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Color(0xFF0A0E1A),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.car_repair, size: 64, color: Color(0xFF00F2FF)),
            SizedBox(height: 16),
            Text(
              'RutAIGeoProxi',
              style: TextStyle(
                color: Color(0xFF00F2FF),
                fontSize: 24,
                fontWeight: FontWeight.bold,
                letterSpacing: 3,
              ),
            ),
            SizedBox(height: 24),
            CircularProgressIndicator(color: Color(0xFF00F2FF)),
          ],
        ),
      ),
    );
  }
}

// ── Wrappers ───────────────────────────────────────────────────────────

class _LoginWrapper extends StatelessWidget {
  const _LoginWrapper();

  @override
  Widget build(BuildContext context) {
    return LoginScreen(
      onLoginSuccess: () =>
          Navigator.pushReplacementNamed(context, '/home'),
    );
  }
}

// ── Home Dashboard ─────────────────────────────────────────────────────

class _HomeWrapper extends StatefulWidget {
  const _HomeWrapper();

  @override
  State<_HomeWrapper> createState() => _HomeWrapperState();
}

class _HomeWrapperState extends State<_HomeWrapper> {
  int _notifCount = 0;

  @override
  void initState() {
    super.initState();
    _initNotifications();
  }

  Future<void> _initNotifications() async {
    // Conectar notificaciones WS al cargar el home
    try {
      final token = await ApiClient.getToken();
      if (token == null) return;

      // ── Configuración FCM (Push Real) ──
      final messaging = FirebaseMessaging.instance;
      
      // Solicitar permiso (iOS y Android 13+)
      NotificationSettings settings = await messaging.requestPermission(
        alert: true, badge: true, sound: true,
      );

      if (settings.authorizationStatus == AuthorizationStatus.authorized) {
        final fcmToken = await messaging.getToken();
        if (fcmToken != null) {
          // Guardar token en el backend
          await Backend.updateFcmToken(fcmToken);
        }
      }

      // Escuchar mensajes en primer plano (Foreground)
      FirebaseMessaging.onMessage.listen((RemoteMessage message) {
        if (message.notification != null && mounted) {
          _showBanner(message.notification!.title ?? 'Notificación', message.notification!.body ?? '');
        }
      });

      // Decodificar user_id del JWT payload (base64url → JSON)
      final parts = token.split('.');
      if (parts.length != 3) return;

      // Normalizar padding base64url
      var b64 = parts[1].replaceAll('-', '+').replaceAll('_', '/');
      while (b64.length % 4 != 0) b64 += '=';

      final payloadStr = utf8.decode(base64Decode(b64));
      final payload = jsonDecode(payloadStr) as Map<String, dynamic>;
      final userId = int.tryParse(payload['sub']?.toString() ?? '');
      if (userId == null) return;

      NotificationService.instance.connect(userId, token);
      NotificationService.instance.notifications.listen((notif) {
        if (mounted) {
          setState(() => _notifCount++);
          _showBanner(notif.titulo, notif.mensaje);
        }
      });
    } catch (_) {
      // Silenciar errores — las notificaciones son opcionales en home
    }
  }

  void _showBanner(String title, String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            if (msg.isNotEmpty) Text(msg, style: const TextStyle(fontSize: 14)),
          ],
        ),
        backgroundColor: const Color(0xFF00F2FF), // Cyan
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.only(top: 50, left: 20, right: 20),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        duration: const Duration(seconds: 5),
        dismissDirection: DismissDirection.up,
      ),
    );
  }

  Future<void> _logout() async {
    NotificationService.instance.disconnect();
    await AuthService.logout();
    if (mounted) Navigator.pushReplacementNamed(context, '/login');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111629),
        title: const Text(
          'RutAIGeoProxi',
          style: TextStyle(
            color: Color(0xFF00F2FF),
            fontWeight: FontWeight.bold,
            letterSpacing: 2,
          ),
        ),
        actions: [
          // Campana de notificaciones con badge
          Stack(
            children: [
              IconButton(
                icon: const Icon(Icons.notifications_outlined, color: Color(0xFF00F2FF)),
                onPressed: () {
                  setState(() => _notifCount = 0);
                  Navigator.pushNamed(context, '/notifications');
                },
              ),
              if (_notifCount > 0)
                Positioned(
                  right: 6,
                  top: 6,
                  child: Container(
                    padding: const EdgeInsets.all(3),
                    decoration: const BoxDecoration(
                      color: Color(0xFFFF6B6B),
                      shape: BoxShape.circle,
                    ),
                    constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                    child: Text(
                      '$_notifCount',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
            ],
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.person, color: Color(0xFF00F2FF)),
            color: const Color(0xFF111629),
            onSelected: (value) {
              if (value == 'profile') Navigator.pushNamed(context, '/profile');
              else if (value == 'incidents') Navigator.pushNamed(context, '/incidents');
              else if (value == 'vehicles') Navigator.pushNamed(context, '/vehicles');
              else if (value == 'payment') Navigator.pushNamed(context, '/payment', arguments: {'incidentId': 4, 'amount': 45000.0});
            },
            itemBuilder: (BuildContext context) => <PopupMenuEntry<String>>[
              const PopupMenuItem<String>(
                value: 'profile',
                child: ListTile(
                  leading: Icon(Icons.person_outline, color: Color(0xFF00F2FF)),
                  title: Text('Ver mi Perfil', style: TextStyle(color: Colors.white)),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const PopupMenuItem<String>(
                value: 'incidents',
                child: ListTile(
                  leading: Icon(Icons.warning_amber_rounded, color: Color(0xFF00F2FF)),
                  title: Text('Mis Incidentes', style: TextStyle(color: Colors.white)),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const PopupMenuItem<String>(
                value: 'vehicles',
                child: ListTile(
                  leading: Icon(Icons.directions_car, color: Color(0xFF00BFFF)),
                  title: Text('Mis Vehículos', style: TextStyle(color: Colors.white)),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const PopupMenuItem<String>(
                value: 'payment',
                child: ListTile(
                  leading: Icon(Icons.payment, color: Color(0xFFAB47BC)),
                  title: Text('Pagar Servicio', style: TextStyle(color: Colors.white)),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white54),
            onPressed: _logout,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 8),
            const Text(
              '¿Qué deseas hacer?',
              style: TextStyle(color: Colors.white54, fontSize: 15),
            ),
            const SizedBox(height: 16),
            _HomeButton(
              icon: Icons.store,
              label: 'Talleres',
              sub: 'CU10-CU13 · Solicitudes e historial',
              color: const Color(0xFF0096FF),
              onTap: () => Navigator.pushNamed(context, '/workshops'),
            ),
            const SizedBox(height: 10),
            _HomeButton(
              icon: Icons.add_alert,
              label: 'Reportar Incidente',
              sub: 'CU7 · GPS + Descripción',
              color: const Color(0xFFFF6B6B),
              onTap: () => Navigator.pushNamed(context, '/report'),
            ),
            const SizedBox(height: 10),
            _HomeButton(
              icon: Icons.gps_fixed,
              label: 'Tracking GPS',
              sub: 'CU15 · Seguimiento en tiempo real',
              color: const Color(0xFF00E676),
              onTap: () => Navigator.pushNamed(
                context,
                '/tracking',
                arguments: {'incidentId': 3, 'role': 'cliente'},
              ),
            ),
            const SizedBox(height: 10),
            _HomeButton(
              icon: Icons.notifications_active,
              label: 'Notificaciones',
              sub: 'CU16/CU17 · Alertas en tiempo real',
              color: const Color(0xFFFFB300),
              badge: _notifCount,
              onTap: () {
                setState(() => _notifCount = 0);
                Navigator.pushNamed(context, '/notifications');
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _HomeButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String sub;
  final Color color;
  final VoidCallback onTap;
  final int badge;

  const _HomeButton({
    required this.icon,
    required this.label,
    required this.sub,
    required this.color,
    required this.onTap,
    this.badge = 0,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF111629),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withValues(alpha: 0.3)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: color, size: 26),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w600),
                  ),
                  Text(
                    sub,
                    style: TextStyle(color: color.withValues(alpha: 0.6), fontSize: 12),
                  ),
                ],
              ),
            ),
            if (badge > 0)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFFFF6B6B),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$badge',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              )
            else
              Icon(Icons.chevron_right, color: color.withValues(alpha: 0.4)),
          ],
        ),
      ),
    );
  }
}

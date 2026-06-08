import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

enum ConnectionState { connecting, connected, disconnected }

class WebSocketService {
  WebSocketChannel? _channel;
  Timer? _reconnectTimer;
  
  int _reconnectAttempt = 0;
  final int _maxReconnectAttempts = 5; // 1s, 2s, 4s, 8s, 16s = 31s max

  final _stateController = StreamController<ConnectionState>.broadcast();
  Stream<ConnectionState> get stateStream => _stateController.stream;

  final _messageController = StreamController<Map<String, dynamic>>.broadcast();
  Stream<Map<String, dynamic>> get messageStream => _messageController.stream;

  String? _currentIncidentId;
  String? _currentToken;
  final String _baseUrl;

  WebSocketService({required String baseUrl}) : _baseUrl = baseUrl {
    _stateController.add(ConnectionState.disconnected);
  }

  void connect(String incidentId, String token) {
    _currentIncidentId = incidentId;
    _currentToken = token;
    _reconnectAttempt = 0;
    _connectInternal();
  }

  void _connectInternal() {
    if (_currentIncidentId == null || _currentToken == null) return;
    
    _stateController.add(ConnectionState.connecting);

    // Reemplazar http/https por ws/wss
    final wsUrl = _baseUrl.replaceFirst('http', 'ws');
    final uri = Uri.parse('$wsUrl/ws/incidents/$_currentIncidentId?token=$_currentToken');

    try {
      _channel = WebSocketChannel.connect(uri);
      
      // Cuando la conexión se establece (el primer stream item suele confirmar)
      _stateController.add(ConnectionState.connected);
      _reconnectAttempt = 0; // reset attempts on successful connection

      _channel!.stream.listen(
        (message) {
          try {
            final decoded = jsonDecode(message);
            _messageController.add(decoded);
          } catch (e) {
            print('[WebSocket] Error parsing message: $e');
          }
        },
        onDone: () {
          print('[WebSocket] Connection closed');
          _handleDisconnect();
        },
        onError: (error) {
          print('[WebSocket] Connection error: $error');
          _handleDisconnect();
        },
      );
    } catch (e) {
      print('[WebSocket] Exception during connect: $e');
      _handleDisconnect();
    }
  }

  void _handleDisconnect() {
    _stateController.add(ConnectionState.disconnected);
    _channel = null;

    if (_reconnectAttempt < _maxReconnectAttempts) {
      // Exponential backoff
      final delay = Duration(seconds: 1 << _reconnectAttempt); // 1, 2, 4, 8, 16...
      _reconnectAttempt++;
      print('[WebSocket] Reconnecting in ${delay.inSeconds}s (Attempt $_reconnectAttempt)');
      
      _reconnectTimer?.cancel();
      _reconnectTimer = Timer(delay, _connectInternal);
    } else {
      print('[WebSocket] Max reconnect attempts reached.');
    }
  }

  void send(Map<String, dynamic> data) {
    if (_channel != null && _stateController.hasListener) { // Solo un hack para saber si estamos alive
      _channel!.sink.add(jsonEncode(data));
    }
  }

  void disconnect() {
    _currentIncidentId = null;
    _currentToken = null;
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
    _stateController.add(ConnectionState.disconnected);
  }

  void dispose() {
    disconnect();
    _stateController.close();
    _messageController.close();
  }
}

// Instancia global sugerida para inyección de dependencias simple
final wsService = WebSocketService(baseUrl: 'http://10.0.2.2:8000'); // Usar la misma URL que el Backend

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import '../modules/workshops/models/workshop_model.dart';
import '../modules/workshops/services/workshop_service.dart';
import 'report_incident_screen.dart';

class WorkshopExplorerScreen extends StatefulWidget {
  final bool isSelecting;
  const WorkshopExplorerScreen({super.key, this.isSelecting = false});

  @override
  State<WorkshopExplorerScreen> createState() => _WorkshopExplorerScreenState();
}

class _WorkshopExplorerScreenState extends State<WorkshopExplorerScreen> {
  final MapController _mapController = MapController();
  List<Workshop> _workshops = [];
  bool _isLoading = true;
  Position? _currentPosition;
  Workshop? _selectedWorkshop;

  @override
  void initState() {
    super.initState();
    _initData();
  }

  Future<void> _initData() async {
    try {
      final position = await _determinePosition();
      setState(() => _currentPosition = position);
      
      // Simulando llamada a un servicio que trae los talleres cercanos
      // El backend no tiene un endpoint explícito para nearby todavía, usaremos los favoritos o un mock local si falla
      try {
        // Fetch all workshops from backend to display on the map
        final data = await WorkshopService.listAllWorkshops();
        if (data.isNotEmpty) {
           _workshops = data;
        }
      } catch (e) {
        print('Error fetching workshops: $e');
      }
      
      if (_workshops.isEmpty) {
        // Fallback para visualización de la UI si no hay favoritos
        _workshops = [
          Workshop(
            id: 1,
            usuarioPropietarioId: 1,
            nombre: 'SuperMecánica SCZ',
            direccion: '3er Anillo Interno, Santa Cruz',
            latitud: -17.7813,
            longitud: -63.1801,
            calificacionPromedio: 4.8,
            estaActivo: true,
            creadoEn: '',
          ),
          Workshop(
            id: 2,
            usuarioPropietarioId: 2,
            nombre: 'AutoFix Express',
            direccion: 'Av. Banzer Km 2, Santa Cruz',
            latitud: -17.7780,
            longitud: -63.1750,
            calificacionPromedio: 4.5,
            estaActivo: true,
            creadoEn: '',
          ),
          Workshop(
            id: 3,
            usuarioPropietarioId: 3,
            nombre: 'Taller El Tuerca',
            direccion: 'Plan 3000, Santa Cruz',
            latitud: -17.8100,
            longitud: -63.1500,
            calificacionPromedio: 4.0,
            estaActivo: true,
            creadoEn: '',
          ),
        ];
      }
      
      setState(() => _isLoading = false);
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<Position> _determinePosition() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) return Future.error('Location services are disabled.');

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        return Future.error('Location permissions are denied');
      }
    }
    
    if (permission == LocationPermission.deniedForever) {
      return Future.error('Location permissions are permanently denied, we cannot request permissions.');
    } 

    return await Geolocator.getCurrentPosition();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        title: const Text('Explorar Talleres'),
        backgroundColor: const Color(0xFF111629),
        elevation: 0,
      ),
      body: _isLoading 
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF00F2FF)))
          : Stack(
              children: [
                _buildMap(),
                if (_selectedWorkshop != null) _buildWorkshopCard(),
              ],
            ),
    );
  }

  Widget _buildMap() {
    final initialLat = _currentPosition?.latitude ?? -17.7833;
    final initialLng = _currentPosition?.longitude ?? -63.1821;

    return FlutterMap(
      mapController: _mapController,
      options: MapOptions(
        initialCenter: LatLng(initialLat, initialLng),
        initialZoom: 13.0,
        onTap: (_, __) => setState(() => _selectedWorkshop = null),
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.rutaigeoproxi.app',
        ),
        MarkerLayer(
          markers: [
            if (_currentPosition != null)
              Marker(
                point: LatLng(_currentPosition!.latitude, _currentPosition!.longitude),
                width: 40,
                height: 40,
                child: const Icon(Icons.my_location, color: Colors.blue, size: 30),
              ),
            ..._workshops.map((w) => Marker(
              point: LatLng(w.latitud, w.longitud),
              width: 50,
              height: 50,
              child: GestureDetector(
                onTap: () {
                  setState(() => _selectedWorkshop = w);
                  _mapController.move(LatLng(w.latitud, w.longitud), 15.0);
                },
                child: Icon(
                  Icons.build_circle, 
                  color: _selectedWorkshop?.id == w.id ? const Color(0xFF00E676) : const Color(0xFFFF6B6B), 
                  size: _selectedWorkshop?.id == w.id ? 45 : 35
                ),
              ),
            )),
          ],
        ),
      ],
    );
  }

  Widget _buildWorkshopCard() {
    final w = _selectedWorkshop!;
    return Positioned(
      bottom: 20,
      left: 20,
      right: 20,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFF111629),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.5), blurRadius: 10, offset: const Offset(0, 5))],
          border: Border.all(color: const Color(0xFF00F2FF).withOpacity(0.3)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    w.nombre,
                    style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFF00E676).withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.star, color: Color(0xFF00E676), size: 16),
                      const SizedBox(width: 4),
                      Text(w.calificacionPromedio.toString(), style: const TextStyle(color: Color(0xFF00E676), fontWeight: FontWeight.bold)),
                    ],
                  ),
                )
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.location_on, color: Colors.white54, size: 16),
                const SizedBox(width: 4),
                Expanded(child: Text(w.direccion, style: const TextStyle(color: Colors.white70, fontSize: 13), maxLines: 1, overflow: TextOverflow.ellipsis)),
              ],
            ),
            if (w.especialidades != null && w.especialidades!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(color: Colors.black26, borderRadius: BorderRadius.circular(8)),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.build, size: 14, color: Colors.white70),
                    const SizedBox(width: 4),
                    Text('Especialidad: ${w.especialidades!.first.toUpperCase()}', style: const TextStyle(color: Colors.white70, fontSize: 13)),
                  ],
                ),
              ),
            ],const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () {
                  if (widget.isSelecting) {
                    Navigator.pop(context, w);
                  } else {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => ReportIncidentScreen(preselectedWorkshop: w)),
                    );
                  }
                },
                icon: const Icon(Icons.check_circle, color: Colors.black),
                label: Text(widget.isSelecting ? 'SELECCIONAR ESTE TALLER' : 'SOLICITAR SERVICIO A ESTE TALLER', style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 13)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF00F2FF),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
            )
          ],
        ),
      ),
    );
  }
}

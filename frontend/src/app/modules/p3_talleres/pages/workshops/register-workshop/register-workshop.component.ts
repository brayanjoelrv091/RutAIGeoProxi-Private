import { Component, OnInit, AfterViewInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, FormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { WorkshopService, Technician, Workshop } from '../../../workshop.service';
import { AuthService } from '../../../../p1_usuarios/auth.service';
import * as L from 'leaflet';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-register-workshop',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, RouterModule],
  templateUrl: './register-workshop.component.html',
  styleUrl: './register-workshop.component.css',
})
export class RegisterWorkshopComponent implements OnInit, AfterViewInit, OnDestroy {
  private readonly wsSvc = inject(WorkshopService);
  private readonly authSvc = inject(AuthService);
  private readonly http = inject(HttpClient);
  private readonly fb = inject(FormBuilder);
  public readonly router = inject(Router);

  workshopForm = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.minLength(2)]],
    direccion: ['', [Validators.required, Validators.minLength(5)]],
    latitud: [0, Validators.required],
    longitud: [0, Validators.required],
    telefono: [''],
    email: [''],
    password: ['', [Validators.minLength(8)]],
    especialidades: [''],
  });

  techForm = this.fb.nonNullable.group({
    nombre: ['', Validators.required],
    telefono: [''],
    especialidad: [''],
  });

  createdWorkshopId: number | null = null;
  technicians: Technician[] = [];
  error = '';
  success = '';
  locLoading = false;
  checkingProfile = true;

  // -- Map Search --
  searchQuery = '';
  isSearching = false;

  // -- Map State --
  private map: L.Map | undefined;
  private tileLayer: L.TileLayer | undefined;
  private myMarker: L.Marker | undefined;
  private subs: Subscription[] = [];
  private themeObserver: MutationObserver | undefined;
  otherWorkshops: Workshop[] = [];

  ngOnInit() {
    this.checkExistingProfile();
    this.loadOtherWorkshops();
  }

  ngAfterViewInit(): void {
    // Timeout needed to wait for ngIf to render the map container if it's conditional
    setTimeout(() => {
      if (!this.createdWorkshopId && !this.checkingProfile) {
        this.initMap();
      }
    }, 100);
  }

  ngOnDestroy(): void {
    this.subs.forEach(s => s.unsubscribe());
    if (this.themeObserver) {
      this.themeObserver.disconnect();
    }
    if (this.map) {
      this.map.remove();
    }
  }

  loadOtherWorkshops() {
    this.subs.push(
      this.wsSvc.listAllWorkshops().subscribe({
        next: (ws) => {
          this.otherWorkshops = ws;
          this.plotOtherWorkshops();
        },
        error: (e) => console.error('Error loading other workshops', e)
      })
    );
  }

  searchAddress() {
    if (!this.searchQuery.trim() || !this.map) return;
    this.isSearching = true;
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(this.searchQuery)}`;
    this.http.get<any[]>(url).subscribe({
      next: (res) => {
        this.isSearching = false;
        if (res && res.length > 0) {
          const lat = parseFloat(res[0].lat);
          const lon = parseFloat(res[0].lon);
          this.map!.flyTo([lat, lon], 16);
          this.updateMyMarker(lat, lon);
        } else {
          this.error = 'No se encontró la dirección.';
          setTimeout(() => this.error = '', 3000);
        }
      },
      error: () => {
        this.isSearching = false;
        this.error = 'Error buscando dirección.';
        setTimeout(() => this.error = '', 3000);
      }
    });
  }

  private initMap(): void {
    const mapContainer = document.getElementById('workshop-map');
    if (!mapContainer) return;

    // Default to a central coordinate (e.g. Santa Cruz, Bolivia)
    this.map = L.map('workshop-map').setView([-17.7833, -63.1821], 13);
    
    const isLight = document.body.classList.contains('light-theme');
    const tileUrl = isLight 
      ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

    this.tileLayer = L.tileLayer(tileUrl, {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 20
    }).addTo(this.map);

    this.themeObserver = new MutationObserver(() => {
      if (this.tileLayer) {
        const light = document.body.classList.contains('light-theme');
        this.tileLayer.setUrl(light 
          ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
          : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
        );
      }
    });
    this.themeObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });

    // Plot existing workshops if already loaded
    this.plotOtherWorkshops();

    // Map Click Listener
    this.map.on('click', (e: L.LeafletMouseEvent) => {
      this.updateMyMarker(e.latlng.lat, e.latlng.lng);
    });

    // Listen to Workshop Name changes to update marker tooltip
    this.subs.push(
      this.workshopForm.get('nombre')!.valueChanges.subscribe(name => {
        if (this.myMarker) {
          const content = `<div style="text-align:center;font-weight:bold;color:#00F2FF;">${name || 'Mi Taller'}</div>`;
          this.myMarker.setPopupContent(content);
        }
      })
    );
  }

  private plotOtherWorkshops() {
    if (!this.map || this.otherWorkshops.length === 0) return;
    
    this.otherWorkshops.forEach(ws => {
      const iconHtml = `<div style="font-size: 20px; text-shadow: 0 0 5px #00C853; opacity: 0.7;">🏪</div>`;
      const customIcon = L.divIcon({
        html: iconHtml,
        className: 'other-workshop-icon',
        iconSize: [25, 25],
        iconAnchor: [12, 12]
      });
      const marker = L.marker([ws.latitud, ws.longitud], { icon: customIcon }).addTo(this.map!);
      marker.bindPopup(`<div style="color:#00C853;font-weight:bold;text-align:center;">${ws.nombre}</div><div style="font-size:0.8rem;text-align:center;">Taller en la red</div>`);
    });
  }

  private updateMyMarker(lat: number, lng: number) {
    this.workshopForm.patchValue({ latitud: lat, longitud: lng });
    
    if (!this.map) return;
    const latLng = L.latLng(lat, lng);
    
    if (!this.myMarker) {
      const iconHtml = `<div style="font-size: 30px; text-shadow: 0 0 15px #00F2FF; animation: pulse 2s infinite;">🔧</div>`;
      const customIcon = L.divIcon({
        html: iconHtml,
        className: 'my-workshop-icon',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      });
      this.myMarker = L.marker(latLng, { icon: customIcon, draggable: true }).addTo(this.map);
      
      this.myMarker.on('dragend', (event: any) => {
        const marker = event.target;
        const position = marker.getLatLng();
        this.workshopForm.patchValue({ latitud: position.lat, longitud: position.lng });
      });

      const name = this.workshopForm.get('nombre')?.value || 'Mi Taller';
      this.myMarker.bindPopup(`<div style="text-align:center;font-weight:bold;color:#00F2FF;">${name}</div>`).openPopup();
    } else {
      this.myMarker.setLatLng(latLng);
      if (!this.myMarker.isPopupOpen()) {
        this.myMarker.openPopup();
      }
    }
  }

  checkExistingProfile() {
    this.wsSvc.getMyProfile().subscribe({
      next: (profile) => {
        if (profile) {
          const role = this.authSvc.getUserRole();
          if ((profile as any).estado_registro === 'completado') {
            if (role === 'admin') {
               // Admin can create multiple workshops, so we don't redirect them
               this.checkingProfile = false;
               setTimeout(() => {
                 if (!this.createdWorkshopId && document.getElementById('workshop-map') && !this.map) {
                   this.initMap();
                 }
               }, 100);
               return;
            }
            this.router.navigate(['/workshops/profile']);
            return;
          } else {
            // Retomar donde quedó
            this.createdWorkshopId = profile.id;
            this.technicians = profile.tecnicos || [];
            this.success = 'Retomando registro del taller...';
          }
        }
        this.checkingProfile = false;
        // Init map after view updates
        setTimeout(() => {
          if (!this.createdWorkshopId && document.getElementById('workshop-map') && !this.map) {
            this.initMap();
          }
        }, 100);
      },
      error: (e) => {
        // No tiene taller (404), continuar normal
        this.checkingProfile = false;
        setTimeout(() => {
          if (!this.createdWorkshopId && document.getElementById('workshop-map') && !this.map) {
            this.initMap();
          }
        }, 100);
      }
    });
  }

  detectLocation(): void {
    if (!navigator.geolocation) return;
    this.locLoading = true;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        this.locLoading = false;
        this.updateMyMarker(pos.coords.latitude, pos.coords.longitude);
        if (this.map) {
          this.map.setView([pos.coords.latitude, pos.coords.longitude], 18);
        }
      },
      () => (this.locLoading = false),
      { enableHighAccuracy: true }
    );
  }

  registerWorkshop(): void {
    if (this.workshopForm.invalid) return;
    this.error = '';
    const v = this.workshopForm.getRawValue();
    const specs = v.especialidades ? v.especialidades.split(',').map((s: string) => s.trim()).filter(Boolean) : undefined;
    this.wsSvc.registerWorkshop({
      nombre: v.nombre, direccion: v.direccion, latitud: v.latitud, longitud: v.longitud,
      telefono: v.telefono || undefined, email: v.email || undefined, password: v.password || undefined, especialidades: specs,
    }).subscribe({
      next: (ws) => {
        this.createdWorkshopId = ws.id;
        this.success = `Taller "${ws.nombre}" registrado correctamente. Ahora agregue a sus técnicos.`;
      },
      error: (e) => (this.error = e?.error?.detail || 'Error al registrar taller'),
    });
  }

  addTechnician(): void {
    if (!this.createdWorkshopId || this.techForm.invalid) return;
    const v = this.techForm.getRawValue();
    this.wsSvc.addTechnician(this.createdWorkshopId, {
      nombre: v.nombre, telefono: v.telefono || undefined, especialidad: v.especialidad || undefined,
    }).subscribe({
      next: (t) => {
        this.technicians.push(t);
        this.techForm.reset({ nombre: '', telefono: '', especialidad: '' });
      },
      error: (e) => (this.error = e?.error?.detail || 'Error al agregar técnico'),
    });
  }

  finishRegistration(): void {
    this.wsSvc.completeRegistration().subscribe({
      next: () => {
        this.router.navigate(['/workshops/profile']);
      },
      error: (e) => (this.error = e?.error?.detail || 'Error al completar el registro'),
    });
  }
}


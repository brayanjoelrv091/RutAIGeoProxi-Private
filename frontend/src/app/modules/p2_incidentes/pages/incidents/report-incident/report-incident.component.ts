import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { IncidentService } from '../../../incident.service';
import { OfflineSyncService } from '../../../p8_realtime/offline-sync.service';

@Component({
  selector: 'app-report-incident',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './report-incident.component.html',
  styleUrl: './report-incident.component.css',
})
export class ReportIncidentComponent {
  private readonly incidentSvc = inject(IncidentService);
  private readonly offlineSyncSvc = inject(OfflineSyncService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);

  form = this.fb.nonNullable.group({
    titulo: ['', [Validators.required, Validators.minLength(3)]],
    descripcion: [''],
    latitud: [0, Validators.required],
    longitud: [0, Validators.required],
    direccion: [''],
  });

  selectedPhotos: File[] = [];
  selectedAudio: File | null = null;
  error = '';
  success = '';
  loading = false;
  locationLoading = false;

  detectLocation(): void {
    if (!navigator.geolocation) {
      this.error = 'Geolocalización no soportada en este navegador';
      return;
    }
    this.locationLoading = true;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        this.form.patchValue({
          latitud: pos.coords.latitude,
          longitud: pos.coords.longitude,
        });
        this.locationLoading = false;
      },
      (err) => {
        this.error = 'No se pudo obtener la ubicación: ' + err.message;
        this.locationLoading = false;
      },
      { enableHighAccuracy: true }
    );
  }

  onPhotosSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      this.selectedPhotos = Array.from(input.files).slice(0, 5);
    }
  }

  onAudioSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      this.selectedAudio = input.files[0];
    }
  }

  async submit(): Promise<void> {
    if (this.form.invalid) return;
    this.loading = true;
    this.error = '';
    this.success = '';

    const v = this.form.getRawValue();

    if (!navigator.onLine) {
      // Offline mode
      const key = this.offlineSyncSvc.generateKey();
      await this.offlineSyncSvc.queueIncident({
        idempotency_key: key,
        titulo: v.titulo,
        descripcion: v.descripcion || undefined,
        latitud: v.latitud,
        longitud: v.longitud,
        direccion: v.direccion || undefined,
      });
      
      this.success = `Guardado sin conexión. Se enviará automáticamente cuando recuperes la señal.`;
      this.loading = false;
      setTimeout(() => void this.router.navigate(['/dashboard']), 2000);
      return;
    }

    this.incidentSvc
      .reportIncident(
        {
          titulo: v.titulo,
          descripcion: v.descripcion || undefined,
          latitud: v.latitud,
          longitud: v.longitud,
          direccion: v.direccion || undefined,
        },
        this.selectedPhotos.length > 0 ? this.selectedPhotos : undefined,
        this.selectedAudio || undefined
      )
      .subscribe({
        next: (incident) => {
          this.success = `Incidente #${incident.id} reportado — Categoría: ${incident.categoria || 'pendiente'}`;
          this.loading = false;
          setTimeout(() => void this.router.navigate(['/incidents', incident.id]), 2000);
        },
        error: (e) => {
          this.error = e?.error?.detail || 'Error al reportar incidente';
          this.loading = false;
        },
      });
  }
}

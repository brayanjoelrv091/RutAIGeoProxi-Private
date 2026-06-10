import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environment';

// ── Interfaces ──

export interface Workshop {
  id: number;
  usuario_propietario_id: number;
  nombre: string;
  direccion: string;
  latitud: number;
  longitud: number;
  telefono: string | null;
  email: string | null;
  especialidades: string[] | null;
  esta_activo: boolean;
  calificacion_promedio: number;
  creado_en: string;
  en_linea?: boolean;
  estado_registro?: string;
  ultimo_heartbeat?: string;
}

export interface Technician {
  id: number;
  taller_id: number;
  nombre: string;
  telefono: string | null;
  especialidad: string | null;
  esta_disponible: boolean;
  latitud: number | null;
  longitud: number | null;
}

export interface ServiceRequest {
  id: number;
  incidente_id: number;
  taller_id: number;
  tecnico_id: number | null;
  estado: string;
  notas: string | null;
  creado_en: string;
  actualizado_en: string | null;
  // Info Enriquecida
  titulo_incidente?: string;
  categoria_incidente?: string;
  severidad_incidente?: string;
  resumen_ia?: string;
}

export interface ServiceHistory {
  // Base fields from ServiceRequest
  id: number;
  taller_id: number;
  incidente_id: number;
  estado: string;
  notas: string | null;
  creado_en: string;
  actualizado_en: string | null;
  // Info Enriquecida
  titulo_incidente: string | undefined;
  categoria_incidente: string | undefined;
  severidad_incidente: string | undefined;
  resumen_ia?: string;
}

@Injectable({ providedIn: 'root' })
export class WorkshopService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiUrl;

  // ── CU10 ──

  registerWorkshop(data: {
    nombre: string;
    direccion: string;
    latitud: number;
    longitud: number;
    telefono?: string;
    email?: string;
    password?: string;
    especialidades?: string[];
  }): Observable<Workshop> {
    return this.http.post<Workshop>(`${this.base}/workshops`, data);
  }

  listMyWorkshops(): Observable<Workshop[]> {
    return this.http.get<Workshop[]>(`${this.base}/workshops`);
  }

  listAllWorkshops(): Observable<Workshop[]> {
    return this.http.get<Workshop[]>(`${this.base}/workshops/all`);
  }

  getWorkshop(id: number): Observable<Workshop> {
    return this.http.get<Workshop>(`${this.base}/workshops/${id}`);
  }

  addTechnician(
    workshopId: number,
    data: { nombre: string; telefono?: string; especialidad?: string; latitud?: number; longitud?: number },
  ): Observable<Technician> {
    return this.http.post<Technician>(`${this.base}/workshops/${workshopId}/technicians`, data);
  }

  listTechnicians(workshopId: number): Observable<Technician[]> {
    return this.http.get<Technician[]>(`${this.base}/workshops/${workshopId}/technicians`);
  }

  toggleAvailability(technicianId: number, available: boolean): Observable<Technician> {
    return this.http.patch<Technician>(
      `${this.base}/workshops/technicians/${technicianId}/availability`,
      { esta_disponible: available },
    );
  }

  // ── HEARTBEAT Y PERFIL ──

  getMyProfile(): Observable<Workshop & { tecnicos: Technician[] }> {
    return this.http.get<Workshop & { tecnicos: Technician[] }>(`${this.base}/workshops/me/profile`);
  }

  completeRegistration(): Observable<Workshop> {
    return this.http.post<Workshop>(`${this.base}/workshops/me/complete`, {});
  }

  heartbeat(): Observable<any> {
    return this.http.post(`${this.base}/workshops/heartbeat`, {});
  }

  disconnect(): Observable<any> {
    return this.http.post(`${this.base}/workshops/disconnect`, {});
  }

  // ── CU11 ──

  listPendingRequests(workshopId: number): Observable<ServiceRequest[]> {
    return this.http.get<ServiceRequest[]>(`${this.base}/workshops/${workshopId}/requests`);
  }

  // ── CU12 ──

  updateRequestStatus(
    requestId: number,
    data: { estado: string; notas?: string; tecnico_id?: number },
  ): Observable<ServiceRequest> {
    return this.http.patch<ServiceRequest>(`${this.base}/workshops/requests/${requestId}/status`, data);
  }

  // ── CU13 ──

  getServiceHistory(workshopId: number): Observable<ServiceHistory[]> {
    return this.http.get<ServiceHistory[]>(`${this.base}/workshops/${workshopId}/history`);
  }
}

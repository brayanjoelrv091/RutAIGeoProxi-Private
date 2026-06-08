import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar'; // O tu servicio de Toasts
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { environment } from '../../../../../environments/environment';

export interface WSMessage {
  type: string;
  data: any;
}

@Injectable({
  providedIn: 'root'
})
export class TallerWebsocketService {
  private socket$!: WebSocketSubject<WSMessage>;
  private tenantId: number | null = null;

  constructor(private snackBar: MatSnackBar) {}

  public connect(tenantId: number, token: string) {
    if (this.socket$) return;
    this.tenantId = tenantId;
    
    // Conecta al namespace de su Tenant
    const wsUrl = `${environment.wsUrl}/realtime/ws/tenant/${tenantId}?token=${token}`;
    this.socket$ = webSocket(wsUrl);

    this.socket$.subscribe({
      next: (msg) => this.handleMessage(msg),
      error: (err) => console.error('WebSocket Error:', err),
      complete: () => console.log('WebSocket cerrado')
    });
  }

  private handleMessage(msg: WSMessage) {
    if (msg.type === 'nuevo_servicio_asignado') {
      const data = msg.data;
      // CU-31: Alerta sonora o visual en Angular
      this.playAlertSound();
      this.snackBar.open(
        `🚨 ¡NUEVO INCIDENTE ASIGNADO! (${data.titulo}) a ${(data.distancia_km || 0).toFixed(2)} km.`,
        'VER DETALLE',
        { 
          duration: 10000, 
          panelClass: ['bg-green-600', 'text-white', 'font-bold'] 
        }
      ).onAction().subscribe(() => {
        // Redirigir a la pantalla del incidente
        window.location.href = `/talleres/incidentes/${data.incidente_id}`;
      });
    }

    if (msg.type === 'servicio_cancelado_timeout') {
      this.snackBar.open(
        `⚠️ Un servicio fue reasignado por timeout de inactividad.`,
        'Cerrar',
        { duration: 5000, panelClass: ['bg-red-600', 'text-white'] }
      );
    }
  }

  private playAlertSound() {
    const audio = new Audio('/assets/sounds/alert.mp3');
    audio.play().catch(e => console.log('Autoplay bloqueado por el navegador'));
  }

  public disconnect() {
    if (this.socket$) {
      this.socket$.complete();
    }
  }
}

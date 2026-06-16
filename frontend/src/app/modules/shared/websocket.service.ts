import { Injectable } from '@angular/core';
import { Subject, Observable } from 'rxjs';
import { environment } from '../../environment';

const TOKEN_KEY = 'access_token';

@Injectable({
  providedIn: 'root'
})
export class WebSocketService {
  private wsUrl = environment.apiUrl.replace('http', 'ws');
  private trackingSubject: Subject<any> = new Subject();
  private notificationSubject: Subject<any> = new Subject();
  private socket: WebSocket | null = null;
  private notificationSocket: WebSocket | null = null;

  constructor() {}

  private getToken(): string | null {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  /**
   * Se conecta al tracking de un incidente específico (CU15).
   */
  connectTracking(incidentId: number): Observable<any> {
    const url = `${this.wsUrl}/assignments/ws/track/${incidentId}`;
    this.socket = new WebSocket(url);

    this.socket.onmessage = (event) => {
      this.trackingSubject.next(JSON.parse(event.data));
    };

    this.socket.onclose = () => {
      console.log('WS Tracking cerrado');
    };

    return this.trackingSubject.asObservable();
  }

  sendLocation(lat: number, lng: number, role: string) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        lat,
        lng,
        role,
        timestamp: new Date().toISOString()
      }));
    }
  }

  /**
   * Se conecta a las notificaciones globales del usuario (CU16, CU17).
   * Incluye token de autenticación.
   */
  connectNotifications(userId: number): Observable<any> {
    if (!this.notificationSocket || this.notificationSocket.readyState !== WebSocket.OPEN) {
      const token = this.getToken();
      const url = token
        ? `${this.wsUrl}/payments/ws/notifications/${userId}?token=${encodeURIComponent(token)}`
        : `${this.wsUrl}/payments/ws/notifications/${userId}`;
      this.notificationSocket = new WebSocket(url);

      this.notificationSocket.onmessage = (event) => {
        this.notificationSubject.next(JSON.parse(event.data));
      };
      
      this.notificationSocket.onclose = () => {
        this.notificationSocket = null;
      };
    }

    return this.notificationSubject.asObservable();
  }
}

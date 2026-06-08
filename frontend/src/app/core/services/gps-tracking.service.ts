import { Injectable, OnDestroy } from '@angular/core';
import { WebsocketService } from './websocket.service';
import { Subject, Subscription, timer } from 'rxjs';
import { throttleTime } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class GpsTrackingService implements OnDestroy {
  private watchId?: number;
  private locationSubject = new Subject<GeolocationPosition>();
  private sub?: Subscription;

  constructor(private wsService: WebsocketService) {
    // Throttling: solo tomamos un evento cada 5 segundos
    this.sub = this.locationSubject.pipe(
      throttleTime(5000)
    ).subscribe((position: GeolocationPosition) => {
      this.wsService.sendMessage({
        type: 'GPS_UPDATE',
        lat: position.coords.latitude,
        lng: position.coords.longitude,
        timestamp: position.timestamp
      });
      console.log('[GPS] Ubicación enviada al WebSocket:', position.coords.latitude, position.coords.longitude);
    });
  }

  public startTracking(): void {
    if (!navigator.geolocation) {
      console.error('La geolocalización no está soportada por este navegador.');
      return;
    }

    if (this.watchId) return; // Ya está corriendo

    this.watchId = navigator.geolocation.watchPosition(
      (position) => {
        this.locationSubject.next(position);
      },
      (error) => {
        console.error('[GPS] Error obteniendo ubicación:', error);
      },
      {
        enableHighAccuracy: true,
        maximumAge: 0,
        timeout: 10000
      }
    );
    console.log('[GPS] Tracking iniciado');
  }

  public stopTracking(): void {
    if (this.watchId !== undefined) {
      navigator.geolocation.clearWatch(this.watchId);
      this.watchId = undefined;
      console.log('[GPS] Tracking detenido');
    }
  }

  ngOnDestroy(): void {
    this.stopTracking();
    if (this.sub) this.sub.unsubscribe();
  }
}

import { Injectable, OnDestroy } from '@angular/core';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { Observable, Subject, timer, Subscription, EMPTY } from 'rxjs';
import { retryWhen, delayWhen, tap, catchError, switchMap } from 'rxjs/operators';
import { environment } from '../../../environments/environment'; // Ajusta la ruta a environment si es necesario

import { HttpClient } from '@angular/common/http';

export enum ConnectionState {
  CONNECTING = 'Conectando...',
  CONNECTED = 'Conectado',
  DISCONNECTED = 'Desconectado',
}

@Injectable({
  providedIn: 'root'
})
export class WebsocketService implements OnDestroy {
  private socket$!: WebSocketSubject<any>;
  private messagesSubject = new Subject<any>();
  private connectionStateSubject = new Subject<ConnectionState>();
  
  public messages$ = this.messagesSubject.asObservable();
  public connectionState$ = this.connectionStateSubject.asObservable();

  private maxRetries = 5; // Limite de reintentos
  private wsSubscription!: Subscription;

  constructor(private http: HttpClient) {
    this.connectionStateSubject.next(ConnectionState.DISCONNECTED);
  }

  public updateEstado(incidentId: string, newState: string): Observable<any> {
    const url = `${environment.apiUrl}/incidents/${incidentId}/estado`;
    return this.http.patch(url, { estado: newState });
  }

  public connect(incidentId: string, token: string): void {
    if (!this.socket$ || this.socket$.closed) {
      this.connectionStateSubject.next(ConnectionState.CONNECTING);
      
      const wsUrl = environment.apiUrl.replace('http', 'ws');
      const url = `${wsUrl}/ws/incidents/${incidentId}?token=${token}`;

      this.socket$ = webSocket({
        url: url,
        openObserver: {
          next: () => {
            console.log('[WebSocket] Conectado');
            this.connectionStateSubject.next(ConnectionState.CONNECTED);
          }
        },
        closeObserver: {
          next: () => {
            console.log('[WebSocket] Desconectado');
            this.connectionStateSubject.next(ConnectionState.DISCONNECTED);
          }
        }
      });

      this.wsSubscription = this.socket$.pipe(
        retryWhen(errors =>
          errors.pipe(
            switchMap((err, index) => {
              if (index >= this.maxRetries) {
                console.error('[WebSocket] Máximos reintentos alcanzados.');
                return EMPTY; // Deja de reintentar
              }
              // Exponential backoff: 1s, 2s, 4s, 8s, 16s
              const delayTime = Math.pow(2, index) * 1000;
              console.log(`[WebSocket] Reintentando en ${delayTime}ms...`);
              this.connectionStateSubject.next(ConnectionState.CONNECTING);
              return timer(delayTime);
            })
          )
        ),
        catchError(error => {
          console.error('[WebSocket] Error persistente:', error);
          this.connectionStateSubject.next(ConnectionState.DISCONNECTED);
          return EMPTY;
        })
      ).subscribe(
        msg => this.messagesSubject.next(msg),
        err => console.error(err),
        () => console.log('[WebSocket] Stream completado')
      );
    }
  }

  public sendMessage(msg: any): void {
    if (this.socket$) {
      this.socket$.next(msg);
    }
  }

  public disconnect(): void {
    if (this.wsSubscription) {
      this.wsSubscription.unsubscribe();
    }
    if (this.socket$) {
      this.socket$.complete();
    }
    this.connectionStateSubject.next(ConnectionState.DISCONNECTED);
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}

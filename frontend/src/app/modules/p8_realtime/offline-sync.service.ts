import { Injectable } from '@angular/core';
import { BehaviorSubject, fromEvent, merge } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { environment } from '../../environment';

/**
 * P8 · CU-21/22/23 — Servicio de sincronización offline (PWA).
 *
 * Características:
 *   - Detecta estado de conexión vía navigator.onLine
 *   - Almacena incidentes pendientes en IndexedDB
 *   - Sincroniza automáticamente al recuperar conexión
 *   - Deduplicación por idempotency_key (UUID v4)
 */

export interface OfflineIncident {
  idempotency_key: string;
  titulo: string;
  descripcion?: string;
  latitud: number;
  longitud: number;
  direccion?: string;
  created_at_local: string;
  synced: boolean;
}

export interface SyncResult {
  idempotency_key: string;
  status: 'created' | 'duplicate' | 'error';
  incident_id?: number;
  message: string;
}

@Injectable({ providedIn: 'root' })
export class OfflineSyncService {

  private readonly DB_NAME = 'rutai_offline_db';
  private readonly STORE_NAME = 'pending_incidents';
  private readonly DB_VERSION = 1;

  // ── Estado observable ──
  private isOnline$ = new BehaviorSubject<boolean>(navigator.onLine);
  readonly online$ = this.isOnline$.asObservable();

  private pendingCount$ = new BehaviorSubject<number>(0);
  readonly pendingCount = this.pendingCount$.asObservable();

  private syncing$ = new BehaviorSubject<boolean>(false);
  readonly isSyncing = this.syncing$.asObservable();

  private db: IDBDatabase | null = null;

  constructor(private http: HttpClient) {
    this.initDB();
    this.watchConnectivity();
  }

  // ══════════════════════════════════════════════════════════════════
  // PUBLIC API
  // ══════════════════════════════════════════════════════════════════

  /**
   * Genera un UUID v4 para idempotency_key.
   */
  generateKey(): string {
    return crypto.randomUUID();
  }

  /**
   * Guarda un incidente en la cola offline (IndexedDB).
   */
  async queueIncident(incident: Omit<OfflineIncident, 'synced' | 'created_at_local'>): Promise<void> {
    const item: OfflineIncident = {
      ...incident,
      created_at_local: new Date().toISOString(),
      synced: false,
    };

    await this.addToStore(item);
    await this.updatePendingCount();
  }

  /**
   * Intenta sincronizar todos los incidentes pendientes.
   */
  async syncAll(token: string): Promise<SyncResult[]> {
    if (!navigator.onLine) {
      return [];
    }

    const pending = await this.getPendingItems();
    if (pending.length === 0) return [];

    this.syncing$.next(true);

    try {
      const headers = new HttpHeaders({
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      });

      const payload = {
        items: pending.map(item => ({
          idempotency_key: item.idempotency_key,
          titulo: item.titulo,
          descripcion: item.descripcion || null,
          latitud: item.latitud,
          longitud: item.longitud,
          direccion: item.direccion || null,
          created_at_local: item.created_at_local,
        })),
      };

      const response: any = await this.http.post(
        `${environment.apiUrl}/realtime/incidents/offline-sync`,
        payload,
        { headers }
      ).toPromise();

      // Marcar items sincronizados
      if (response?.results) {
        for (const result of response.results) {
          if (result.status === 'created' || result.status === 'duplicate') {
            await this.markSynced(result.idempotency_key);
          }
        }
      }

      await this.updatePendingCount();
      return response?.results || [];

    } catch (err) {
      console.error('[OfflineSyncService] Error en sincronización:', err);
      return [];
    } finally {
      this.syncing$.next(false);
    }
  }

  /**
   * Obtiene la lista de incidentes pendientes de sync.
   */
  async getPendingItems(): Promise<OfflineIncident[]> {
    return new Promise((resolve, reject) => {
      if (!this.db) { resolve([]); return; }

      const tx = this.db.transaction(this.STORE_NAME, 'readonly');
      const store = tx.objectStore(this.STORE_NAME);
      const index = store.index('synced');
      const request = index.getAll(0); // synced = false (0)

      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  // ══════════════════════════════════════════════════════════════════
  // INTERNALS
  // ══════════════════════════════════════════════════════════════════

  private initDB(): void {
    const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);

    request.onupgradeneeded = (event: any) => {
      const db: IDBDatabase = event.target.result;

      if (!db.objectStoreNames.contains(this.STORE_NAME)) {
        const store = db.createObjectStore(this.STORE_NAME, { keyPath: 'idempotency_key' });
        store.createIndex('synced', 'synced', { unique: false });
        store.createIndex('created_at_local', 'created_at_local', { unique: false });
      }
    };

    request.onsuccess = (event: any) => {
      this.db = event.target.result;
      this.updatePendingCount();
    };

    request.onerror = () => {
      console.error('[OfflineSyncService] Error abriendo IndexedDB');
    };
  }

  private watchConnectivity(): void {
    const online$ = fromEvent(window, 'online').pipe(map(() => true));
    const offline$ = fromEvent(window, 'offline').pipe(map(() => false));

    merge(online$, offline$)
      .pipe(distinctUntilChanged())
      .subscribe(isOnline => {
        this.isOnline$.next(isOnline);

        if (isOnline) {
          console.log('[OfflineSyncService] Conexión restaurada — auto-sync');
          // Auto-sync al recuperar conexión
          const token = localStorage.getItem('auth_token') || '';
          if (token) {
            this.syncAll(token);
          }
        }
      });
  }

  private addToStore(item: OfflineIncident): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.db) { reject('DB no inicializada'); return; }

      const tx = this.db.transaction(this.STORE_NAME, 'readwrite');
      const store = tx.objectStore(this.STORE_NAME);
      const request = store.put(item);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  private markSynced(key: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.db) { reject('DB no inicializada'); return; }

      const tx = this.db.transaction(this.STORE_NAME, 'readwrite');
      const store = tx.objectStore(this.STORE_NAME);
      const getReq = store.get(key);

      getReq.onsuccess = () => {
        if (getReq.result) {
          getReq.result.synced = true;
          store.put(getReq.result);
        }
        resolve();
      };
      getReq.onerror = () => reject(getReq.error);
    });
  }

  private async updatePendingCount(): Promise<void> {
    const pending = await this.getPendingItems();
    this.pendingCount$.next(pending.length);
  }
}

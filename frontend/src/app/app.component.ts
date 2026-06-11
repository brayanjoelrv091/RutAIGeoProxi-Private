import { Component, inject, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { CommonModule, DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { AuthService } from './modules/p1_usuarios/auth.service';
import { WebSocketService } from './modules/shared/websocket.service';
import { environment } from './environment';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive, DatePipe],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit {
  title = 'RutAIGeoProxi';
  private readonly auth = inject(AuthService);
  private readonly ws = inject(WebSocketService);
  private readonly http = inject(HttpClient);
  
  // Use config to fallback if environment is missing
  private apiUrl = environment.apiUrl;
  
  menuOpen = false;
  isDarkTheme = true;
  notifications: any[] = [];
  unreadCount = 0;
  showNotifications = false;
  isSuperadmin = false;

  ngOnInit() {
    this.isDarkTheme = localStorage.getItem('theme') !== 'light';
    this.applyTheme();
    if (this.isLoggedIn()) {
      this.requestNotificationPermission();
      this.fetchNotifications();
      this.initNotifications();
      this.checkSuperadmin();
    }
  }

  requestNotificationPermission() {
    if ('Notification' in window && Notification.permission !== 'granted' && Notification.permission !== 'denied') {
      Notification.requestPermission();
    }
  }

  checkSuperadmin() {
    if (this.userRole !== 'admin') return;
    this.auth.me().subscribe({
      next: (me) => {
        // Un superadmin real NO TIENE tenant_id y tiene rol admin
        this.isSuperadmin = me.rol === 'admin' && me.tenant_id === null;
      }
    });
  }

  fetchNotifications() {
    this.http.get<any[]>(`${this.apiUrl}/payments/notifications`, {
      headers: { Authorization: `Bearer ${this.auth.token}` }
    }).subscribe({
      next: (data) => {
        this.notifications = data;
        this.unreadCount = data.filter(n => !n.leido).length;
      },
      error: (e) => console.error('Error fetching notifications', e)
    });
  }

  deleteNotification(id: number, event: Event) {
    event.stopPropagation();
    this.http.delete(`${this.apiUrl}/payments/notifications/${id}`, {
      headers: { Authorization: `Bearer ${this.auth.token}` }
    }).subscribe({
      next: () => {
        this.notifications = this.notifications.filter(n => n.id !== id);
      },
      error: (e) => console.error('Error deleting notification', e)
    });
  }

  deleteAllNotifications() {
    if(!confirm('¿Estás seguro de borrar todas las notificaciones?')) return;
    this.http.delete(`${this.apiUrl}/payments/notifications/all`, {
      headers: { Authorization: `Bearer ${this.auth.token}` }
    }).subscribe({
      next: () => {
        this.notifications = [];
        this.unreadCount = 0;
      },
      error: (e) => console.error('Error deleting all notifications', e)
    });
  }

  yangoModalActive = false;
  latestEmergencyId: number | null = null;

  initNotifications() {
    const token = this.auth.token;
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const userId = parseInt(payload.sub, 10);
        if (userId) {
          this.ws.connectNotifications(userId).subscribe((notif) => {
            if (notif.type === 'tenant_suspended') {
              alert(notif.mensaje || 'Su cuenta ha sido suspendida debido a que la suscripción expiró o no se pagó a tiempo.');
              this.logout();
              return;
            }

            this.notifications.unshift(notif);
            this.unreadCount++;
            
            // 🔔 EXPERIENCIA YANGO: Sonido + Popup + Notificación Nativa
            const msg = (notif.mensaje || notif.message || '').toLowerCase();
            const titulo = (notif.titulo || notif.title || '').toLowerCase();
            
            if (notif.type === 'nuevo_incidente' || titulo.includes('asignación') || titulo.includes('incidente') || msg.includes('emergencia') || msg.includes('asignado')) {
              this.playAlertSound();
              this.showNativeNotification(notif.titulo || notif.title || 'Alerta', notif.mensaje || notif.message || 'Nueva emergencia detectada');
              this.yangoModalActive = true;
              
              // Extraer ID si viene en el texto (ej: incidente #42)
              const match = msg.match(/#(\d+)/);
              if (match) this.latestEmergencyId = parseInt(match[1], 10);
            }
          });
        }
      } catch (e) {
        console.error('Error parsing token for notifications', e);
      }
    }
  }

  showNativeNotification(title: string, body: string) {
    if ('Notification' in window && Notification.permission === 'granted') {
      const notification = new Notification(title, {
        body: body,
        icon: '/assets/logo.png', // Fallback opcional si tienes un icono
        requireInteraction: true // Mantiene la notificación visible hasta que interactúen
      });
      
      notification.onclick = () => {
        window.focus();
        notification.close();
      };
    }
  }

  playAlertSound() {
    try {
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      // Tono 1
      const osc1 = audioCtx.createOscillator();
      const gain1 = audioCtx.createGain();
      osc1.connect(gain1); gain1.connect(audioCtx.destination);
      osc1.type = 'square'; osc1.frequency.setValueAtTime(800, audioCtx.currentTime);
      gain1.gain.setValueAtTime(0.5, audioCtx.currentTime);
      gain1.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
      osc1.start(); osc1.stop(audioCtx.currentTime + 0.3);
      
      // Tono 2 (más alto, como sirena corta)
      setTimeout(() => {
        const osc2 = audioCtx.createOscillator();
        const gain2 = audioCtx.createGain();
        osc2.connect(gain2); gain2.connect(audioCtx.destination);
        osc2.type = 'square'; osc2.frequency.setValueAtTime(1200, audioCtx.currentTime);
        gain2.gain.setValueAtTime(0.5, audioCtx.currentTime);
        gain2.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
        osc2.start(); osc2.stop(audioCtx.currentTime + 0.3);
      }, 150);
    } catch (e) { console.warn("No audio context"); }
  }

  closeYangoModal() {
    this.yangoModalActive = false;
  }

  toggleNotifications() {
    this.showNotifications = !this.showNotifications;
    if (this.showNotifications) {
      this.unreadCount = 0;
    }
  }

  toggleTheme() {
    this.isDarkTheme = !this.isDarkTheme;
    localStorage.setItem('theme', this.isDarkTheme ? 'dark' : 'light');
    this.applyTheme();
  }

  private applyTheme() {
    document.body.classList.toggle('light-theme', !this.isDarkTheme);
  }

  isLoggedIn(): boolean {
    return this.auth.isLoggedIn();
  }

  get userRole(): string | null {
    return this.auth.getUserRole();
  }

  toggleMenu(): void {
    this.menuOpen = !this.menuOpen;
  }

  logout(): void {
    this.auth.logout();
    this.menuOpen = false;
  }
}

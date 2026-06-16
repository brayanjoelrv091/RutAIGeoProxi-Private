import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AnalyticsService, DashboardKPIs } from '../../services/analytics.service';
import { ChartConfiguration, ChartData, ChartType } from 'chart.js';
import { BaseChartDirective } from 'ng2-charts';
import { AuthService } from '../../../p1_usuarios/auth.service';
import { WebSocketService } from '../../../shared/websocket.service';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, BaseChartDirective],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit, OnDestroy {
  analyticsService = inject(AnalyticsService);
  kpis: DashboardKPIs | null = null;
  loading = true;
  refreshInterval: any;
  lastUpdated: Date | null = null;
  
  private auth = inject(AuthService);
  private ws = inject(WebSocketService);
  private wsSubscription?: Subscription;

  // Pie
  public pieChartOptions: ChartConfiguration['options'] = {
    responsive: true,
    plugins: {
      legend: { display: true, position: 'top' },
    }
  };
  public pieChartData: ChartData<'pie', number[], string | string[]> = {
    labels: [],
    datasets: [{ data: [] }]
  };
  public pieChartType: ChartType = 'pie';

  // Bar
  public barChartOptions: ChartConfiguration['options'] = {
    responsive: true,
    scales: { x: {}, y: { min: 0 } },
    plugins: {
      legend: { display: true },
    }
  };
  public barChartType: ChartType = 'bar';
  public barChartData: ChartData<'bar'> = {
    labels: [],
    datasets: []
  };

  ngOnInit(): void {
    this.loadData();
    this.refreshInterval = setInterval(() => {
      this.loadData();
    }, 30000);

    const token = this.auth.token;
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const userId = parseInt(payload.sub, 10);
        if (userId) {
          this.wsSubscription = this.ws.connectNotifications(userId).subscribe((notif: any) => {
            // Actualizar dashboard inmediatamente si hay un cambio relevante
            if (notif.type === 'nuevo_incidente' || notif.type === 'ESTADO_UPDATED' || (notif.titulo && notif.titulo.toLowerCase().includes('incidente'))) {
              this.loadData();
            }
          });
        }
      } catch (e) {
        console.error('Error suscribiéndose a notificaciones en dashboard', e);
      }
    }
  }

  ngOnDestroy(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
    if (this.wsSubscription) {
      this.wsSubscription.unsubscribe();
    }
  }

  loadData(): void {
    this.analyticsService.getDashboardKPIs().subscribe({
      next: (data) => {
        this.kpis = data;
        this.lastUpdated = new Date();
        
        // Categoria (Pie)
        const categorias = data.incidentes_por_categoria || {};
        const catKeys = Object.keys(categorias);
        if (catKeys.length > 0) {
          this.pieChartData.labels = catKeys;
          this.pieChartData.datasets[0].data = Object.values(categorias);
        } else {
          this.pieChartData.labels = ['Sin datos'];
          this.pieChartData.datasets[0].data = [1];
        }

        // Talleres Eficientes (Bar)
        const talleres = data.talleres_mas_eficientes || [];
        if (talleres.length > 0) {
          this.barChartData.labels = talleres.map(t => t.nombre);
          this.barChartData.datasets = [
            { data: talleres.map(t => t.avg_resolucion_min), label: 'Minutos Promedio', backgroundColor: '#3b82f6' }
          ];
        } else {
          this.barChartData.labels = ['Sin Talleres'];
          this.barChartData.datasets = [{ data: [0], label: 'Minutos Promedio' }];
        }

        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading KPIs', err);
        this.loading = false;
      }
    });
  }
}

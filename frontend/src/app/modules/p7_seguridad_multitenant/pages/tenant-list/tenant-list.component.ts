import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { environment } from '../../../../environment';

export interface Tenant {
  id: number;
  nombre: string;
  dominio?: string;
  estado: string;
  plan: string;
  estado_pago: string;
  metodo_pago?: string;
  checkout_url?: string;
  creado_en: string;
}

@Component({
  selector: 'app-tenant-list',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  templateUrl: './tenant-list.component.html',
  styleUrls: ['./tenant-list.component.css']
})
export class TenantListComponent implements OnInit {
  http = inject(HttpClient);
  route = inject(ActivatedRoute);
  router = inject(Router);
  tenants: Tenant[] = [];
  loading = true;

  // Variables del Modal de Upgrade
  showUpgradeModal = false;
  selectedTenant: Tenant | null = null;
  upgradePlan = 'profesional';
  upgradeMetodo = 'efectivo';
  upgradeMonto = 29;
  upgradeLoading = false;
  upgradeError = '';

  // Variables de feedback (Success Stripe)
  paymentSuccessMsg = '';

  ngOnInit() {
    this.route.queryParams.subscribe(params => {
      if (params['payment_success'] === 'true' && params['tenant_id']) {
        // Regresando de Stripe: Confirmar
        this.paymentSuccessMsg = 'Confirmando pago en línea...';
        this.http.post(`${environment.apiUrl}/tenants/${params['tenant_id']}/superadmin-upgrade-confirm`, {
          nuevo_plan: params['plan'],
          metodo_pago: 'tarjeta',
          monto_pago: parseFloat(params['monto'] || '0')
        }).subscribe({
          next: () => {
            this.paymentSuccessMsg = '¡Pago registrado y plan actualizado exitosamente!';
            setTimeout(() => { this.paymentSuccessMsg = ''; this.router.navigate(['/tenants']); }, 5000);
            this.loadTenants();
          },
          error: (err) => {
            console.error('Error confirming stripe payment:', err);
            this.upgradeError = 'Error al confirmar pago de Stripe.';
            this.paymentSuccessMsg = '';
          }
        });
      } else {
        this.loadTenants();
      }
    });
  }

  loadTenants() {
    this.loading = true;
    this.http.get<Tenant[]>(`${environment.apiUrl}/tenants`).subscribe({
      next: (data) => {
        this.tenants = data;
        this.loading = false;
      },
      error: (err) => {
        console.error(err);
        this.loading = false;
      }
    });
  }

  openUpgradeModal(tenant: Tenant) {
    this.selectedTenant = tenant;
    this.upgradePlan = tenant.plan === 'basico' ? 'profesional' : tenant.plan;
    this.updateSuggestedMonto();
    this.showUpgradeModal = true;
  }

  updateSuggestedMonto() {
    if (this.upgradePlan === 'profesional') this.upgradeMonto = 29;
    else if (this.upgradePlan === 'empresarial') this.upgradeMonto = 99;
    else this.upgradeMonto = 0;
  }

  closeUpgradeModal() {
    this.showUpgradeModal = false;
    this.selectedTenant = null;
    this.upgradeError = '';
  }

  confirmUpgrade() {
    if (!this.selectedTenant) return;
    this.upgradeLoading = true;
    this.upgradeError = '';

    const payload = {
      nuevo_plan: this.upgradePlan,
      metodo_pago: this.upgradeMetodo,
      monto_pago: this.upgradeMonto
    };

    this.http.post<Tenant>(`${environment.apiUrl}/tenants/${this.selectedTenant.id}/superadmin-upgrade`, payload)
      .subscribe({
        next: (res) => {
          if (res.checkout_url) {
            // Redirigir a Stripe
            window.location.href = res.checkout_url;
            return;
          }
          
          this.upgradeLoading = false;
          this.closeUpgradeModal();
          this.loadTenants(); // Recargar la lista
        },
        error: (err) => {
          this.upgradeError = err.error?.detail || 'Error al procesar el pago y upgrade.';
          this.upgradeLoading = false;
        }
      });
  }
}

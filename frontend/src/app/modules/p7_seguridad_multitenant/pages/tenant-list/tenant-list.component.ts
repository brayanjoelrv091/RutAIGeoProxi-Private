import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
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

  ngOnInit() {
    this.loadTenants();
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

    this.http.post(`${environment.apiUrl}/tenants/${this.selectedTenant.id}/superadmin-upgrade`, payload)
      .subscribe({
        next: () => {
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

import { Component, inject, OnInit } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { environment } from '../../../../environment';
import { AuthService } from '../../auth.service';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

interface Tenant {
  id: number;
  nombre: string;
  slug: string;
  esta_activo: boolean;
  plan: string;
  creado_en: string;
  fecha_fin_plan: string | null;
  estado_pago: string;
  metodo_pago: string;
  monto_pago: number;
  admin_nombre: string;
  admin_email: string;
  total_pagado: number;
  historial_suscripciones?: any[];
  expanded?: boolean;
}

@Component({
  selector: 'app-superadmin-saas',
  standalone: true,
  imports: [CommonModule, DatePipe],
  templateUrl: './superadmin-saas.component.html',
  styleUrls: ['./superadmin-saas.component.css'],
})
export class SuperadminSaasComponent implements OnInit {
  private readonly auth = inject(AuthService);
  
  tenants: Tenant[] = [];
  loading = true;
  error = '';
  totalRevenue = 0;

  ngOnInit(): void {
    this.fetchTenants();
  }

  async fetchTenants() {
    this.loading = true;
    try {
      const res = await fetch(`${environment.apiUrl}/admin/saas/tenants`, {
        headers: { Authorization: `Bearer ${this.auth.token}` }
      });
      if (res.ok) {
        const data = await res.json();
        this.tenants = data.map((t: Tenant) => {
          if (t.plan === 'gratis' && !t.fecha_fin_plan) {
            const date = new Date(t.creado_en);
            date.setDate(date.getDate() + 30);
            t.fecha_fin_plan = date.toISOString();
          }
          return t;
        });
        this.totalRevenue = this.tenants.reduce((acc, t) => acc + (t.total_pagado || 0), 0);
      } else {
        this.error = 'No se pudieron cargar los tenants.';
      }
    } catch (e: any) {
      this.error = 'Error de conexión.';
    } finally {
      this.loading = false;
    }
  }

  toggleHistory(tenant: Tenant) {
    tenant.expanded = !tenant.expanded;
  }

  async toggleStatus(tenant: Tenant) {
    const newStatus = !tenant.esta_activo;
    const confirmMsg = newStatus 
      ? `¿Estás seguro de ACTIVAR la suscripción de ${tenant.nombre}?` 
      : `¿Estás seguro de SUSPENDER a ${tenant.nombre}? El tenant y todos sus usuarios perderán acceso.`;
      
    if (!confirm(confirmMsg)) return;

    try {
      const res = await fetch(`${environment.apiUrl}/admin/saas/tenants/${tenant.id}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.auth.token}`
        },
        body: JSON.stringify({ esta_activo: newStatus })
      });
      
      if (res.ok) {
        const updated = await res.json();
        const idx = this.tenants.findIndex(t => t.id === tenant.id);
        if (idx !== -1) {
          this.tenants[idx] = updated;
        }
      } else {
        alert('Error al actualizar el estado del tenant.');
      }
    } catch (e) {
      alert('Error de red al actualizar estado.');
    }
  }

  exportCSV() {
    if (this.tenants.length === 0) return;
    
    const headers = ['ID', 'Empresa', 'Admin', 'Plan', 'Monto ($)', 'Método Pago', 'Estado', 'Suscripción Activa', 'F. Creación', 'F. Vencimiento'];
    const rows = this.tenants.map(t => [
      t.id,
      t.nombre,
      t.admin_nombre,
      t.plan.toUpperCase(),
      t.monto_pago,
      t.metodo_pago.toUpperCase(),
      t.estado_pago.toUpperCase(),
      t.esta_activo ? 'SI' : 'NO',
      new Date(t.creado_en).toLocaleDateString(),
      t.fecha_fin_plan ? new Date(t.fecha_fin_plan).toLocaleDateString() : 'Ilimitado'
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(e => e.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `SaaS_Historial_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  exportPDF() {
    if (this.tenants.length === 0) return;

    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text('Historial de Suscripciones SaaS', 14, 22);
    
    doc.setFontSize(11);
    doc.setTextColor(100);
    doc.text(`Generado el: ${new Date().toLocaleDateString()}`, 14, 30);

    const tableColumn = ["ID", "Empresa", "Plan", "Monto", "Estado", "Vencimiento"];
    const tableRows: any[] = [];

    this.tenants.forEach(t => {
      const row = [
        t.id,
        t.nombre,
        t.plan.toUpperCase(),
        `$${t.monto_pago}`,
        t.esta_activo ? 'ACTIVO' : 'SUSPENDIDO',
        t.fecha_fin_plan ? new Date(t.fecha_fin_plan).toLocaleDateString() : 'N/A'
      ];
      tableRows.push(row);
    });

    autoTable(doc, {
      head: [tableColumn],
      body: tableRows,
      startY: 35,
      styles: { fontSize: 10 },
      headStyles: { fillColor: [0, 242, 255], textColor: [0, 0, 0] }
    });

    doc.save(`SaaS_Historial_${new Date().toISOString().split('T')[0]}.pdf`);
  }
}

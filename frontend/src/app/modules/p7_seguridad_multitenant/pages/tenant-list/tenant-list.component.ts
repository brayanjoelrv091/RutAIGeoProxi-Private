import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environment';

export interface Tenant {
  id: number;
  nombre: string;
  dominio?: string;
  estado: string;
  creado_en: string;
}

@Component({
  selector: 'app-tenant-list',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './tenant-list.component.html',
  styleUrls: ['./tenant-list.component.css']
})
export class TenantListComponent implements OnInit {
  http = inject(HttpClient);
  tenants: Tenant[] = [];
  loading = true;

  ngOnInit() {
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
}

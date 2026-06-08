import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router, ActivatedRoute } from '@angular/router';
import { environment } from '../../../../environment';

@Component({
  selector: 'app-tenant-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './tenant-form.component.html',
  styleUrls: ['./tenant-form.component.css']
})
export class TenantFormComponent implements OnInit {
  fb = inject(FormBuilder);
  http = inject(HttpClient);
  router = inject(Router);
  route = inject(ActivatedRoute);

  tenantForm: FormGroup;
  tenantId: number | null = null;
  loading = false;
  error = '';

  constructor() {
    this.tenantForm = this.fb.group({
      nombre: ['', Validators.required],
      slug: [''],
      esta_activo: [true],
      email_admin: [''],
      plan: ['basico']
    });
  }

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.tenantId = +id;
      this.loadTenant();
    }
  }

  loadTenant() {
    this.loading = true;
    this.http.get<any>(`${environment.apiUrl}/tenants/${this.tenantId}`).subscribe({
      next: (data) => {
        this.tenantForm.patchValue(data);
        this.loading = false;
      },
      error: (err) => {
        this.error = 'Error cargando tenant';
        this.loading = false;
      }
    });
  }

  onSubmit() {
    if (this.tenantForm.invalid) return;

    this.loading = true;
    this.error = '';
    const formVal = this.tenantForm.value;

    // Auto-generar slug desde el nombre si no se proporcionó
    if (!formVal.slug || formVal.slug.trim() === '') {
      formVal.slug = formVal.nombre
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
    }

    if (this.tenantId) {
      this.http.patch(`${environment.apiUrl}/tenants/${this.tenantId}`, formVal).subscribe({
        next: () => this.router.navigate(['/tenants']),
        error: (err) => { this.error = err.error?.detail || 'Error actualizando'; this.loading = false; }
      });
    } else {
      this.http.post(`${environment.apiUrl}/tenants/`, formVal).subscribe({
        next: () => this.router.navigate(['/tenants']),
        error: (err) => { this.error = err.error?.detail || 'Error creando'; this.loading = false; }
      });
    }
  }
}


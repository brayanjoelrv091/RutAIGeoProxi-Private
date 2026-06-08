import { Component, OnInit, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AuthService, Me, Vehicle } from '../../auth.service';
import { RouterLink } from '@angular/router';
import { NgClass, UpperCasePipe } from '@angular/common';
import { WorkshopService } from '../../../p3_talleres/workshop.service';


@Component({
  selector: 'app-home',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, NgClass, UpperCasePipe],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css',
})
export class HomeComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  private readonly wsSvc = inject(WorkshopService);

  me: Me | null = null;
  workshopProfile: any = null;
  adminWorkshopsCount: number = 0;
  loadError = '';
  vehicleError = '';

  vehicleForm = this.fb.nonNullable.group({
    marca: ['', Validators.required],
    modelo: ['', Validators.required],
    placa: ['', Validators.required],
    anio: [null as number | null],
  });

  passwordForm = this.fb.nonNullable.group({
    currentPassword: ['', Validators.required],
    newPassword: ['', [
      Validators.required,
      Validators.minLength(8),
      Validators.pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d\w\W]{8,}$/)
    ]],
  });

  passError = '';
  passSuccess = '';
  passLoading = false;
  showCurrentPass = false;
  showNewPass = false;

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loadError = '';
    this.auth.me().subscribe({
      next: (m) => {
        this.me = m;
        if (this.isTaller) {
          this.wsSvc.getMyProfile().subscribe({
            next: (profile: any) => this.workshopProfile = profile,
            error: () => {} // If 404, hasn't registered a workshop yet
          });
        }
        if (this.isAdmin) {
          this.wsSvc.listMyWorkshops().subscribe({
            next: (talleres) => {
              this.adminWorkshopsCount = talleres.length;
            },
            error: () => { this.adminWorkshopsCount = 0; }
          });
        }
      },
      error: () => (this.loadError = 'No se pudo cargar el perfil.'),
    });
  }

  get isCliente(): boolean {
    return this.me?.rol === 'cliente';
  }

  get isAdmin(): boolean {
    return this.me?.rol === 'admin';
  }

  get isSuperadmin(): boolean {
    return this.me?.rol === 'admin' && this.me?.tenant_id === null;
  }

  get isTaller(): boolean {
    return this.me?.rol === 'taller';
  }

  addVehicle(): void {
    if (!this.isCliente || this.vehicleForm.invalid) return;
    const v = this.vehicleForm.getRawValue();
    this.vehicleError = '';
    this.auth
      .addVehicle({
        marca: v.marca,
        modelo: v.modelo,
        placa: v.placa,
        anio: v.anio ?? undefined,
      })
      .subscribe({
        next: () => {
          this.vehicleForm.reset({ marca: '', modelo: '', placa: '', anio: null });
          this.refresh();
        },
        error: (e) => (this.vehicleError = e?.error?.detail ?? 'No se pudo guardar el vehículo.'),
      });
  }

  removeVehicle(v: Vehicle): void {
    if (!confirm(`Eliminar ${v.placa}?`)) return;
    this.auth.deleteVehicle(v.id).subscribe({ next: () => this.refresh() });
  }

  changePassword(): void {
    if (this.passwordForm.invalid) return;
    const vals = this.passwordForm.getRawValue();
    this.passLoading = true;
    this.passError = '';
    this.passSuccess = '';
    
    this.auth.changePassword(vals.currentPassword, vals.newPassword).subscribe({
      next: (res) => {
        this.passLoading = false;
        this.passSuccess = res.message || 'Contraseña actualizada exitosamente.';
        this.passwordForm.reset();
        setTimeout(() => this.passSuccess = '', 5000);
      },
      error: (e) => {
        this.passLoading = false;
        this.passError = e.error?.detail || 'Error al actualizar contraseña.';
      }
    });
  }



  logout(): void {
    this.auth.logout();
  }
}

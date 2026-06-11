import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { WorkshopService, Workshop, Technician } from '../../../../services/workshop.service';

@Component({
  selector: 'app-tenant-workshops',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './tenant-workshops.component.html',
  styleUrl: './tenant-workshops.component.css'
})
export class TenantWorkshopsComponent implements OnInit {
  private workshopService = inject(WorkshopService);
  workshops: (Workshop & { tecnicos: Technician[] })[] = [];
  loading = true;
  error = '';

  ngOnInit() {
    this.loadWorkshops();
  }

  loadWorkshops() {
    this.loading = true;
    this.workshopService.getTenantWorkshops().subscribe({
      next: (data) => {
        this.workshops = data;
        this.loading = false;
      },
      error: (err) => {
        console.error(err);
        this.error = 'Error al cargar los talleres. Por favor intenta de nuevo.';
        this.loading = false;
      }
    });
  }
}

import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../../environments/environment';
import { ActivatedRoute, Router } from '@angular/router';

@Component({
  selector: 'app-cotizacion-form',
  template: `
    <div class="p-6 max-w-4xl mx-auto bg-white rounded-xl shadow-md">
      <h2 class="text-2xl font-bold mb-4 text-slate-800">Generar Cotización (Taller)</h2>
      
      <form [formGroup]="cotizacionForm" (ngSubmit)="onSubmit()">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-700">Notas Adicionales</label>
          <textarea formControlName="notas" class="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"></textarea>
        </div>

        <div class="mb-4">
          <h3 class="text-lg font-semibold text-slate-700 border-b pb-2">Ítems de Reparación</h3>
          <div formArrayName="items" class="mt-4 space-y-4">
            <div *ngFor="let item of items.controls; let i=index" [formGroupName]="i" class="flex gap-4 items-end bg-slate-50 p-4 rounded-lg">
              
              <div class="flex-1">
                <label class="block text-sm font-medium text-slate-700">Descripción</label>
                <input type="text" formControlName="descripcion" class="mt-1 block w-full rounded-md border-slate-300">
              </div>
              
              <div class="w-24">
                <label class="block text-sm font-medium text-slate-700">Cantidad</label>
                <input type="number" formControlName="cantidad" min="1" class="mt-1 block w-full rounded-md border-slate-300">
              </div>
              
              <div class="w-32">
                <label class="block text-sm font-medium text-slate-700">Precio Unit. ($)</label>
                <input type="number" formControlName="precio_unitario" step="0.01" min="0" class="mt-1 block w-full rounded-md border-slate-300">
              </div>
              
              <button type="button" (click)="removeItem(i)" class="mb-1 px-3 py-2 bg-red-100 text-red-600 rounded hover:bg-red-200">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
              </button>
            </div>
          </div>
          
          <button type="button" (click)="addItem()" class="mt-4 px-4 py-2 border border-dashed border-indigo-500 text-indigo-600 rounded-lg hover:bg-indigo-50 font-medium">
            + Añadir Repuesto/Servicio
          </button>
        </div>

        <!-- Cálculo en vivo UI (No se envía, Backend recalcula) -->
        <div class="bg-indigo-50 p-4 rounded-lg mt-6 text-right">
            <p class="text-sm text-slate-500">Subtotal estimado: {{ calcularSubtotal() | currency }}</p>
            <p class="text-sm text-slate-500">IVA (16%): {{ calcularSubtotal() * 0.16 | currency }}</p>
            <p class="text-xl font-bold text-indigo-900 mt-2">TOTAL ESTIMADO: {{ calcularSubtotal() * 1.16 | currency }}</p>
        </div>

        <div class="mt-8 flex justify-end">
          <button type="submit" [disabled]="cotizacionForm.invalid || items.length === 0 || loading" 
            class="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50">
            {{ loading ? 'Enviando...' : 'Enviar Cotización al Cliente' }}
          </button>
        </div>
      </form>
    </div>
  `
})
export class CotizacionFormComponent implements OnInit {
  cotizacionForm: FormGroup;
  incidenteId: number = 0;
  loading = false;

  constructor(private fb: FormBuilder, private http: HttpClient, private route: ActivatedRoute, private router: Router) {
    this.cotizacionForm = this.fb.group({
      notas: [''],
      items: this.fb.array([])
    });
  }

  ngOnInit() {
    this.route.params.subscribe(params => {
      this.incidenteId = +params['incident_id'];
    });
    this.addItem(); // Un item por defecto
  }

  get items() {
    return this.cotizacionForm.get('items') as FormArray;
  }

  addItem() {
    this.items.push(this.fb.group({
      descripcion: ['', Validators.required],
      cantidad: [1, [Validators.required, Validators.min(1)]],
      precio_unitario: [0.00, [Validators.required, Validators.min(0)]]
    }));
  }

  removeItem(index: number) {
    this.items.removeAt(index);
  }

  calcularSubtotal(): number {
    return this.items.controls.reduce((acc, control) => {
      const val = control.value;
      return acc + (val.cantidad * val.precio_unitario);
    }, 0);
  }

  onSubmit() {
    if (this.cotizacionForm.invalid || this.items.length === 0) return;
    this.loading = true;

    const payload = {
      incidente_id: this.incidenteId,
      notas: this.cotizacionForm.value.notas,
      items: this.cotizacionForm.value.items
    };

    // Al hacer POST, el backend FastAPI recalculará los Decimales y emitirá el WebSocket
    this.http.post(`${environment.apiUrl}/analytics/quotations_manual`, payload)
      .subscribe({
        next: (res) => {
          this.loading = false;
          alert('Cotización enviada al cliente.');
          this.router.navigate(['/talleres/incidentes', this.incidenteId]);
        },
        error: (err) => {
          console.error(err);
          alert('Error al enviar la cotización');
          this.loading = false;
        }
      });
  }
}

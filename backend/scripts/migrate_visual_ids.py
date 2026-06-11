import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'rutaigeoproxi.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def column_exists(table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

# Incidentes
if not column_exists('incidentes', 'tenant_secuencia'):
    cursor.execute("ALTER TABLE incidentes ADD COLUMN tenant_secuencia INTEGER")
    print("Added tenant_secuencia to incidentes")
if not column_exists('incidentes', 'codigo_visual'):
    cursor.execute("ALTER TABLE incidentes ADD COLUMN codigo_visual VARCHAR(20)")
    print("Added codigo_visual to incidentes")

# Bitacora
if not column_exists('bitacora', 'tenant_id'):
    cursor.execute("ALTER TABLE bitacora ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE")
    print("Added tenant_id to bitacora")
if not column_exists('bitacora', 'tenant_secuencia'):
    cursor.execute("ALTER TABLE bitacora ADD COLUMN tenant_secuencia INTEGER")
    print("Added tenant_secuencia to bitacora")
if not column_exists('bitacora', 'codigo_visual'):
    cursor.execute("ALTER TABLE bitacora ADD COLUMN codigo_visual VARCHAR(20)")
    print("Added codigo_visual to bitacora")

# Populate existing incidentes
cursor.execute("SELECT id, tenant_id FROM incidentes ORDER BY creado_en ASC")
incidentes = cursor.fetchall()
tenant_seq_inc = {}
for inc_id, tenant_id in incidentes:
    if tenant_id not in tenant_seq_inc:
        tenant_seq_inc[tenant_id] = 1
    else:
        tenant_seq_inc[tenant_id] += 1
    seq = tenant_seq_inc[tenant_id]
    code = f"INC-{seq:04d}"
    cursor.execute("UPDATE incidentes SET tenant_secuencia = ?, codigo_visual = ? WHERE id = ?", (seq, code, inc_id))

# Populate existing bitacora
# First, link tenant_id from usuarios
cursor.execute("UPDATE bitacora SET tenant_id = (SELECT tenant_id FROM usuarios WHERE usuarios.id = bitacora.usuario_id) WHERE usuario_id IS NOT NULL")

cursor.execute("SELECT id, tenant_id FROM bitacora ORDER BY creado_en ASC")
bitacoras = cursor.fetchall()
tenant_seq_bit = {}
for bit_id, tenant_id in bitacoras:
    if tenant_id not in tenant_seq_bit:
        tenant_seq_bit[tenant_id] = 1
    else:
        tenant_seq_bit[tenant_id] += 1
    seq = tenant_seq_bit[tenant_id]
    code = f"BIT-{seq:04d}" if tenant_id else f"SYS-{seq:04d}"
    cursor.execute("UPDATE bitacora SET tenant_secuencia = ?, codigo_visual = ? WHERE id = ?", (seq, code, bit_id))

conn.commit()
conn.close()
print("Migration completed successfully.")

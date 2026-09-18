"""Prepare explicit income registration without coupling work totals to balances."""
from .cloud_bridge import initialize_cloud_ids


def income_draft(db, kind, record_id):
    if kind not in ('trip', 'extra'):raise ValueError('Tipo de trabajo inválido.')
    record=db.work_trip(record_id) if kind=='trip' else db.work_extra(record_id)
    if not record:raise ValueError('El registro ya no existe.')
    amount=float(record.get('charged' if kind=='trip' else 'amount') or 0)
    if amount<=0:raise ValueError('Cargá primero un importe cobrado mayor a cero.')
    initialize_cloud_ids(db)
    table='work_trips' if kind=='trip' else 'work_extras'
    source='work_'+kind
    with db.connect() as con:
        identity=con.execute('SELECT remote_id FROM cloud_identity WHERE entity=? AND local_id=?',(table,str(record_id))).fetchone()[0]
        if con.execute('SELECT id FROM transactions WHERE source=? AND external_id=?',(source,identity)).fetchone():
            raise ValueError('Este registro ya tiene un ingreso en Movimientos. Editá ese ingreso para modificarlo.')
    name=record.get('client' if kind=='trip' else 'app_name') or ''
    return dict(kind='income',amount=amount,tx_date=record['trip_date' if kind=='trip' else 'work_date'],
                description=('Viaje' if kind=='trip' else 'Extra')+' · '+name,
                note=record.get('details') or '',source=source,external_id=identity)

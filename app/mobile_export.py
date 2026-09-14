"""Exportación explícita para Móvil. No incluye credenciales ni modifica SQLite."""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone

TABLES = ('accounts', 'categories', 'transactions', 'budgets', 'recurring_transactions',
    'card_installment_plans', 'account_adjustments', 'imported_movements', 'import_rules',
    'historical_imports', 'historical_monthly', 'flex_zones', 'flex_zone_rates', 'flex_deliveries',
    'flex_income_links', 'work_trips', 'work_trip_destinations', 'work_extras', 'work_day_mileage',
    'work_field_definitions', 'work_trip_field_values', 'work_rate_schemes', 'work_rate_options')

def cents(value):
    return int((Decimal(str(value or 0))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def export_mobile(db):
    with db.connect() as con:
        con.execute('BEGIN')
        tables = {name: [dict(row) for row in con.execute(f'SELECT * FROM {name}')] for name in TABLES}
    identity = lambda table, value: f'desktop:{table}:{value}' if value is not None else ''
    def ref(table, value): return identity(table, value)
    def base(row, table): return {'id':ref(table,row['id']), 'desktop':row}
    def tx(row):
        return dict(kind=row['kind'], amount=cents(row['amount']), account=ref('accounts',row['account_id']),
            to=ref('accounts',row.get('to_account_id')),category=ref('categories',row.get('category_id')),
            description=row.get('description',''),note=row.get('note',''),tags=row.get('tags',''))
    s = {'format':'app-gastos-mobile','schema':1,'exported_at':datetime.now(timezone.utc).isoformat(),
         'desktop_snapshot':tables, 'accounts':[], 'categories':[], 'transactions':[], 'trips':[],
         'extras':[], 'mileage':[], 'zones':[], 'deliveries':[], 'recurring':[], 'installments':[],
         'budgets':[], 'review':[], 'adjustments':[], 'workFields':[]}
    for a in tables['accounts']:
        s['accounts'].append({**base(a,'accounts'),'name':a['name'],'type':a['type'],'initial':cents(a['opening_balance']),
            'color':a['color'],'icon':{'Ahorro':'piggy-bank','Efectivo':'coins','Tarjeta':'card','Banco':'bank'}.get(a['type'],'wallet'),
            'include':bool(a['include_in_balance']),'archived':bool(a['archived']),'credit_limit':cents(a['credit_limit']),
            'closing_day':a['closing_day'],'due_day':a['due_day']})
    for c in tables['categories']:
        s['categories'].append({**base(c,'categories'),'name':c['name'],'kind':c['kind'],'parent':ref('categories',c['parent_id']),
            'color':c['color'],'secondary_color':c.get('secondary_color'),'icon':c['icon']})
    for t in tables['transactions']:s['transactions'].append({**base(t,'transactions'),**tx(t),'date':t['tx_date']})
    for a in tables['account_adjustments']:s['adjustments'].append({**base(a,'account_adjustments'),'account':ref('accounts',a['account_id']),'amount':cents(a['amount']),'date':a['adjustment_date']})
    for r in tables['recurring_transactions']:
        s['recurring'].append({**base(r,'recurring_transactions'),**tx(r),'next_date':r['next_date'],'frequency':r['frequency'],
            'interval':r['interval_value'],'anchor':r.get('anchor_day') or int(r['next_date'][8:10]),'active':bool(r['active'])})
    for p in tables['card_installment_plans']:
        s['installments'].append({**base(p,'card_installment_plans'),'account':ref('accounts',p['account_id']),
            'category':ref('categories',p['category_id']),'total':cents(p['total_amount']),'count':p['installments'],
            'first_date':p['purchase_date'],'next_date':p['next_installment_date'],'base':cents(p['base_amount']),'next_number':p['next_number'],'description':p['description'],'note':p['note'],'active':bool(p['active'])})
    for b in tables['budgets']:s['budgets'].append({**base(b,'budgets'),'name':b['name'],'amount':cents(b['amount']),
        'date':b['start_date'],'account':ref('accounts',b['account_id']),'category':ref('categories',b['category_id']),'active':bool(b['active'])})
    for t in tables['work_trips']:
        destinations=sorted((d for d in tables['work_trip_destinations'] if d['trip_id']==t['id']),key=lambda d:d['position'])
        values={ref('work_field_definitions',v['field_id']):v['value_bool'] if v['value_bool'] is not None else v['value_number'] if v['value_number'] is not None else v['value_text'] for v in tables['work_trip_field_values'] if v['trip_id']==t['id']}
        s['trips'].append({**base(t,'work_trips'),'client':t['client'] or 'Sin cliente','origin':t['origin'],'date':t['trip_date'],
            'destinations':[d['destination'] for d in destinations],'stops':t['stop_count'],'trip_count':t['trip_count'],
            'amount':cents(t['charged']),'bulky':bool(t['bulky']),'rain':bool(t['rain']),'flex':bool(t['flex']),
            'own':bool(t['own_client']),'note':t['details'],'custom':values})
    for e in tables['work_extras']:s['extras'].append({**base(e,'work_extras'),'app':e['app_name'] or 'Otra app','date':e['work_date'],
        'minutes':round(e['hours']*60),'orders':e['orders'],'amount':cents(e['amount']),'note':e['details']})
    for m in tables['work_day_mileage']:
        # Registros parciales permanecen en desktop_snapshot; no se inventa un odómetro.
        if m['odometer_start'] is not None and m['odometer_end'] is not None:
            s['mileage'].append({'id':ref('mileage',m['work_date']),'date':m['work_date'],'start':m['odometer_start'],'end':m['odometer_end'],'desktop':m})
    for z in tables['flex_zones']:
        rates=sorted((r for r in tables['flex_zone_rates'] if r['zone_id']==z['id']),key=lambda r:r['effective_from'])
        s['zones'].append({**base(z,'flex_zones'),'name':z['name'],'color':z['color'],'rate':cents(rates[-1]['price']) if rates else 0})
    for d in tables['flex_deliveries']:s['deliveries'].append({**base(d,'flex_deliveries'),'zone':ref('flex_zones',d['zone_id']),
        'date':d['week_start'],'quantity':d['quantity'],'amount':cents(d['unit_price'])*d['quantity']})
    for f in tables['work_field_definitions']:
        if not f['built_in_key']:
            import json
            s['workFields'].append({**base(f,'work_field_definitions'),'name':f['label'],'type':({'select':'options','phone':'tel'}.get(f['ui_type'],f['ui_type']) or f['field_type']),
                'options':','.join(map(str,json.loads(f['options_json'] or '[]'))),'active':bool(f['active']),'summary':bool(f['show_in_summary'])})
    for r in tables['imported_movements']:
        if r['status']=='pending':s['review'].append({**base(r,'imported_movements'),**tx(r),'date':r['tx_date']})
    return s

"""Explicit cloud adapter. All writes use one SQLite transaction; no credentials here."""
import copy
import json
import uuid
from datetime import date, timedelta
from .mobile_export import export_mobile, TABLES

KINDS={'accounts':'accounts','categories':'categories','recurring':'recurring_transactions',
       'installments':'card_installment_plans','transactions':'transactions','budgets':'budgets',
       'adjustments':'account_adjustments','workFields':'work_field_definitions','trips':'work_trips',
       'extras':'work_extras','mileage':'mileage','zones':'flex_zones','deliveries':'flex_deliveries'}

def initialize_cloud_ids(db):
    with db.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS cloud_identity (entity TEXT NOT NULL, local_id TEXT NOT NULL, remote_id TEXT NOT NULL UNIQUE, PRIMARY KEY(entity,local_id))')
        c.execute('CREATE TABLE IF NOT EXISTS cloud_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        for table in TABLES:
            column='work_date' if table=='work_day_mileage' else 'id'
            # Detail records don't need identities, but assigning them is harmless.
            if table=='work_trip_field_values': continue
            for row in c.execute(f'SELECT {column} FROM {table}').fetchall():
                entity='mileage' if table=='work_day_mileage' else table
                c.execute('INSERT OR IGNORE INTO cloud_identity VALUES (?,?,?)',(entity,str(row[0]),str(uuid.uuid4())))

def meta(db,key,default=None):
    with db.connect() as c:
        row=c.execute('SELECT value FROM cloud_meta WHERE key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else default

def put_meta(c,key,value):
    c.execute('INSERT INTO cloud_meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value,ensure_ascii=False)))

def export_cloud(db, initialize=True):
    if initialize: initialize_cloud_ids(db)
    with db.connect() as c:
        ids={(r['entity'],r['local_id']):r['remote_id'] for r in c.execute('SELECT * FROM cloud_identity')}
    def identity(table,value):
        return ids[(table,str(value))] if value is not None else ''
    result=export_mobile(db,identity)
    # The snapshot is retained for Desktop-only features but isn't executable input.
    result.pop('exported_at',None)
    for key in KINDS:
        for row in result[key]: row.pop('desktop',None)
    overlay=meta(db,'overlay',{})
    result['review']=overlay.get('review',result['review'])
    for row in result['desktop_snapshot'].get('historical_monthly',[]):
        row['_cloud_category']=ids.get(('categories',str(row.get('category_id'))),'')
    for delivery in result['deliveries']:
        saved=next((r for r in overlay.get('deliveries',[]) if r['id']==delivery['id']),{})
        if saved.get('date'):
            d=date.fromisoformat(saved['date'])
            if (d-timedelta(days=d.weekday())).isoformat()==delivery['date']:delivery['date']=saved['date']
    for account in result['accounts']:
        saved=next((a for a in overlay.get('accounts',[]) if a['id']==account['id']),{})
        if saved.get('icon'): account['icon']=saved['icon']
    return result

def merge_copies(base,local,remote):
    merged=copy.deepcopy(local);conflicts=[]
    for key in [*KINDS,'review']:
        b={r['id']:r for r in (base or {}).get(key,[])};l={r['id']:r for r in local.get(key,[])};r={v['id']:v for v in remote.get(key,[])}
        result=[]
        for identity in dict.fromkeys([*l,*r,*b]):
            before,left,right=b.get(identity),l.get(identity),r.get(identity)
            if left==right: value=left
            elif left==before: value=right
            elif right==before: value=left
            else: conflicts.append((key,identity));value=left
            if value is not None:result.append(copy.deepcopy(value))
        merged[key]=result
    old=(base or {}).get('desktop_snapshot');left=local.get('desktop_snapshot');right=remote.get('desktop_snapshot')
    if left==old:merged['desktop_snapshot']=copy.deepcopy(right)
    elif right!=old and left!=right:conflicts.append(('desktop_snapshot','historial'))
    return merged,conflicts

def apply_cloud(db,document,expected,base,revision):
    """Only apply if Desktop has not changed during the network exchange."""
    if document.get('format')!='app-gastos-mobile' or document.get('schema')!=1:raise ValueError('Copia incompatible.')
    for key in KINDS:
        rows=document.get(key)
        if not isinstance(rows,list) or len({r['id'] for r in rows})!=len(rows):raise ValueError('Registros inválidos.')
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if export_cloud(db, initialize=False)!=expected:raise ValueError('Hubo cambios en Desktop durante la sincronización. Reintentá.')
        c.execute('PRAGMA defer_foreign_keys=ON')
        ids={(r['entity'],r['remote_id']):r['local_id'] for r in c.execute('SELECT * FROM cloud_identity')}
        def ref(entity,identity):
            if not identity:return None
            value=ids.get((entity,identity))
            if value is None:raise ValueError('Referencia inexistente: '+entity)
            return value if entity=='mileage' else int(value)
        def amount(v):
            if not isinstance(v,int) or isinstance(v,bool) or abs(v)>=10**14:raise ValueError('Importe inválido.')
            return v/100
        def day(value):date.fromisoformat(value);return value
        def week(value):d=date.fromisoformat(value);return (d-timedelta(days=d.weekday())).isoformat()
        def save(table,row,values):
            remote_id=row['id'];local=ids.get((table,remote_id));names=list(values)
            collection=next((k for k,v in KINDS.items() if v==table),None)
            if local and collection and previous[collection].get(remote_id)==row:return int(local)
            if local:
                c.execute(f"UPDATE {table} SET "+','.join(n+'=?' for n in names)+' WHERE id=?',(*values.values(),local))
            else:
                local=c.execute(f"INSERT INTO {table} ("+','.join(names)+') VALUES ('+','.join('?' for _ in names)+')',tuple(values.values())).lastrowid
                c.execute('INSERT INTO cloud_identity VALUES (?,?,?)',(table,str(local),remote_id));ids[(table,remote_id)]=str(local)
            return int(local)
        previous={k:{r['id']:r for r in expected[k]} for k in KINDS}
        # Release unique names only for rows explicitly removed by this replacement.
        for key,table in [('accounts','accounts'),('zones','flex_zones')]:
            keep={r['id'] for r in document[key]}
            for row in expected[key]:
                if row['id'] not in keep:
                    c.execute(f'UPDATE {table} SET name=? WHERE id=?',('__sync_removed_'+str(uuid.uuid4()),ref(table,row['id'])))
        if len({r['date'] for r in document['mileage']})!=len(document['mileage']):raise ValueError('Kilometrajes duplicados para el mismo día.')
        for a in document['accounts']:
            save('accounts',a,dict(name=a['name'],type=a.get('type','Cuenta'),opening_balance=amount(a['initial']),color=a.get('color','#7264FF'),include_in_balance=int(a.get('include',True)),archived=int(a.get('archived',False)),credit_limit=amount(a.get('credit_limit') or 0),closing_day=a.get('closing_day') or None,due_day=a.get('due_day') or None))
        pending=list(document['categories']);seen=set()
        while pending:
            progress=False
            for r in pending[:]:
                if r.get('parent') and r['parent'] not in seen:continue
                save('categories',r,dict(name=r['name'],kind=r['kind'],parent_id=ref('categories',r.get('parent')),color=r.get('color','#7264FF'),secondary_color=r.get('secondary_color'),icon=r.get('icon','other')))
                seen.add(r['id']);pending.remove(r);progress=True
            if not progress:raise ValueError('Jerarquía de categorías inválida.')
        for key,table in [('recurring','recurring_transactions'),('installments','card_installment_plans'),('budgets','budgets')]:
            for r in document[key]:
                v=dict(account_id=ref('accounts',r.get('account')),category_id=ref('categories',r.get('category')),active=int(r.get('active',True)))
                if key=='recurring':v.update(kind=r['kind'],amount=amount(r['amount']),to_account_id=ref('accounts',r.get('to')),description=r.get('description',''),note=r.get('note',''),tags=r.get('tags',''),frequency=r['frequency'],interval_value=r.get('interval',1),next_date=day(r['next_date']),anchor_day=r.get('anchor'))
                elif key=='installments':
                    if not r.get('next_date'):
                        import calendar
                        first=date.fromisoformat(r['first_date']); months=first.year*12+first.month-1+r['next_number']-1; y,m=divmod(months,12); r={**r,'next_date':date(y,m+1,min(first.day,calendar.monthrange(y,m+1)[1])).isoformat()}
                    v.update(total_amount=amount(r['total']),installments=r['count'],base_amount=amount(r.get('base',r['total']//r['count'])),purchase_date=day(r['first_date']),next_installment_date=day(r['next_date']),next_number=r['next_number'],description=r.get('description',''),note=r.get('note',''))
                else:v.update(name=r['name'],amount=amount(r['amount']),start_date=day(r['date']))
                save(table,r,v)
        for r in document['transactions']:
            origin=r.get('work_origin')
            if origin and (not isinstance(origin,dict) or origin.get('source') not in ('work_trip','work_extra') or not isinstance(origin.get('id'),str) or not origin['id']):
                raise ValueError('Vínculo de ingreso inválido.')
            save('transactions',r,dict(kind=r['kind'],amount=amount(r['amount']),account_id=ref('accounts',r['account']),to_account_id=ref('accounts',r.get('to')),category_id=ref('categories',r.get('category')),tx_date=day(r['date']),description=r.get('description',''),note=r.get('note',''),tags=r.get('tags',''),recurring_id=ref('recurring_transactions',r.get('recurring')),installment_plan_id=ref('card_installment_plans',r.get('installment')),installment_number=r.get('number')))
            if origin:
                c.execute('UPDATE transactions SET source=?,external_id=? WHERE id=?',(origin['source'],origin['id'],ref('transactions',r['id'])))
        for r in document['adjustments']:
            save('account_adjustments',r,dict(account_id=ref('accounts',r['account']),amount=amount(r['amount']),adjustment_date=day(r['date'])))
        for i,r in enumerate(document['workFields']):
            t=r['type'];save('work_field_definitions',r,dict(key='cloud_'+r['id'],label=r['name'],field_type=t if t in ['check','number','money'] else 'text',ui_type={'options':'select','tel':'phone'}.get(t,t),options_json=json.dumps(r.get('options','').split(',')),active=int(r.get('active',True)),show_in_summary=int(r.get('summary',True)),sort_order=i))
        for r in document['trips']:
            tid=save('work_trips',r,dict(client=r['client'],origin=r.get('origin',''),trip_date=day(r['date']),week_start=week(r['date']),trip_count=r.get('trip_count',1),stop_count=r['stops'],bulky=int(r.get('bulky',False)),rain=int(r.get('rain',False)),flex=int(r.get('flex',False)),own_client=int(r.get('own',False)),details=r.get('note',''),charged=amount(r['amount'])))
            if previous['trips'].get(r['id'])!=r:
                c.execute('DELETE FROM work_trip_destinations WHERE trip_id=?',(tid,))
                c.executemany('INSERT INTO work_trip_destinations(trip_id,position,destination) VALUES (?,?,?)',[(tid,i,v) for i,v in enumerate(r['destinations'])])
                for field in document['workFields']:
                    value=r.get('custom',{}).get(field['id']);fid=ref('work_field_definitions',field['id']);c.execute('DELETE FROM work_trip_field_values WHERE trip_id=? AND field_id=?',(tid,fid))
                    if value is not None:
                        t=field['type'];c.execute('INSERT INTO work_trip_field_values VALUES (?,?,?,?,?)',(tid,fid,str(value) if t not in ['check','number','money'] else None,float(value) if t in ['number','money'] and value!='' else None,int(bool(value)) if t=='check' else None))
        for r in document['extras']:save('work_extras',r,dict(app_name=r['app'],work_date=day(r['date']),week_start=week(r['date']),hours=r['minutes']/60,orders=r['orders'],amount=amount(r['amount']),details=r.get('note','')))
        for r in document['mileage']:
            if previous['mileage'].get(r['id'])==r:continue
            d=day(r['date']);c.execute('INSERT INTO work_day_mileage(work_date,week_start,odometer_start,odometer_end) VALUES (?,?,?,?) ON CONFLICT(work_date) DO UPDATE SET odometer_start=excluded.odometer_start,odometer_end=excluded.odometer_end',(d,week(d),r['start'],r['end']))
            c.execute('INSERT OR IGNORE INTO cloud_identity VALUES (?,?,?)',('mileage',d,r['id']))
        for r in document['zones']:
            zid=save('flex_zones',r,dict(name=r['name'],color=r.get('color','#7264FF')))
            for rate in r.get('rates',[{'date':'1900-01-01','amount':r['rate']}]):c.execute('INSERT INTO flex_zone_rates(zone_id,effective_from,price) VALUES (?,?,?) ON CONFLICT(zone_id,effective_from) DO UPDATE SET price=excluded.price',(zid,day(rate['date']),amount(rate['amount'])))
        for r in document['deliveries']:
            q=r.get('quantity',1)
            if q<1 or r['amount']%q:raise ValueError('Lote de Flex con importe indivisible.')
            save('flex_deliveries',r,dict(zone_id=ref('flex_zones',r['zone']),week_start=week(r['date']),quantity=q,unit_price=amount(r['amount']//q)))
        # Children first. SQLite foreign keys reject deletions still used elsewhere.
        for key in ['deliveries','mileage','extras','trips','workFields','adjustments','transactions','budgets','installments','recurring','categories','zones','accounts']:
            table=KINDS[key];keep={r['id'] for r in document[key]};deleted=[r for r in expected[key] if r['id'] not in keep]
            if key=='categories':deleted.reverse()
            for row in deleted:
                local=ref(table,row['id'])
                if key=='mileage':c.execute('DELETE FROM work_day_mileage WHERE work_date=?',(local,))
                else:c.execute(f'DELETE FROM {table} WHERE id=?',(local,))
        put_meta(c,'overlay',document);put_meta(c,'base',base);put_meta(c,'revision',revision)

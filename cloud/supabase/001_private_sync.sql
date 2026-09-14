-- Run only in the App Gastos Supabase project. No service-role key in clients.
create table if not exists public.app_gastos_copies (
  user_id uuid primary key references auth.users(id) on delete cascade,
  revision bigint not null default 1,
  operation_id uuid not null,
  document jsonb not null,
  updated_at timestamptz not null default now(),
  check (jsonb_typeof(document) = 'object'),
  check (octet_length(document::text) <= 10485760)
);
alter table public.app_gastos_copies enable row level security;
revoke all on public.app_gastos_copies from anon, authenticated;
grant select on public.app_gastos_copies to authenticated;
drop policy if exists own_copy on public.app_gastos_copies;
create policy own_copy on public.app_gastos_copies for select to authenticated
using ((select auth.uid()) = user_id);

-- Atomic compare-and-swap. A lost response can be retried with the same operation.
create or replace function public.save_app_gastos_copy(expected_revision bigint, request_id uuid, payload jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare current_row public.app_gastos_copies; caller uuid := auth.uid();
begin
  if caller is null then raise exception 'Authentication required' using errcode='28000'; end if;
  if request_id is null or expected_revision is null or expected_revision < 0
     or payload is null or jsonb_typeof(payload) <> 'object'
     or payload->>'format' is distinct from 'app-gastos-mobile'
     or payload->>'schema' is distinct from '1'
     or octet_length(payload::text) > 10485760 then
    raise exception 'Invalid sync request';
  end if;
  -- Serialize the very first insert as well as subsequent updates for this user.
  perform pg_advisory_xact_lock(hashtextextended(caller::text,0));
  select * into current_row from public.app_gastos_copies where user_id=caller for update;
  if found then
    if current_row.operation_id=request_id then
      if current_row.document <> payload then raise exception 'Operation reused with different content'; end if;
      return jsonb_build_object('ok',true,'revision',current_row.revision);
    end if;
    if current_row.revision <> expected_revision then
      return jsonb_build_object('ok',false,'conflict',true,'revision',current_row.revision);
    end if;
    update public.app_gastos_copies set document=payload, revision=revision+1,
      operation_id=request_id,updated_at=now() where user_id=caller returning * into current_row;
  else
    if expected_revision <> 0 then return jsonb_build_object('ok',false,'conflict',true,'revision',0); end if;
    insert into public.app_gastos_copies(user_id,operation_id,document)
      values(caller,request_id,payload) returning * into current_row;
  end if;
  return jsonb_build_object('ok',true,'revision',current_row.revision);
end $$;
revoke all on function public.save_app_gastos_copy(bigint,uuid,jsonb) from public, anon;
grant execute on function public.save_app_gastos_copy(bigint,uuid,jsonb) to authenticated;

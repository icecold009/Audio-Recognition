-- API quota state is server-only. The client identifier is an HMAC digest,
-- never a raw IP address or another user-supplied identifier.
create table if not exists public.api_usage (
    client_id_hash text primary key
        check (client_id_hash ~ '^[0-9a-f]{64}$'),
    daily_period date not null,
    daily_count integer not null default 0
        check (daily_count >= 0),
    monthly_period date not null,
    monthly_count integer not null default 0
        check (monthly_count >= 0),
    last_request_at timestamptz,
    updated_at timestamptz not null default now()
);

alter table public.api_usage enable row level security;
revoke all on table public.api_usage from public, anon, authenticated;
grant select, insert, update on table public.api_usage to service_role;

-- PostgREST resolves RPC names in exposed schemas. These functions remain in
-- public for that resolution, but execution is restricted to service_role.
-- SECURITY INVOKER means the caller's explicit table grants are required.
create or replace function public.check_api_quota(
    p_client_id_hash text,
    p_daily_limit integer,
    p_monthly_limit integer,
    p_cooldown_seconds integer,
    p_now timestamptz default now()
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, public
as $$
declare
    current_day date := (p_now at time zone 'UTC')::date;
    current_month date := date_trunc('month', p_now at time zone 'UTC')::date;
    usage_row public.api_usage%rowtype;
    current_daily_count integer;
    current_monthly_count integer;
    retry_after integer;
begin
    if p_client_id_hash is null or p_client_id_hash !~ '^[0-9a-f]{64}$' then
        raise exception using message = 'invalid quota configuration';
    end if;
    if p_daily_limit <= 0 or p_monthly_limit <= 0 or p_cooldown_seconds < 0 then
        raise exception using message = 'invalid quota configuration';
    end if;

    select * into usage_row
      from public.api_usage
     where client_id_hash = p_client_id_hash;

    if not found then
        return jsonb_build_object('allowed', true);
    end if;

    current_daily_count := case when usage_row.daily_period = current_day
        then usage_row.daily_count else 0 end;
    current_monthly_count := case when usage_row.monthly_period = current_month
        then usage_row.monthly_count else 0 end;

    if usage_row.last_request_at is not null
       and p_now < usage_row.last_request_at + make_interval(secs => p_cooldown_seconds) then
        retry_after := greatest(1, ceil(extract(epoch from (
            usage_row.last_request_at + make_interval(secs => p_cooldown_seconds) - p_now
        )))::integer);
        return jsonb_build_object('allowed', false, 'reason', 'cooldown',
            'retry_after_seconds', retry_after);
    end if;

    if current_daily_count >= p_daily_limit then
        retry_after := greatest(1, ceil(extract(epoch from (
            date_trunc('day', p_now at time zone 'UTC') + interval '1 day'
            - (p_now at time zone 'UTC')
        )))::integer);
        return jsonb_build_object('allowed', false, 'reason', 'daily_limit',
            'retry_after_seconds', retry_after);
    end if;

    if current_monthly_count >= p_monthly_limit then
        retry_after := greatest(1, ceil(extract(epoch from (
            date_trunc('month', p_now at time zone 'UTC') + interval '1 month'
            - (p_now at time zone 'UTC')
        )))::integer);
        return jsonb_build_object('allowed', false, 'reason', 'monthly_limit',
            'retry_after_seconds', retry_after);
    end if;

    return jsonb_build_object('allowed', true);
end;
$$;

create or replace function public.consume_api_quota(
    p_client_id_hash text,
    p_daily_limit integer,
    p_monthly_limit integer,
    p_cooldown_seconds integer,
    p_now timestamptz default now()
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog, public
as $$
declare
    current_day date := (p_now at time zone 'UTC')::date;
    current_month date := date_trunc('month', p_now at time zone 'UTC')::date;
    usage_row public.api_usage%rowtype;
    current_daily_count integer;
    current_monthly_count integer;
    retry_after integer;
begin
    if p_client_id_hash is null or p_client_id_hash !~ '^[0-9a-f]{64}$' then
        raise exception using message = 'invalid quota configuration';
    end if;
    if p_daily_limit <= 0 or p_monthly_limit <= 0 or p_cooldown_seconds < 0 then
        raise exception using message = 'invalid quota configuration';
    end if;

    insert into public.api_usage (client_id_hash, daily_period, monthly_period)
    values (p_client_id_hash, current_day, current_month)
    on conflict (client_id_hash) do nothing;

    select * into usage_row
      from public.api_usage
     where client_id_hash = p_client_id_hash
     for update;

    current_daily_count := case when usage_row.daily_period = current_day
        then usage_row.daily_count else 0 end;
    current_monthly_count := case when usage_row.monthly_period = current_month
        then usage_row.monthly_count else 0 end;

    if usage_row.last_request_at is not null
       and p_now < usage_row.last_request_at + make_interval(secs => p_cooldown_seconds) then
        retry_after := greatest(1, ceil(extract(epoch from (
            usage_row.last_request_at + make_interval(secs => p_cooldown_seconds) - p_now
        )))::integer);
        update public.api_usage set daily_period = current_day,
            daily_count = current_daily_count, monthly_period = current_month,
            monthly_count = current_monthly_count, updated_at = p_now
        where client_id_hash = p_client_id_hash;
        return jsonb_build_object('allowed', false, 'reason', 'cooldown',
            'retry_after_seconds', retry_after);
    end if;

    if current_daily_count >= p_daily_limit then
        retry_after := greatest(1, ceil(extract(epoch from (
            date_trunc('day', p_now at time zone 'UTC') + interval '1 day'
            - (p_now at time zone 'UTC')
        )))::integer);
        update public.api_usage set daily_period = current_day,
            daily_count = current_daily_count, monthly_period = current_month,
            monthly_count = current_monthly_count, updated_at = p_now
        where client_id_hash = p_client_id_hash;
        return jsonb_build_object('allowed', false, 'reason', 'daily_limit',
            'retry_after_seconds', retry_after);
    end if;

    if current_monthly_count >= p_monthly_limit then
        retry_after := greatest(1, ceil(extract(epoch from (
            date_trunc('month', p_now at time zone 'UTC') + interval '1 month'
            - (p_now at time zone 'UTC')
        )))::integer);
        update public.api_usage set daily_period = current_day,
            daily_count = current_daily_count, monthly_period = current_month,
            monthly_count = current_monthly_count, updated_at = p_now
        where client_id_hash = p_client_id_hash;
        return jsonb_build_object('allowed', false, 'reason', 'monthly_limit',
            'retry_after_seconds', retry_after);
    end if;

    update public.api_usage set daily_period = current_day,
        daily_count = current_daily_count + 1, monthly_period = current_month,
        monthly_count = current_monthly_count + 1, last_request_at = p_now,
        updated_at = p_now
    where client_id_hash = p_client_id_hash;

    return jsonb_build_object('allowed', true,
        'daily_count', current_daily_count + 1,
        'monthly_count', current_monthly_count + 1);
end;
$$;

revoke all on function public.check_api_quota(text, integer, integer, integer, timestamptz)
    from public, anon, authenticated;
revoke all on function public.consume_api_quota(text, integer, integer, integer, timestamptz)
    from public, anon, authenticated;
grant execute on function public.check_api_quota(text, integer, integer, integer, timestamptz)
    to service_role;
grant execute on function public.consume_api_quota(text, integer, integer, integer, timestamptz)
    to service_role;

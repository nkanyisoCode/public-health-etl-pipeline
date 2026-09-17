{{ config(materialized='table') }}

with years as (
    select distinct year
    from {{ source('staging', 'stg_health_indicators') }}
    where year is not null
)

select
    (year * 10000 + 101)::int as date_id,
    make_date(year, 1, 1) as date_day,
    1 as day,
    1 as month,
    year,
    1 as quarter,
    'Yearly'::text as reporting_frequency
from years

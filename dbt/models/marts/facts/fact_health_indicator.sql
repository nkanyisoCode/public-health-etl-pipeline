{{ config(materialized='table') }}

with indicators as (
select * from {{ source('staging', 'stg_health_indicators') }}
),

final as (
select
        i.region_key,
        dr.region_key as region_id,
        dd.date_id,
        di.indicator_code as indicator_id,
        i.value,
        i.is_missing,
        i.is_revised,
        i.is_estimated,
        i.loaded_at
from indicators i
inner join {{ ref('dim_region') }} dr on i.region_key = dr.region_key
inner join {{ ref('dim_date') }} dd on i.year = dd.year
inner join {{ ref('dim_indicator') }} di on i.indicator_code = di.indicator_code
where i.value is not null
)

select * from final
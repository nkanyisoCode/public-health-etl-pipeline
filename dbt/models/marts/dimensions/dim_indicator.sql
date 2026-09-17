{{ config(materialized='table') }}

select distinct
    indicator_code,
    indicator_name,
    indicator_category,
    indicator_unit
from {{ source('staging', 'stg_health_indicators') }}
where indicator_code is not null

{{ config(materialized='table') }}

select
    region_key,
    region_name,
    iso_code,
    region_type,
    case
        when region_type = 'country' then 'Country'
        when region_type = 'aggregate' then 'Regional aggregate'
        else 'Other'
    end as region_type_label
from {{ ref('stg_regions') }}

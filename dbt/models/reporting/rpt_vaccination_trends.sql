-- DTP3 vaccination coverage trends by region and year
select
    dr.region_name,
    dr.iso_code,
    dr.region_type_label,
    dd.year,
    f.value as dtp3_coverage_pct,
    f.is_estimated
from {{ ref('fact_health_indicator') }} f
inner join {{ ref('dim_region') }} dr on f.region_id = dr.region_key
inner join {{ ref('dim_date') }} dd on f.date_id = dd.date_id
inner join {{ ref('dim_indicator') }} di on f.indicator_id = di.indicator_code
where di.indicator_code = 'dtp3'
order by dr.region_name, dd.year

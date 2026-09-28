-- Latest-year DTP3 coverage by country for regional comparison
with latest as (
    select max(dd.year) as max_year
    from {{ ref('fact_health_indicator') }} f
    inner join {{ ref('dim_date') }} dd on f.date_id = dd.date_id
    inner join {{ ref('dim_indicator') }} di on f.indicator_id = di.indicator_code
    where di.indicator_code = 'dtp3'
)

select
    dr.region_name,
    dr.iso_code,
    dd.year,
    f.value as dtp3_coverage_pct,
    case when f.value >= 80 then 'At or above WHO target'
         when f.value >= 50 then 'Moderate coverage'
         else 'Low coverage'
    end as coverage_band
from {{ ref('fact_health_indicator') }} f
inner join {{ ref('dim_region') }} dr on f.region_id = dr.region_key
inner join {{ ref('dim_date') }} dd on f.date_id = dd.date_id
inner join {{ ref('dim_indicator') }} di on f.indicator_id = di.indicator_code
cross join latest l
where di.indicator_code = 'dtp3'
  and dr.region_type = 'country'
  and dd.year = l.max_year
order by f.value desc

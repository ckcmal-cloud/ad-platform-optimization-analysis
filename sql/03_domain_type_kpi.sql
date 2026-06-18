-- 목적: 비용 정제가 완료 광고 로그 기반 (Python 원본과 동일하게 필터 없이), 도메인(Domain) 및 광고유형(Type) 단위의 성과 지표(KPI)를 도출

-- 1. 메타 데이터 및 한글 라벨 매핑 처리
WITH mapped_metadata AS (
    SELECT 
        ads_idx,
        ads_name,
        ads_contract_price,
        CASE domain_label 
            WHEN 1 THEN '엔터'
            WHEN 2 THEN '금융'
            WHEN 3 THEN '라이프'
            WHEN 4 THEN '커머스'
            ELSE '기타'
        END AS domain_name,
        CASE ads_type
            WHEN 1 THEN '설치형'
            WHEN 2 THEN '실행형'
            WHEN 3 THEN '참여형'
            WHEN 4 THEN '클릭형'
            WHEN 5 THEN '페이스북'
            WHEN 6 THEN '트위터'
            WHEN 7 THEN '인스타그램'
            WHEN 9 THEN '퀘스트'
            WHEN 10 THEN '유튜브'
            WHEN 11 THEN '네이버'
            WHEN 12 THEN 'CPS(구매)'
            ELSE '기타'
        END AS type_name
    FROM ad_meta -- 실무 데이터의 'IVE_광고목록_도메인라벨링_수기보정' 테이블에 대응
),

-- 2. 광고 로그 집계 (Python 03 노트북 정합성 반영)
cleaned_ad_summary AS (
    SELECT 
        f.ads_idx,
        -- 광고별 클릭수, 전환수, 비용 집계
        COUNT(f.click_key) AS click_count,
        SUM(CASE WHEN f.rwd_cost > 0 THEN 1 ELSE 0 END) AS conversion_count,
        SUM(f.adv_cost) AS total_cost
    FROM fraud_detection_results f
    -- Python 03 노트북은 어뷰징 필터링 전 원천 정제 데이터(cleaned_reward) 전체를 기준으로 KPI를 집계함.
    -- 따라서 정합성을 위해 WHERE row_label = '정상' 조건을 제거함.
    GROUP BY f.ads_idx
),

-- 3. 광고 성과 테이블 결합
ad_performance_base AS (
    SELECT 
        m.domain_name,
        m.type_name,
        m.ads_idx,
        m.ads_contract_price,
        COALESCE(s.click_count, 0) AS click_count,
        COALESCE(s.conversion_count, 0) AS conversion_count,
        COALESCE(s.total_cost, 0) AS total_cost
    FROM mapped_metadata m
    LEFT JOIN cleaned_ad_summary s 
        ON m.ads_idx = s.ads_idx
)

-- 4. KPI 지표 요약 조회
-- 4-1.도메인별 KPI 분석
SELECT 
    '도메인별 성과' AS gubun,
    domain_name AS category,
    COUNT(DISTINCT ads_idx) AS total_ads,
    SUM(click_count) AS total_clicks,
    SUM(conversion_count) AS total_conversions,
    SUM(total_cost) AS total_spent,
    -- CVR (전환율, %)
    ROUND(SUM(conversion_count) * 100.0 / NULLIF(SUM(click_count), 0), 2) AS cvr_pct,
    -- CPA (전환당 비용)
    ROUND(SUM(total_cost) / NULLIF(SUM(conversion_count), 0), 2) AS cpa
FROM ad_performance_base
GROUP BY domain_name

UNION ALL

-- 4-2. 광고유형별 KPI 분석
SELECT 
    '광고유형별 성과' AS gubun,
    type_name AS category,
    COUNT(DISTINCT ads_idx) AS total_ads,
    SUM(click_count) AS total_clicks,
    SUM(conversion_count) AS total_conversions,
    SUM(total_cost) AS total_spent,
    -- CVR (전환율, %)
    ROUND(SUM(conversion_count) * 100.0 / NULLIF(SUM(click_count), 0), 2) AS cvr_pct,
    -- CPA (전환당 비용)
    ROUND(SUM(total_cost) / NULLIF(SUM(conversion_count), 0), 2) AS cpa
FROM ad_performance_base
GROUP BY type_name
ORDER BY gubun, total_spent DESC;

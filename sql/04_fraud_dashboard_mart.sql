-- =========================================================================
-- 04_fraud_dashboard_mart.sql
-- 목적: 어뷰징 탐지 결과(fraud_detection_results)를 매체, 도메인, 광고유형, 일별로 집계하여
--       어뷰징 현황 및 매출 손실액(Loss)을 모니터링할 수 있는 대시보드 마트를 생성합니다.
-- 유래: 02_fraud_detection_pipeline.ipynb의 "4-1. 도메인 오염도", "6. 매체 사례", "5. 8월 이상신호" 집계 기준 반영
-- =========================================================================

CREATE TABLE mart_fraud_dashboard AS
WITH metadata AS (
    SELECT 
        ads_idx,
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
    FROM ad_meta
)
SELECT 
    f.click_date,
    -- 1. 매체별 집계 (Python Line 1721-1725: loss_by_media 기준)
    f.mda_idx AS media_idx,
    -- 2. 도메인 및 광고유형별 집계 (Python Line 775-782: type_sum, Line 829-837: domain_sum 기준)
    m.domain_name,
    m.type_name,
    
    -- 3. 실적 집계
    COUNT(f.click_key) AS total_clicks,
    SUM(CASE WHEN f.rwd_cost > 0 THEN 1 ELSE 0 END) AS total_conversions,
    SUM(f.earn_cost) AS total_revenue,
    
    -- 4. 어뷰징 유형별 집계 플래그 합산 (Python Line 778-781: ctit_abnormal_rows 등 기준)
    SUM(f.ctit_error) AS ctit_error_count,
    SUM(f.is_device_error) AS device_error_count,
    SUM(f.is_click_error) AS click_error_count,
    
    -- 5. 최종 어뷰징 확정 건수 및 손실액 집계 (Python Line 743-744, Line 1724 기준)
    SUM(CASE WHEN f.row_label = '어뷰징 확정' THEN 1 ELSE 0 END) AS total_fraud_count,
    SUM(f.fraud_loss) AS total_fraud_loss,
    
    -- 6. 비율 연산 지표
    ROUND(SUM(CASE WHEN f.row_label = '어뷰징 확정' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(f.click_key), 0), 2) AS pollution_rate_pct,
    ROUND(SUM(f.fraud_loss) * 100.0 / NULLIF(SUM(f.earn_cost), 0), 2) AS loss_rate_pct

FROM fraud_detection_results f
LEFT JOIN metadata m 
    ON f.ads_idx = m.ads_idx
GROUP BY 
    f.click_date,
    f.mda_idx,
    m.domain_name,
    m.type_name;

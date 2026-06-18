-- =========================================================================
-- 05_ad_recommendation_mart.sql
-- 목적: 어뷰징이 제외된 정상 집행 성과를 바탕으로, 공급 광고 대비 실제 반응률(Response Rate),
--       전환율(CVR), 전환당 단가(CPA) 및 운영 효율성을 종합 분석하여 매체별/광고주별 
--       최적의 광고 조합을 추천하는 마트를 생성합니다.
-- 유래: 03_domain_optimization_analysis.ipynb의 "2. 광고 반응 현황", "공급 광고 유형", 
--       "통합 광고 성과 테이블 생성(total_df)" 및 추천 전략 기준 반영
-- =========================================================================

CREATE TABLE mart_ad_recommendation AS
WITH metadata AS (
    SELECT 
        ads_idx,
        ads_name,
        ads_contract_price,
        ads_order,
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
),

-- 광고별(ads_idx) 정상 클릭 실적 집계 (Python Line 313-318: click_ad 기준)
cleaned_click_ad AS (
    SELECT 
        ads_idx,
        COUNT(click_key) AS click_count,
        MIN(click_date) AS first_click,
        MAX(click_date) AS last_click
    FROM fraud_detection_results
    WHERE row_label = '정상'
    GROUP BY ads_idx
),

-- 광고별(ads_idx) 정상 전환 및 비용 실적 집계 (Python Line 319-325: conv_ad 기준)
cleaned_conv_ad AS (
    SELECT 
        ads_idx,
        COUNT(click_key) AS conversion_count,
        SUM(adv_cost) AS total_cost,
        MIN(click_date) AS first_conv,
        MAX(click_date) AS last_conv
    FROM fraud_detection_results
    WHERE row_label = '정상' AND rwd_cost > 0
    GROUP BY ads_idx
),

-- 개별 광고단위 통합 성과 테이블 구축 (Python Line 327-336: total_df 생성 로직 반영)
ad_performance_detail AS (
    SELECT 
        m.ads_idx,
        m.ads_name,
        m.domain_name,
        m.type_name,
        m.ads_contract_price,
        m.ads_order,
        COALESCE(c.click_count, 0) AS click_count,
        COALESCE(v.conversion_count, 0) AS conversion_count,
        COALESCE(v.total_cost, 0) AS total_cost,
        
        -- 운영 일수 연산 (Python Line 333-335: operation_days 계산)
        CASE 
            WHEN c.first_click IS NOT NULL AND v.first_conv IS NOT NULL THEN
                DATEDIFF(
                    day,
                    CASE WHEN c.first_click < v.first_conv THEN c.first_click ELSE v.first_conv END,
                    CASE WHEN c.last_click > v.last_conv THEN c.last_click ELSE v.last_conv END
                ) + 1
            WHEN c.first_click IS NOT NULL THEN
                DATEDIFF(day, c.first_click, c.last_click) + 1
            WHEN v.first_conv IS NOT NULL THEN
                DATEDIFF(day, v.first_conv, v.last_conv) + 1
            ELSE 0
        END AS operation_days
    FROM metadata m
    LEFT JOIN cleaned_click_ad c ON m.ads_idx = c.ads_idx
    LEFT JOIN cleaned_conv_ad v ON m.ads_idx = v.ads_idx
)

-- 최종 마트 테이블: 도메인 x 광고유형 단위로 요약 및 추천 로직 설계
SELECT 
    domain_name,
    type_name,
    COUNT(ads_idx) AS total_supplied_ads,
    
    -- 반응 광고 수 및 비율 (Python Line 330, Line 358-364: response 분석 기준)
    SUM(CASE WHEN click_count > 0 OR conversion_count > 0 THEN 1 ELSE 0 END) AS responded_ads_count,
    ROUND(SUM(CASE WHEN click_count > 0 OR conversion_count > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(ads_idx), 2) AS response_rate_pct,
    
    -- 실적 지표
    SUM(click_count) AS total_clicks,
    SUM(conversion_count) AS total_conversions,
    SUM(total_cost) AS total_spent,
    
    -- CVR & CPA (Python Line 331-332: cvr, cpconv 계산 기준)
    ROUND(SUM(conversion_count) * 100.0 / NULLIF(SUM(click_count), 0), 2) AS avg_cvr_pct,
    ROUND(SUM(total_cost) / NULLIF(SUM(conversion_count), 0), 2) AS avg_cpa,
    
    -- 운영 일수 평균
    ROUND(AVG(operation_days), 1) AS avg_operation_days,
    
    -- 광고 집행 포트폴리오 추천 추천 액션
    CASE 
        WHEN ROUND(SUM(CASE WHEN click_count > 0 OR conversion_count > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(ads_idx), 2) < 5.0 
            THEN '공급 과잉 / 집행 축소 및 무반응 광고 중단 권고'
        WHEN ROUND(SUM(conversion_count) * 100.0 / NULLIF(SUM(click_count), 0), 2) >= 15.0 AND ROUND(SUM(total_cost) / NULLIF(SUM(conversion_count), 0), 2) <= 1500 
            THEN '추천 전략: 핵심 주력 상품 - 예산 대폭 증액 권고'
        WHEN ROUND(SUM(conversion_count) * 100.0 / NULLIF(SUM(click_count), 0), 2) < 2.0 
            THEN '효율 저하: CVR 개선 필요 / 단가 재협상 권고'
        ELSE '유지 및 점진적 최적화'
    END AS strategic_recommendation

FROM ad_performance_detail
GROUP BY 
    domain_name,
    type_name;

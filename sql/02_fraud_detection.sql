-- 목적: 통합 로그 기반 3대 어뷰징 탐지 기준 적용, 행 단위 어뷰징 판정 테이블 구축 및 손실액 계산

-- 1. 광고 유형별 CTIT 중앙값 산출 (유형 4인 클릭형 제외)
-- Python(df_reward.median())과 정합성을 맞추기 위해 조인 전 원천 적립 로그 사용 및 PERCENTILE_DISC 적용
WITH ctit_medians AS (
    SELECT 
        m.ads_type,
        PERCENTILE_DISC(0.5) WITHIN GROUP (ORDER BY r.ctit) AS ctit_median
    FROM ad_reward r
    INNER JOIN ad_master m ON r.ads_idx = m.ads_idx
    WHERE m.ads_type <> 4
      AND r.show_cost >= r.adv_cost
      AND r.adv_cost >= r.earn_cost
      AND r.earn_cost >= r.rwd_cost
    GROUP BY m.ads_type
),

-- 유형별 CTIT cutoff (중앙값의 10%) 기준값 매칭
ctit_thresholds AS (
    SELECT 
        ads_type,
        (ctit_median * 0.1) AS ctit_cut
    FROM ctit_medians
),

-- 2. 매체(mda_idx) 및 IP(user_ip)별 기기수 및 클릭수 집계
-- Python(score_base = 참여 로그)과 정합성을 맞추기 위해 조인 전 참여 로그 기준 집계 (Fan-out 방지)
ip_media_aggregation AS (
    SELECT 
        e.mda_idx,
        e.user_ip,
        COUNT(DISTINCT e.dvc_idx) AS device_count,
        COUNT(e.click_key) AS click_count
    FROM (
        SELECT mda_idx, user_ip, dvc_idx, click_key
        FROM ad_engagement
        WHERE (adv_price >= contract_price)
          AND (contract_price >= media_price)
          AND (media_price >= reward_price)
    ) e
    INNER JOIN (
        SELECT DISTINCT click_key 
        FROM ad_reward 
        WHERE click_key IS NOT NULL
          AND show_cost >= adv_cost
          AND adv_cost >= earn_cost
          AND earn_cost >= rwd_cost
    ) r ON e.click_key = r.click_key
    GROUP BY e.mda_idx, e.user_ip
),

-- 3. 전체 기기수 및 클릭수 분포 기준 상위 0.1%(99.9% percentile) 임계값 산출
ip_thresholds AS (
    SELECT 
        PERCENTILE_CONT(0.999) WITHIN GROUP (ORDER BY device_count) AS device_cut,
        PERCENTILE_CONT(0.999) WITHIN GROUP (ORDER BY click_count) AS click_cut
    FROM ip_media_aggregation
),

-- 4. 3가지 어뷰징 플래그 맵 생성
ip_error_flags AS (
    SELECT 
        agg.mda_idx,
        agg.user_ip,
        agg.device_count,
        agg.click_count,
        CASE WHEN agg.device_count > th.device_cut THEN 1 ELSE 0 END AS is_device_error,
        CASE WHEN agg.click_count > th.click_cut THEN 1 ELSE 0 END AS is_click_error
    FROM ip_media_aggregation agg
    CROSS JOIN ip_thresholds th
)

-- 5. 최종 판정 테이블 생성 (fraud_loss 계산 및 row_label 매핑)
CREATE TABLE fraud_detection_results AS
SELECT 
    base.ads_idx,
    base.ads_type,
    base.mda_idx,
    base.click_key,
    base.show_cost,
    base.adv_cost,
    base.earn_cost,
    base.rwd_cost,
    base.click_date,
    base.ctit,
    base.user_ip,
    base.dvc_idx,
    
    -- 조건 1: CTIT 이상 여부 플래그
    CASE 
        WHEN base.ads_type = 4 AND base.ctit = 0 THEN 1
        WHEN base.ads_type <> 4 AND base.ctit < COALESCE(ct.ctit_cut, 0) THEN 1
        ELSE 0 
    END AS ctit_error,
    
    -- 조건 2, 3: IP 다기기 및 IP 클릭 집중 여부 플래그
    COALESCE(err.is_device_error, 0) AS is_device_error,
    COALESCE(err.is_click_error, 0) AS is_click_error,
    
    -- 지급 완료 여부 (rwd_cost > 0)
    CASE WHEN base.rwd_cost > 0 THEN 1 ELSE 0 END AS is_rewarded,
    
    -- 최종 판정 행 라벨 (row_label)
    CASE 
        WHEN base.rwd_cost = 0 THEN '미적립'
        WHEN (
            (base.ads_type = 4 AND base.ctit = 0) OR
            (base.ads_type <> 4 AND base.ctit < COALESCE(ct.ctit_cut, 0)) OR
            COALESCE(err.is_device_error, 0) = 1 OR
            COALESCE(err.is_click_error, 0) = 1
        ) THEN '어뷰징 확정'
        ELSE '정상'
    END AS row_label,
    
    -- 어뷰징 확정 건의 손실액 (fraud_loss) 연산
    CASE 
        WHEN base.rwd_cost > 0 AND (
            (base.ads_type = 4 AND base.ctit = 0) OR
            (base.ads_type <> 4 AND base.ctit < COALESCE(ct.ctit_cut, 0)) OR
            COALESCE(err.is_device_error, 0) = 1 OR
            COALESCE(err.is_click_error, 0) = 1
        ) THEN base.earn_cost
        ELSE 0
    END AS fraud_loss

FROM integrated_cleaned_logs base
LEFT JOIN ctit_thresholds ct 
    ON base.ads_type = ct.ads_type
LEFT JOIN ip_error_flags err 
    ON base.mda_idx = err.mda_idx 
    AND base.user_ip = err.user_ip;

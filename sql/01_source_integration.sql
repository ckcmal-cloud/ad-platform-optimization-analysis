-- 목적: 원본(참여, 적립, 광고 목록) 정제 및 결측 및 비용 역전 오류가 제거된 분석용 통합 데이터셋 생성

-- 1. 참여 로그(Engagement) 정제 및 비용 검증
-- 비용 관계 검증: adv_price >= contract_price >= media_price >= reward_price
WITH cleaned_engagement AS (
    SELECT 
        click_key,
        dvc_idx,
        mda_idx,
        click_date,
        user_ip,
        COALESCE(network, 'Unknown') AS network,
        CAST(COALESCE(adv_price, 0) AS DECIMAL(18,2)) AS adv_price,
        CAST(COALESCE(contract_price, 0) AS DECIMAL(18,2)) AS contract_price,
        CAST(COALESCE(media_price, 0) AS DECIMAL(18,2)) AS media_price,
        CAST(COALESCE(reward_price, 0) AS DECIMAL(18,2)) AS reward_price
    FROM ad_engagement -- 실무 데이터의 'IVE_광고참여정보' 테이블에 대응
    WHERE 
        -- 비용 역전 오류 제거
        (adv_price >= contract_price)
        AND (contract_price >= media_price)
        AND (media_price >= reward_price)
),

-- 2. 적립 로그(Reward) 정제 및 비용 검증
-- 비용 관계 검증: show_cost >= adv_cost >= earn_cost >= rwd_cost
cleaned_reward AS (
    SELECT 
        ads_idx,
        mda_idx,
        COALESCE(advid, 'Unknown') AS advid,
        click_key,
        CAST(COALESCE(show_cost, 0) AS DECIMAL(18,2)) AS show_cost,
        CAST(COALESCE(adv_cost, 0) AS DECIMAL(18,2)) AS adv_cost,
        CAST(COALESCE(earn_cost, 0) AS DECIMAL(18,2)) AS earn_cost,
        CAST(COALESCE(rwd_cost, 0) AS DECIMAL(18,2)) AS rwd_cost,
        CAST(click_date AS DATE) AS click_date,
        CAST(COALESCE(ctit, 0) AS INT) AS ctit
    FROM ad_reward -- 실무 데이터의 'IVE_광고적립_all' 테이블에 대응
    WHERE 
        -- 비용 역전 오류 제거
        (show_cost >= adv_cost)
        AND (adv_cost >= earn_cost)
        AND (earn_cost >= rwd_cost)
),

-- 3. 고유 IP 매칭 정보 생성
click_ip_map AS (
    SELECT 
        click_key,
        user_ip
    FROM (
        SELECT 
            click_key,
            user_ip,
            ROW_NUMBER() OVER (PARTITION BY click_key ORDER BY click_date DESC) as rn
        FROM cleaned_engagement
    ) t
    WHERE rn = 1 -- click_key당 단일 IP 보장
)

-- 4. 통합 광고 로그 생성 (Cleaned Base 데이터셋)
-- 광고 마스터와 매칭되고, click_key가 존재하는 적립/참여 로그 결합
CREATE TABLE integrated_cleaned_logs AS
SELECT 
    r.ads_idx,
    m.ads_type,
    r.mda_idx,
    r.click_key,
    r.show_cost,
    r.adv_cost,
    r.earn_cost,
    r.rwd_cost,
    r.click_date,
    r.ctit,
    ip.user_ip,
    e.dvc_idx
FROM cleaned_reward r
INNER JOIN ad_master m -- 실무 데이터의 'IVE_광고목록' 테이블에 대응
    ON r.ads_idx = m.ads_idx
INNER JOIN click_ip_map ip 
    ON r.click_key = ip.click_key
LEFT JOIN cleaned_engagement e 
    ON r.click_key = e.click_key
WHERE 
    r.click_key IS NOT NULL 
    AND ip.user_ip IS NOT NULL;

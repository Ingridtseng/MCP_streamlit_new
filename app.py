import streamlit as st
from streamlit_mic_recorder import mic_recorder
from openai import OpenAI
import os
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
import re
import base64

# --- 密碼驗證功能 ---
def check_password():
    """回傳 True 代表密碼正確"""
    def password_entered():
        # 這裡設定你的真實密碼，例如 "mcp2026"
        if st.session_state["password"] == "88888":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # 驗證後刪除 session 中的明文密碼
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 尚未登入，顯示輸入框
        st.text_input("請輸入專案存取密碼", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # 密碼錯誤，顯示錯誤並再次顯示輸入框
        st.text_input("密碼錯誤，請重新輸入", type="password", on_change=password_entered, key="password")
        st.error("😕 密碼不正確")
        return False
    else:
        # 密碼正確
        return True

if not check_password():
    st.stop()  # 如果密碼沒過，後面的程式碼（數據處理、繪圖）都不會執行


# 匯入 data_agent 功能
from data_agent import get_mcp_vision_insight, query_data_via_duckdb
TAIWAN_CITIES = [
    '台北', '新北', '桃園', '台中', '台南', '高雄', 
    '基隆', '新竹縣', '新竹市', '嘉義縣', '嘉義市', '彰化', '南投', '雲林', 
    '屏東', '宜蘭', '花蓮', '台東', '澎湖','苗栗','金門', '連江'
]
# 1. 載入環境變數與初始化
load_dotenv()
client = OpenAI()

# 配置頁面：寬版模式
st.set_page_config(page_title="TALARIA AI 數據戰情室", layout="wide", initial_sidebar_state="collapsed")

# --- 1. 初始化 Session State (確保變數永遠存在) ---
if 'product_keywords' not in st.session_state:
    st.session_state.product_keywords = [] # 預設為空清單

if 'generated_sql' not in st.session_state:
    st.session_state.generated_sql = "" # 預設為空 SQL


# --- 視覺風格定義 (Visual Identity) ---
st.markdown("""
    <style>
    /* 1. 基礎背景設定 */
    
    .stApp { 
        background-color: #000000; 
        background-image: radial-gradient(circle at 50% 30%, #0D1117 0%, #010409 100%);
    }

    /* 3. 標題樣式 - 增加霓虹光暈 */
    h1 { 
        font-size: 48px !important; 
        color: #ffffff !important; 
        text-align: center; 
        text-shadow: 0 0 20px rgba(88, 166, 255, 0.6);
        font-weight: 800 !important;
        margin-bottom: 30px !important;
    }
    h2, h3, .stSubheader p {
        color: #65E8FF !important;
        font-weight: bold !important;
        font-size: 34px !important;
        text-shadow: 0 0 20px rgba(88, 166, 255, 0.2);
        opacity: 0.9 !important;
    }

    /* 4. 欄位容器優化 (左/右欄) - 玻璃擬態風格 */
    div[data-testid="stColumn"] > div {
        background-color: rgba(22, 27, 34, 0.6); /* 半透明深灰藍 */
        border: 1px solid rgba(88, 166, 255, 0.1); /* 極細微的藍邊框 */
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); /* 柔和陰影 */
        backdrop-filter: blur(5px); /* 背景模糊效果 */
    
    /* 只針對 key 為 manual_in 的輸入框標籤進行放大 */
    div[data-widget-key="manual_in"] label p {
        font-size: 24px !important; /* 在這裡調大「⌨️ 輸入指令：」 */
        font-weight: 800 !important;
        color: #65E8FF !important;
        text-shadow: 0 0 10px rgba(101, 232, 255, 0.4);
        opacity: 0.9;
    }


    /* 5. 輸入框超級優化 (解決看不到字與游標的問題) */
    .stTextInput input {
        background-color: #0D1117 !important; /* 比背景稍亮一點 */
        color: #FFFFFF !important; /* 輸入文字純白 */
        caret-color: #00FFFF !important; /* ★關鍵：游標(直槓)改成亮青色，看得見了！ */
        font-size: 30px !important; /* 字再大一點 */
        height: 80px !important; /* 高度加高 */
        border-radius: 12px !important;
        border: 2px solid #30363d !important; /* 平常是暗邊框 */
        padding-left: 15px !important;
        transition: all 0.3s ease;
    }
    
    /* 輸入框被點擊(Focus)時的特效 */
    .stTextInput input:focus {
        border-color: #00FFFF !important; /* 邊框變青色 */
        box-shadow: 0 0 15px rgba(0, 255, 255, 0.3) !important; /* 發光 */
        background-color: #161b22 !important;
    }

    /* 調整輸入框標籤：極簡清透風 */
    .stTextInput label {
        color: #65E8FF !important; /* 使用你喜歡的藍色 */
        font-size: 28px !important; /* 大小適中 */
        font-weight: 600 !important;
        letter-spacing: 1.5px; /* 增加一點字距感 */
        padding-left: 0px !important;
        margin-bottom: 8px !important;
        /* 使用文字下方的發光效果代替背景 */
        text-shadow: 0 0 8px rgba(101, 232, 255, 0.4);
        opacity: 0.9;
    }
    /* 新增：讓提示文字的大小也跟著連動 */
    .stTextInput input::placeholder {
    font-size: 20px !important; /* 調整提示文字的大小 */
    color: rgba(255, 255, 255, 0.4) !important; /* 保持清透感 */
    }


    /* 6. 按鈕優化 (讓 Record/Submit 按鈕也變帥) */
    .stButton button {
        background: linear-gradient(90deg, #1E293B 0%, #0F172A 100%);
        color: #65E8FF !important;
        border: 1px solid #65E8FF !important;
        border-radius: 8px !important;
        font-size: 20px !important;
        font-weight: bold !important;
        padding: 10px 20px !important;
        transition: all 0.3s;
    }
    
    .stButton button:hover {
        background: #65E8FF !important;
        color: #000000 !important;
        box-shadow: 0 0 20px rgba(88, 166, 255, 0.6);
        border-color: #65E8FF !important;
    }

    /* 7. 使用者指令顯示框 (美化版) */
    .user-command-text {
        background: rgba(30, 41, 59, 0.6) !important;
        color: #E2E8F0 !important;
        font-size: 22px !important;
        font-weight: 500 !important;
        padding: 20px !important;
        border-radius: 12px !important;
        border-left: 5px solid #00FFFF !important; /* 左側亮條 */
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3) !important;
        margin: 20px 0px !important;
        backdrop-filter: blur(5px);
    }

    /* 8. AI 洞察箱 (維持原本的醒目風格，微調圓角) */

    .insight-box {
    /* 1. 半透明背景：使用你的色號 #65E8FF，但轉為 RGBA 格式並給予 0.8 的透明度 */
    background: rgba(101, 232, 255, 0.8) !important;
    
    /* 2. 玻璃霧化效果：這是靈魂，會讓後面的東西模糊掉 */
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    
    /* 3. 漸層感：加一層淡淡的白色發光漸層 */
    background-image: linear-gradient(
        135deg, 
        rgba(255, 255, 255, 0.4) 0%, 
        rgba(101, 232, 255, 0.8) 100%
    ) !important;

    /* 4. 文字顏色：既然背景變亮了，文字要用黑色才高級 */
    color: #000000 !important;
    font-size: 20px !important;
    font-weight: 700;
    line-height: 1.8 !important;
    
    /* 5. 圓角與邊框 */
    padding: 30px;
    border-radius: 20px;
    margin-bottom: 25px;
    
    /* 6. 白色細邊框：模擬玻璃邊緣的折射感 */
    border: 1px solid rgba(255, 255, 255, 0.5) !important;
    
    /* 7. 外發光：淡淡的天藍色光暈 */
    box-shadow: 0 8px 32px 0 rgba(101, 232, 255, 0.3);
    }   
    /* 建立統一的區塊感樣式 */
    .chart-card {
        background-color: rgba(255, 255, 255, 0.03); 
        border: 1px solid rgba(0, 255, 255, 0.2);   
        border-radius: 20px;                         
        padding: 25px;                               
        margin: 10px 0 25px 0;                         
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);   
        display: block;
        width: 100%;
        /* 確保內容不會溢出圓角 */
        overflow: hidden; 
    }


    /* 9. 表格樣式優化 */
    div[data-testid="stDataFrame"] {
        background-color: #0D1117 !important;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 5px;
    }
    div[data-testid="stDataFrame"] table {
        color: #c9d1d9 !important;
    }
    div[data-testid="stDataFrame"] thead th {
        background-color: #161b22 !important;
        color: #58a6ff !important;
        font-size: 24px !important;
    }

    /* 10. Metric 數值優化 */
    [data-testid="stMetricValue"] {
        font-size: 36px !important;
        color: #00FFFF !important;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
    }
    [data-testid="stMetricLabel"] {
        color: #8b949e !important;
    }
    
    /* 11. Expander (偵探模式) 優化 */
    [data-testid="stExpander"] {
        background-color: #161b22 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
    }
    .streamlit-expanderHeader {
        color: #8b949e !important;
        font-size: 24px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 數據工具函數 ---
def transcribe_audio(audio_bytes):
    try:
        temp_filename = "temp_audio.mp3"
        with open(temp_filename, "wb") as f: f.write(audio_bytes)
        with open(temp_filename, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        if os.path.exists(temp_filename): os.remove(temp_filename)
        return transcript.text
    except Exception as e: return f"轉錄錯誤: {e}"

def parse_sql_context(sql_query):
    """
    一站式解析 SQL：一次拿回資料表、城市、分類標籤
    """
    if not sql_query:
        return {"table": None, "city": "全台灣", "tags": [], "source_name": "未知"}

    sql_lower = sql_query.lower()
    
    # 1. 判斷資料表與中文名稱
    table_map = {
        'sub_category': ('sub_category', '子類別明細表'),
        'main_category_summary': ('main_category_summary', '類別摘要表'),
        'city_summary': ('city_summary', '城市總覽表')
    }
    
    current_table = 'sub_category'
    source_name = '未知來源'
    for key, (t_name, c_name) in table_map.items():
        if key in sql_lower:
            current_table = t_name
            source_name = c_name
            break

    # 2. 提取城市 (整合 detect_city_from_sql 邏輯)
    city_match = re.search(r"city_clean\s+LIKE\s+'%?([^'%]+)%?'", sql_query, re.IGNORECASE)
    detected_city = city_match.group(1).strip() if city_match else "全台灣"


    # 3. 提取標籤：只看 = 或 IN 語法
    final_tags = []
    
    # 搜尋 subcategory = '...' 或 category = '...'
    # re.search 會在找到第一個匹配項後立即停止
    tag_match = re.search(r"(?:subcategory|category)\s*=\s*'([^']*)'", sql_query, re.IGNORECASE)
    
    if tag_match:
        final_tags = [tag_match.group(1)]
    else:
        # 備援：搜尋 subcategory IN ('...')
        in_match = re.search(r"(?:subcategory|category)\s+IN\s*\(\s*'([^']*)'", sql_query, re.IGNORECASE)
        if in_match:
            final_tags = [in_match.group(1)]

    return {
        "table": current_table,
        "source_name": source_name,
        "city": detected_city,
        "tags": final_tags
    }

@st.cache_data(ttl=3600)
def get_city_monthly_data(city_name):
    """
    情況 C 專用：取得城市整體的每月總趨勢數據
    """
    # 城市過濾條件
    where_clause = ""
    if city_name and city_name != "全台灣":
        where_clause = f"WHERE city_clean LIKE '{city_name}%'"
        
    # 執行主查詢 (依照你的模板，將分類寫死為 '全品項')
    sql = f"""
    WITH city_data AS (
        SELECT 
            year,
            month,
            city_clean,
            SUM(amt) as amt,
            SUM(inv_cnt) as inv_cnt,
            SUM(barcode_cnt) as barcode_cnt,
            SUM(qty) as qty
        FROM city_summary
        {where_clause}
        GROUP BY year, month
    )
    SELECT 
        year as Year,
        month as Month,
        city_clean,
        amt as 銷售金額,
        CASE 
            WHEN inv_cnt > 0 THEN ROUND(amt / inv_cnt, 1)
            ELSE 0 
        END as 均發票金額,
        inv_cnt as 發票數量,
        barcode_cnt as 消費人數,
        qty as 銷售數量
    FROM city_data
    ORDER BY year, month
    """
    return query_data_via_duckdb(sql)

@st.cache_data(ttl=3600)
def get_product_monthly_data(target_categories, city_name=None, table_name='sub_category'):
    if not target_categories:
        return pd.DataFrame()
    
    # 1. 判定欄位名
    if table_name == 'main_category_summary':
        actual_col = 'category'
        display_name = 'Category'
    else:
        actual_col = 'subcategory'
        display_name = 'Subcategory'
    
    # --- 處理城市字串 ---
    is_all_taiwan = (not city_name or city_name == "全台灣")
    city_cond = "1=1"
    city_label_str = "全台灣"
    
    if not is_all_taiwan:
        clean_city = city_name.replace('臺', '台')
        city_cond = f"city_clean LIKE '{clean_city}%'"
        city_label_str = city_name

    # 2. 分拆分子與分母的 WHERE 條件
    safe_categories = [c.replace("'", "''") for c in target_categories]
    categories_str = "', '".join(safe_categories)
    
    # ✅ 僅在此處加入過濾「其他」的條件
    product_where = f"WHERE {actual_col} IN ('{categories_str}') AND {actual_col} NOT LIKE '%其他%' AND {city_cond}"
    market_where = f"WHERE {actual_col} NOT LIKE '%其他%' AND {city_cond}"

    # 4. 執行主查詢
    sql = f"""
    WITH market_total AS (
        SELECT 
            year, 
            month, 
            SUM(inv_cnt) as monthly_market_total
        FROM {table_name}
        {market_where}
        GROUP BY year, month
    ),
    product_data AS (
        SELECT 
            year,
            month,  -- 已修正原本代碼中的 Ímonth
            '{city_label_str}' as City,
            {actual_col} as cat_val,
            SUM(amt) as amt,
            SUM(inv_cnt) as inv_cnt,
            SUM(barcode_cnt) as barcode_cnt,
            SUM(qty) as qty
        FROM {table_name}
        {product_where}
        GROUP BY year, month, cat_val
    )
    SELECT 
        p.year as Year,
        p.month as Month,
        p.City,
        p.cat_val as {display_name},
        p.amt as 銷售金額,
        CASE WHEN p.inv_cnt > 0 THEN ROUND(p.amt / p.inv_cnt, 1) ELSE 0 END as 均發票金額,
        ROUND((p.inv_cnt * 100.0 / m.monthly_market_total), 4) as 發票占比,
        p.inv_cnt as 發票數量,
        p.barcode_cnt as 消費人數,
        p.qty as 銷售數量
    FROM product_data p
    LEFT JOIN market_total m ON p.year = m.year AND p.month = m.month
    ORDER BY p.year, p.month, p.cat_val
    """
    
    return query_data_via_duckdb(sql)

def standardize_table_structure(df, data_source=None, city_name=None):
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    # --- A. 建立統一映射字典 ---
    column_mapping = {
        'year': '年份', 'Year': '年份',
        'month': '月份', 'Month': '月份',
        'city': '城市', 'city_clean': '城市', 'City': '城市',
        'category': '分析維度', 'subcategory': '分析維度', 
        'Subcategory': '分析維度', 'Category': '分析維度',
        'cat_val': '分析維度', # 補上這個，因為 SQL 裡的品類叫 cat_val
        '發票占比': '發票占比',
        # 指標類：確保原始名稱能對接到標準名稱
        'amt': '銷售金額', 
        'inv_cnt': '發票張數',
        'barcode_cnt': '消費人數',
        'qty': '銷售數量',
        '客單價': '均發票金額'
    }
    
    df = df.rename(columns=column_mapping)

    # --- B. 補全邏輯 (僅針對 SQL 沒算到的部分) ---
    if '均發票金額' not in df.columns and '銷售金額' in df.columns and '發票張數' in df.columns:
        df['均發票金額'] = (df['銷售金額'] / df['發票張數'].replace(0, 1)).round(1)

    # 如果 SQL 已經給了 '銷售金額_億'，Python 就不動它；
    # 如果只有原始 '銷售金額'，才在這裡換算。
    if '銷售金額_百萬' not in df.columns and '銷售金額' in df.columns:
        df['銷售金額_百萬'] = (df['銷售金額'] / 1_000_000).round(2)
    
    if '發票數量_萬' not in df.columns and '發票張數' in df.columns:
        df['發票數量_萬'] = (df['發票張數'] / 10_000).round(2)

    if '消費人數_萬' not in df.columns and '消費人數' in df.columns:
        df['消費人數_萬'] = (df['消費人數'] / 10_000).round(2)

    if '銷售數量_萬' not in df.columns and '銷售數量' in df.columns:
        df['銷售數量_萬'] = (df['銷售數量'] / 10_000).round(2)

    # --- C. 統一發票占比計算 ---
    # if '發票占比' not in df.columns and '發票張數' in df.columns:
    #     total_inv = df['發票張數'].sum()
    #     df['發票占比'] = (df['發票張數'] / total_inv * 100).round(2) if total_inv > 0 else 0

    # --- D. 最終欄位篩選與排序 ---
    # 這裡的名稱必須與 SQL 產出的名稱「完全一致」
    target_columns = [
        '年份', '月份', '城市', '分析維度', 
        '銷售金額_百萬', '均發票金額', '發票占比', 
        '消費人數_萬', '發票數量_萬', '銷售數量_萬'
    ]
    
    final_cols = [col for col in target_columns if col in df.columns]
    
    return df[final_cols]



@st.cache_data(ttl=3600)
def get_bubble_chart_data(city_name=None):
    """取得泡泡圖數據：包含 year_month 以支援動畫"""
    # 💡 修正 city_name 判斷，確保 None 或 "None" 都能正確處理
    target_city = city_name if (city_name and str(city_name) != 'None') else None
    
    print(f"🌀 [SQL] 正在讀取 {target_city if target_city else '全台'} 的月度趨勢...")

    conditions = ["category NOT LIKE '%其他%'"]
    if target_city:
        conditions.append(f"city_clean LIKE '{target_city}%'")
    
    where_clause = f"WHERE {' AND '.join(conditions)}"

    # 💡 關鍵：必須在這裡產出 year_month 供 Plotly 動畫使用
    sql = f"""
    SELECT 
        CAST(year AS VARCHAR) || '-' || LPAD(CAST(month AS VARCHAR), 2, '0') as year_month,
        category,
        SUM(amt) as total_amt,
        SUM(inv_cnt) as total_inv_cnt,
        SUM(amt) / NULLIF(SUM(inv_cnt), 0) as avg_order_value
    FROM main_category_summary
    {where_clause}
    GROUP BY year, month, category
    ORDER BY year_month ASC, total_amt DESC
    """
    return query_data_via_duckdb(sql)

@st.cache_data(ttl=3600)
def get_all_subcategory_ratio(city_name=None):
    """
    取得全中分類佔比數據：計算所有中分類的總發票佔比
    
    Args:
        city_name: 城市名稱（可選）
    
    Returns:
        DataFrame with columns: subcategory, ratio, total_inv_cnt
    """
    # 建立過濾條件：排除類別名稱包含「其他」的資料
    conditions = ["subcategory NOT LIKE '%其他%'"]
    if city_name:
        conditions.append(f"city_clean LIKE '%{city_name}%'")
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    # 使用窗口函數計算佔比，更安全且準確
    sql = f"""
    WITH category_totals AS (
        SELECT 
            subcategory,
            SUM(inv_cnt) as total_inv_cnt,
            sum(amt) as amt
        FROM sub_category
        {where_clause}
        GROUP BY subcategory
    ),
    grand_total AS (
        SELECT SUM(total_inv_cnt) as grand_total_inv_cnt
        FROM category_totals
    )
    SELECT 
        ct.subcategory,
        ct.total_inv_cnt,
        ct.amt,
        CASE 
            WHEN gt.grand_total_inv_cnt > 0 
            THEN (ct.total_inv_cnt * 1.0 / gt.grand_total_inv_cnt)
            ELSE 0 
        END as ratio
    FROM category_totals ct
    CROSS JOIN grand_total gt
    ORDER BY ratio DESC
    """
    
    return query_data_via_duckdb(sql)

def get_smart_trend_data(target_table, target_tag, city_name=None):
    """
    智慧趨勢分析：支持指定城市或全台灣數據
    """
    # 1. 處理城市過濾器 (支援 None 或 "全台灣")
    if city_name and city_name not in ["全台灣", "全台"]:
        # 確保搜尋時包含該字眼
        city_filter = f"AND city_clean LIKE '%{city_name}%'"
    else:
        # 如果是 None 或是全台灣，則不加入城市過濾條件，即查詢全台數據
        city_filter = ""
    
    # 2. 核心邏輯：判定類別過濾條件
    if target_table == 'main_category_summary' and target_tag:
        # 指定大類 -> 鎖定該大類
        parent_cat_filter = f"WHERE category = '{target_tag}'"
    elif target_table == 'sub_category' and target_tag:
        # 指定中類 -> 反查其所屬大類
        sql_get_parent = f"SELECT category FROM sub_category WHERE subcategory = '{target_tag}' LIMIT 1"
        parent_cat_filter = f"WHERE category = ({sql_get_parent})"
    else:
        # 無特定對象 -> 抓取全場/全城 Top 10 中類
        # 注意：這裡的城市過濾必須同步套用到 Top 10 的計算中
        top_10_names_sql = f"""
            SELECT subcategory FROM sub_category 
            WHERE subcategory NOT LIKE '%其他%' {city_filter} 
            GROUP BY subcategory 
            ORDER BY SUM(inv_cnt) DESC LIMIT 10
        """
        parent_cat_filter = f"WHERE subcategory IN ({top_10_names_sql})"


    # 3. 最終 SQL 組裝
    # 使用 NULLIF 避免分母為 0
    sql = f"""
    SELECT 
        month,
        subcategory,
        SUM(inv_cnt) * 1.0 / NULLIF(SUM(SUM(inv_cnt)) OVER (PARTITION BY month), 0) as ratio
    FROM sub_category
    {parent_cat_filter}
    AND subcategory NOT LIKE '%其他%'
    {city_filter}
    GROUP BY month, subcategory
    ORDER BY month ASC
    """
    
    return query_data_via_duckdb(sql)

def get_trend_data(table_name, target_col, city_name=None):
    """
    取得佔比趨勢數據：計算前10名分類的月度佔比
    
    Args:
        table_name: 資料表名稱 ('main_category_summary' 或 'sub_category')
        target_col: 分類欄位名稱 ('category' 或 'subcategory')
        city_name: 城市名稱（可選）
    
    Returns:
        DataFrame with columns: month, {target_col}, ratio
    """
    # 建立過濾條件：排除類別名稱包含「其他」的資料
    conditions = [f"{target_col} NOT LIKE '%其他%'"]
    if city_name:
        conditions.append(f"city_clean LIKE '%{city_name}%'")
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    # 先找出前10名分類（按總發票數）
    top_categories_sql = f"""
    SELECT {target_col}
    FROM {table_name}
    {where_clause}
    GROUP BY {target_col}
    ORDER BY SUM(inv_cnt) DESC
    LIMIT 10
    """
    top_categories_df = query_data_via_duckdb(top_categories_sql)
    
    if top_categories_df is None or top_categories_df.empty:
        return pd.DataFrame()
    
    top_categories = top_categories_df[target_col].tolist()
    # 轉義單引號，避免 SQL 語法錯誤
    top_categories_escaped = [cat.replace("'", "''") for cat in top_categories]
    top_categories_str = "', '".join(top_categories_escaped)
    
    # 計算每個月的總發票數（作為分母）
    # 如果指定城市，則計算該城市的總發票數；否則計算全市場的總發票數
    city_filter = f"AND city_clean LIKE '%{city_name}%'" if city_name else ""
    
    # 計算佔比趨勢
    sql = f"""
    WITH monthly_totals AS (
        -- 計算每個月的總發票數（分母）
        SELECT 
            year,
            month,
            SUM(inv_cnt) as total_inv_cnt_month
        FROM {table_name}
        WHERE {target_col} NOT LIKE '%其他%' {city_filter}
        GROUP BY year, month
    ),
    category_monthly AS (
        -- 計算前10名分類每個月的發票數
        SELECT 
            t.year,
            t.month,
            t.{target_col},
            SUM(t.inv_cnt) as category_inv_cnt
        FROM {table_name} t
        WHERE t.{target_col} IN ('{top_categories_str}')
          AND t.{target_col} NOT LIKE '%其他%' {city_filter}
        GROUP BY t.year, t.month, t.{target_col}
    )
    SELECT 
        cm.year || '-' || LPAD(CAST(cm.month AS VARCHAR), 2, '0') as month,
        cm.{target_col},
        CASE 
            WHEN mt.total_inv_cnt_month > 0 
            THEN (cm.category_inv_cnt * 1.0 / mt.total_inv_cnt_month)
            ELSE 0 
        END as ratio
    FROM category_monthly cm
    JOIN monthly_totals mt 
        ON cm.year = mt.year AND cm.month = mt.month
    ORDER BY cm.year, cm.month, cm.{target_col}
    """
    
    return query_data_via_duckdb(sql)

    # --- 開始進入 Streamlit 畫面渲染 ---
    def get_base64_image(image_path):
        import os
        if not os.path.exists(image_path):
            # 預防檔案不存在報錯，回傳一個空字串或預設路徑
            print(f"警告：找不到圖檔 {image_path}")
            return ""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()





# ==========================================
# 佈局規劃：左 1/4 (對話) | 右 3/4 (畫布)
# ==========================================
left_col, right_col = st.columns([1, 3], gap="large")

# 城市偵測初始化
if 'detected_city' not in st.session_state:
    st.session_state.detected_city = None

# 對話歷史初始化
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

with left_col:
    # =========================================================
    # 1. 變數強制初始化 (這一步是為了解決 NameError)
    # =========================================================
    # 不管下面發生什麼事，這些變數現在就出生了，絕對不會報錯
    product_keywords = [] 
    data_source = "尚未偵測"
    sql_query = ""
    target_categories = []
    df = None
    product_df = None
    
    #st.title("TALARIA 數據決策大腦")
    # --- 第一步：定義函數 (放在最頂端，確保誰都認識它) ---
    def get_base64_image(image_path):
        if not os.path.exists(image_path):
            return ""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    logo_base64 = get_base64_image("白色logo.png")

    title_html = f"""
        <div style="
            display: flex; 
            justify-content: center; /* 這裡實現水平置中 */
            align-items: center;      /* 改為 center 讓 Logo 與文字在同一水平線上 */
            gap: 15px; 
            padding: 25px 0 20px 0; 
            width: 100%;             /* 確保容器佔滿寬度 */
        ">
            <img src="data:image/png;base64,{logo_base64}" style="height: 48px;">
            <div style="
                font-size: 40px;
                font-weight: 600;
                color: white;
                text-shadow: none;
                line-height: 1;
                letter-spacing: 2px;
                margin-top: 12px;     /* 正值往下移，負值（如 -5px）往上提 */
            ">
                數據決策大腦
            </div>
        </div>
        """

    st.markdown(title_html, unsafe_allow_html=True)

    # 增加一點空間感後，再接你的語音狀態
    st.write("")


        
    # =========================================================
    # 2. 輸入介面
    # =========================================================
    st.write("")
    audio = mic_recorder(start_prompt="🔴 語音指令", stop_prompt="⏹️ 停止並分析", key='recorder')
    # 分隔線
    st.markdown('<div style="margin: 20px 0;"></div>', unsafe_allow_html=True) # 用隱形間距代替死板的分隔線

    manual_input = st.text_input("⌨️ 輸入指令：", placeholder="例如：台北生鮮消費分析", key="manual_in")
    
    # 處理輸入訊號
    if manual_input: 
        st.session_state.user_prompt = manual_input
    if audio:
        with st.spinner("辨識中..."):
            user_text = transcribe_audio(audio['bytes'])
            if "轉錄錯誤" not in user_text: 
                st.session_state.user_prompt = user_text

    # =========================================================
    # 3. 核心執行邏輯 (只有在有指令時才執行)
    # =========================================================
    # city
    if 'user_prompt' in st.session_state and st.session_state.user_prompt:
        prompt = st.session_state.user_prompt.replace('臺', '台')
        # 簡單偵測城市 (Python 字串處理)
        detected_city = None
        for c in TAIWAN_CITIES:
            if c in prompt:
                detected_city = c
                break
        st.session_state.detected_city = detected_city
        
        st.markdown(f'<div class="user-command-text">👤 使用者提問：<br>{prompt}</div>', unsafe_allow_html=True)
        
        with st.spinner("🤖 Claude 正在分析需求..."):
            try:
                # --- STEP A: 呼叫 Agent ---
                res = get_mcp_vision_insight(prompt)
                
                # --- STEP B: 取得 SQL 並存檔 ---
                sql_query = res.get('sql', '')
                st.session_state.generated_sql = sql_query
                
                # 預設空的 DataFrame 以防報錯
                product_df = pd.DataFrame()
                df = pd.DataFrame()

                # --- STEP C: 執行查詢與解析 ---
                if sql_query:
                    # 一次解析所有資訊
                    sql_info = parse_sql_context(sql_query) 
                    
                    # 存入 session_state 供後續或其他元件使用
                    st.session_state.product_keywords = sql_info["tags"]
                    st.session_state.current_city = sql_info["city"]
                    st.session_state.data_source = sql_info["source_name"]
                    st.session_state.raw_table = sql_info["table"]

                    # 執行主查詢 (快照數據)
                    df = query_data_via_duckdb(sql_query)

                    # 4. 根據表名決定如何抓取趨勢數據 (Trend Data)
                    if sql_info['table'] == 'city_summary':
                        product_df = get_city_monthly_data(sql_info['city']) 
                        print(f"🌆 [UI 連動] 城市總體分析: {sql_info['city']}")
                    elif sql_info['tags']:
                        product_df = get_product_monthly_data(
                            target_categories=sql_info['tags'], 
                            city_name=sql_info['city'], 
                            table_name=sql_info['table']
                        )
                        print(f"📊 [UI 連動] 標籤: {sql_info['tags']} | 城市: {sql_info['city']} | 來源表: {sql_info['table']}")

                # =========================================================
                # 4. 顯示結果區 (Insight + 表格 + 圖表)
                # =========================================================
                
                # 決定主要顯示用的 DataFrame (優先用格式穩定的趨勢表)
                display_df = product_df if not product_df.empty else df

                if isinstance(display_df, pd.DataFrame) and not display_df.empty:
                    # 從 session_state 取回乾淨的標籤資訊
                    current_city = st.session_state.current_city
                    data_source_name = st.session_state.data_source
                    product_keywords = st.session_state.product_keywords

                    # A. 顧問導讀
                    st.subheader("💡 顧問導讀")
                    raw_insight = res.get('insight', '未取得內容')
                    html_ready_text = raw_insight.strip().replace('\n', '<br>')
                    st.markdown(f'<div class="insight-box">{html_ready_text}</div>', unsafe_allow_html=True)
                    
                    # B. 數據來源標籤
                    st.markdown(f"""
                        <div style="margin: 10px 0;">
                            <span style="background: rgba(88, 166, 255, 0.1); color: #ffffff; padding: 5px 10px; border-radius: 15px; border: 1px solid #ffffff; font-size: 1.2em;">
                                 來源：{data_source_name} | 區域：{current_city}
                            </span>
                        </div>
                    """, unsafe_allow_html=True)

                    # D. 標準化表格結構
                    final_table = standardize_table_structure(display_df, data_source_name, current_city)


                    # --- E. 📈 自動趨勢繪圖 (僅顯示月份簡潔版) ---
                    if 'Month' in display_df.columns or '月份' in final_table.columns:
                        st.subheader("📈 月度趨勢圖")
                        
                        import plotly.express as px
                        import plotly.graph_objects as go

                        plot_df = final_table.copy()
                        if '月份' in plot_df.columns:
                            # 1. 準備格式：只取月份並加上 "月" 字，確保排序正確
                            # 這裡假設你的「月份」欄位是數字 1~12
                            plot_df['月份排序'] = plot_df['月份'].astype(int)
                            plot_df = plot_df.sort_values('月份排序')
                            plot_df['顯示月份'] = plot_df['月份排序'].astype(str) + "月"
                            
                            # 2. 決定 Y 軸數值
                            y_axis = '銷售金額_百萬' if '銷售金額_百萬' in plot_df.columns else '發票占比'
                            # 將數值轉為 M 單位（僅顯示用）
                            plot_df['y_display_m'] = plot_df[y_axis]

                            # 3. 建立 Plotly 圖表
                            fig = px.line(
                                plot_df, 
                                x='顯示月份', 
                                y=y_axis, 
                                markers=True,
                                text='y_display_m' 
                            )

                            # 4. 定製顏色風格 (使用你的招牌藍色 #58a6ff)
                            fig.update_traces(
                                line=dict(color='#1CBFFF', width=3, shape='spline'), # spline 讓線條更圓滑
                                marker=dict(size=8, color='#65E8FF', line=dict(width=2, color='#0d1117')),
                                texttemplate='%{text}M',
                                textposition="top center",
                                hovertemplate='月份: %{x}<br>銷額: %{y:,.0f}',
                                customdata=plot_df['y_display_m']
                            )

                            # 5. 設定版面配置
                            fig.update_layout(
                                hovermode="x unified",
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)',
                                margin=dict(l=0, r=0, t=30, b=20),
                                height=300, # 稍微調低高度，讓畫面更緊湊
                                xaxis=dict(
                                    tickformat='%-m',   # ✅ 顯示 1 2 3 4
                                    dtick='M1',
                                    showgrid=False, 
                                    color='#8b949e', 
                                    title="",
                                    tickmode='linear' # 強制顯示每一個月份
                                ),
                                yaxis=dict(
                                    showgrid=True, 
                                    gridcolor='rgba(139, 148, 158, 0.1)',
                                    color='#8b949e',
                                    title="",
                                    zeroline=False,
                                    ticksuffix=" M",
                                    rangemode='tozero'
                                )
                            )

                            # 顯示圖表
                            st.plotly_chart(fig, width=True, config={'displayModeBar': False})

                    
                    
                    # E. 顯示表格
                    title_text = f"📋 統計數據表：{', '.join(product_keywords)}" if product_keywords else "📋 統計數據表"
                    st.subheader(title_text)
                    st.dataframe(final_table, width=True, hide_index=True)

                elif sql_query: 
                    st.warning("查無相關數據 (SQL 執行結果為空)")

                # --- STEP F: 偵探模式 (除錯用) ---
                with st.expander("🕵️ 偵探模式 (檢查解析與 SQL)", expanded=False):
                    st.write(f"**鎖定分類:** {st.session_state.product_keywords}")
                    st.write(f"**偵測城市:** {st.session_state.get('current_city', '全台')}")
                    st.code(sql_query, language="sql")

            except Exception as e:
                st.error(f"執行流程發生錯誤: {str(e)}")
                import traceback
                st.text(traceback.format_exc())
# --- 右側：3/4 泡泡圖看板 ---
with right_col:

    # --- 1. 取得連動狀態 ---
    detected_city = st.session_state.get('detected_city', None)
    location_label = detected_city if (detected_city and str(detected_city) != "None") else "全台"

    raw_keywords = st.session_state.get('product_keywords', [])
    target_set = set([str(k).strip().replace("'", "").replace('"', "") for k in raw_keywords if k])
    
    st.subheader(f"{location_label} 消費品類分佈分析")

    # --- 2. 數據獲取 ---
    bubble_df = get_bubble_chart_data(detected_city)

    if bubble_df is not None and not bubble_df.empty and 'year_month' in bubble_df.columns:
        # 數據排序
        bubble_df = bubble_df.sort_values(['year_month', 'total_amt'], ascending=[True, False])

        # --- 3. 座標軸跨度計算 (視野擴張邏輯) ---
        avg_x = bubble_df['avg_order_value'].mean()
        avg_y = bubble_df['total_amt'].mean()
        
        x_min, x_max = bubble_df['avg_order_value'].min(), bubble_df['avg_order_value'].max()
        y_min, y_max = bubble_df['total_amt'].min(), bubble_df['total_amt'].max()
        
        x_span = x_max - x_min if x_max != x_min else x_max
        y_span = y_max - y_min if y_max != y_min else y_max
        
        # 💡 關鍵：左右上下各留 20%~40% 空間，確保半徑 70 的泡泡不掉出去
        x_range = [x_min - (x_span * 0.05), x_max + (x_span * 0.1)]
        y_range = [y_min - (y_span * 0.05), y_max + (y_span * 0.1)]

        # --- 4. 關鍵字凸顯邏輯 ---
        raw_keywords = st.session_state.get('product_keywords', [])
        target_set = set([str(k).strip().replace("'", "").replace('"', "") for k in raw_keywords if k])
        is_hit = any(str(cat).strip() in target_set for cat in bubble_df['category'].unique())
        
        if is_hit:
            bubble_df['is_target'] = bubble_df['category'].apply(
                lambda x: '🎯 Highlight' if str(x).strip() in target_set else 'General'
            )
            color_param, color_map, c_scale = "is_target", {'🎯 Highlight': '#FF007F', 'General': '#65E8FF'}, None
        else:
            color_param, color_map, c_scale = "total_amt", None, "Viridis"

        # --- 5. 建立動畫圖表 ---
        fig = px.scatter(
            bubble_df,
            x="avg_order_value", y="total_amt", size="total_inv_cnt",
            color=color_param, color_discrete_map=color_map, color_continuous_scale=c_scale,
            hover_name="category", text="category",
            animation_frame="year_month", animation_group="category",
            template="plotly_dark",
            range_x=x_range, range_y=y_range,
            size_max=70,
            labels={"avg_order_value": "均發票金額", "total_amt": "銷售金額", "total_inv_cnt": "發票張數","year_month":"年月"}
        )

        # --- 6. 佈局與四象限背景 ---
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=50, b=100), height=800,
            coloraxis_showscale=False,
            xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False,tickformat=","),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False, tickformat=","),

            # 調整動畫速度設定
            updatemenus=[{
                "type": "buttons",
                "showactive": False,
                "x": 0.1, "y": 0,
                "xanchor": "right", "yanchor": "top",
                "pad": {"t": 85, "r": 10},
                # 🟢 新增：調整按鈕文字顏色與大小
                "font": {"color": "#1636CB", "size": 14}, 
                # 🟢 新增：調整按鈕背景色 (可選)
                "bgcolor": "rgba(255, 255, 255, 1)",
                "bordercolor": "#ffffff",
                "buttons": [
                    {
                        "label": "▶ Play",
                        "method": "animate",
                        "args": [None, {
                            "frame": {"duration": 1000, "redraw": False}, # 每個月份停 1.2 秒
                            "fromcurrent": True, 
                            "transition": {
                                "duration": 1000,          # 用 1 秒的時間慢慢飛過去
                                "easing": "cubic-in-out"   # 平滑移動曲線
                            }
                        }]
                    },
                    {
                        "label": "|| Pause",
                        "method": "animate",
                        "args": [[None], {
                            "frame": {"duration": 0, "redraw": False},
                            "mode": "immediate",
                            "transition": {"duration": 0}
                        }]
                    }
                ]
            }],
            sliders=[{
                "currentvalue": {"prefix": "時間週期: "},
                "steps": [
                    {"args": [[f.name], {
                        "frame": {"duration": 0, "redraw": False},
                        "mode": "immediate",
                        "transition": {"duration": 800, "easing": "cubic-in-out"}
                    }],
                    "label": f.name, "method": "animate"} for f in fig.frames
                ]
            }]
        )

        # 四象限背景矩形
        q_colors = ["rgba(0, 255, 0, 0.1)", "rgba(255, 255, 0, 0.1)", "rgba(255, 165, 0, 0.1)", "rgba(255, 0, 0, 0.1)"]
        fig.add_shape(type="rect", x0=avg_x, y0=avg_y, x1=x_range[1], y1=y_range[1], fillcolor=q_colors[0], layer="below", line_width=0)
        fig.add_shape(type="rect", x0=x_range[0], y0=avg_y, x1=avg_x, y1=y_range[1], fillcolor=q_colors[1], layer="below", line_width=0)
        fig.add_shape(type="rect", x0=avg_x, y0=y_range[0], x1=x_range[1], y1=avg_y, fillcolor=q_colors[2], layer="below", line_width=0)
        fig.add_shape(type="rect", x0=x_range[0], y0=y_range[0], x1=avg_x, y1=avg_y, fillcolor=q_colors[3], layer="below", line_width=0)

        # 輔助線
        fig.add_vline(
            x=avg_x, 
            line=dict(color="Cyan", width=1, dash="dash"),
            annotation_text=f"平均發票金額: {avg_x:.0f}", # 這裡顯示文字
            annotation_position="top left",          # 標籤位置
            annotation_font_color="Cyan"
        )

        # 將金額轉換為萬 
        avg_y_display = f"{avg_y/1000000:.1f}百萬" if avg_y >= 10000 else f"{avg_y:.0f}"

        fig.add_hline(
            y=avg_y, 
            line=dict(color="Cyan", width=1, dash="dash"),
            annotation_text=f"均銷: {avg_y_display}", # 💡 改用簡稱「均銷」
            annotation_position="top left",
            annotation_font_color="Cyan"
        )

        # --- 7. 修復後的 Trace 更新 (cliponaxis 移出 marker) ---
        fig.update_traces(
            cliponaxis=False,  # ✅ 放在第一層，不再報錯
            textposition='top center',
            textfont=dict(
            family="Arial, sans-serif", # 字體族
            size=15,                   # 字體大小
            color="rgba(230, 240, 255, 0.95)"              # 字體顏色
            ),
            marker=dict(line=dict(width=1, color='white')),

            hovertemplate=
                "均發票金額: %{x:,.0f}<br>"
                "銷售金額: %{y:,.0f}<br>"
                "發票張數: %{marker.size:,}"
                "<extra></extra>"

        )
        
        
        # 渲染圖表
        st.plotly_chart(fig, width=True, config={'displayModeBar': False})
        
        st.markdown('</div>', unsafe_allow_html=True)



    elif bubble_df is not None and 'year_month' not in bubble_df.columns:
        st.error("🚨 數據錯誤：缺少 'year_month' 欄位。")
    else:
        st.info("🔭 正在載入初始全台數據...")

    # --- 底部解讀指南 ---
    st.markdown("""
    <div style="
        color: #65E8FF; 
        font-size: 20px; 
        padding: 10px 20px; 
        border-left: 3px solid #65E8FF; /* 左側精緻裝飾線 */
        background: transparent; 
        margin: 20px 0;
        line-height: 1.5;
        letter-spacing: 1px;
    ">
        <b style="color: #FFFFFF; font-weight: 700;">● 戰情解讀：</b> 
        <span style="opacity: 0.8;">橫軸越右單價越高，縱軸越上市場越大，泡泡大小代表交易熱度。</span>
    </div>
    """, unsafe_allow_html=True)
    # --- 佔比趨勢折線圖區塊 ---
    st.divider()
    trend_left_col, trend_right_col = st.columns(2, gap="large")
    
    # 使用 session_state 中的城市資訊，確保連動
    detected_city = st.session_state.get('detected_city', None)
    location_label = detected_city if detected_city else "全台"

    
    # 左側：Top 10 大分類佔比趨勢
    with trend_left_col:
        st.subheader(f"{location_label} Top 10 大分類佔比趨勢")
        trend_main_df = get_trend_data('main_category_summary', 'category', detected_city)
        
        if trend_main_df is not None and not trend_main_df.empty:
            fig_trend_main = px.line(
                trend_main_df,
                x="month",
                y="ratio",
                color="category",
                markers=True,
                template="plotly_dark",
                labels={
                    "month": "月份",
                    "ratio": "發票佔比 (%)",
                    "category": "大分類"
                }
            )
            
            fig_trend_main.update_layout(
                height=700,
                margin=dict(b=150),
                font=dict(size=14),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    tickformat='%-m',
                    dtick='M1',
                    gridcolor='rgba(0, 255, 255, 0.1)',
                    zeroline=False,
                    showgrid=True,
                    color='#00FFFF',
                    title_font=dict(color='#FFFFFF')
                ),
                yaxis=dict(
                    gridcolor='rgba(0, 255, 255, 0.1)',
                    zeroline=False,
                    showgrid=True,
                    color='#00FFFF',
                    title_font=dict(color='#FFFFFF'),
                    tickformat='.1%'  # 格式化為百分比
                ),
                legend=dict(
                    font=dict(color='#FFFFFF', size=18), # 純白字
                    bgcolor='rgba(40, 44, 52, 0.8)',      # 深色半透明背景，更有質感
                    bordercolor='rgba(255, 255, 255, 0.3)', # 淡淡的白邊
                    borderwidth=1,
                    orientation='h',
                    yanchor='top',
                    y=-0.2,           # 讓它離圖表近一點
                    xanchor='center',
                    x=0.5,
                    itemwidth=40
                )
            )
            
            # 更新線條顏色為亮青色系
            colors = px.colors.qualitative.Set3
            for i, trace in enumerate(fig_trend_main.data):
                trace.line.color = colors[i % len(colors)]
                trace.marker.color = colors[i % len(colors)]
            
            st.plotly_chart(fig_trend_main, width=True)
            
            # 記錄大分類趨勢圖到對話歷史
            if st.session_state.chat_history:
                last_entry = st.session_state.chat_history[-1]
                if 'charts' not in last_entry:
                    last_entry['charts'] = []
                last_entry['charts'].append({
                    'type': 'line_chart',
                    'title': f'{location_label} Top 10 大分類佔比趨勢',
                    'data_points': len(trend_main_df)
                })
        else:
            st.warning("暫無大分類趨勢數據")
    
    # 右側：Top 10 中分類佔比趨勢
    with trend_right_col:

        # 1. 取得數據
        target_table = st.session_state.get('raw_table','subcategory') 
        target_tags = st.session_state.get('product_keywords', [])
        first_tag = target_tags[0] if target_tags else None
        
        # 這裡確保傳進去的是正確的 table name
        trend_df = get_smart_trend_data(target_table, first_tag, st.session_state.get('current_city'))
        
        if trend_df is not None and not trend_df.empty:
            header_label = f"「{first_tag}」占比趨勢" if first_tag else f"{location_label} TOP 10 中分類佔比趨勢"
            st.subheader(f"{header_label}")

            import plotly.express as px
            
            # 2. 建立折線圖 (與左側風格一致)
            fig_trend = px.line(
                trend_df,
                x="month",
                y="ratio",
                color="subcategory",
                markers=True, # 顯示點點
                template="plotly_dark",
                labels={"month": "月份", "ratio": "發票佔比 (%)", "subcategory": "中分類"}
            )

            # 3. 調整風格：亮青色霓虹感
            fig_trend.update_layout(
                height=700, # 跟左邊一樣的高度
                margin=dict(b=150), # 留空間給大圖例
                font=dict(size=14),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                
                # X 軸：青色發光感
                xaxis=dict(
                    tickformat='%m',
                    dtick='M1',
                    gridcolor='rgba(0, 255, 255, 0.1)',
                    zeroline=False,
                    showgrid=True,
                    color='#00FFFF',
                    title_font=dict(color='#FFFFFF')
                ),
                
                # Y 軸：百分比格式
                yaxis=dict(
                    gridcolor='rgba(0, 255, 255, 0.1)',
                    zeroline=False,
                    showgrid=True,
                    color='#00FFFF',
                    title_font=dict(color='#FFFFFF'),
                    tickformat='.1%'
                ),
                
                # 圖例：超大字體 (size=24) + 霓虹邊框
                legend=dict(
                    font=dict(color='#FFFFFF', size=18), # 純白字
                    bgcolor='rgba(40, 44, 52, 0.8)',      # 深色半透明背景，更有質感
                    bordercolor='rgba(255, 255, 255, 0.3)', # 淡淡的白邊
                    borderwidth=1,
                    orientation='h',
                    yanchor='top',
                    y=-0.2,           # 讓它離圖表近一點
                    xanchor='center',
                    x=0.5,
                    itemwidth=40
                )
            )
            
            # 4. 強制線條配色 (使用亮色系)
            colors = px.colors.qualitative.Set3
            for i, trace in enumerate(fig_trend.data):
                trace.line.color = colors[i % len(colors)]
                trace.marker.color = colors[i % len(colors)]
                trace.line.width = 3 # 粗一點比較亮
            
            st.plotly_chart(fig_trend, width=True)
            
        else:
            st.warning("暫無中分類趨勢數據")
    
    # --- 全中分類佔比方格矩陣圖 ---
    st.divider()
    st.subheader(f"{location_label} 全中分類佔比分析")

    all_sub_df = get_all_subcategory_ratio(detected_city)

    if all_sub_df is not None and not all_sub_df.empty:
        # 💡 修正 1：先依照發票張數進行降序排列，確保排序邏輯正確
        df_plot = all_sub_df.copy().sort_values("total_inv_cnt", ascending=False).reset_index(drop=True)
        
        # 單位轉換（可選，配合你之前的需求）
        if "amt" in df_plot.columns:
            df_plot = df_plot.rename(columns={"amt": "銷售金額"})
        
        # 💡 修正 2：建立 display_text 並直接作為一個欄位，讓 px.treemap 自己去抓
        df_plot["display_text"] = df_plot.apply(
            lambda x: f"{x['subcategory']}<br>{x['ratio']:.2%}", axis=1
        )

        valid_sub_in_df = set(df_plot['subcategory'].unique())
        hits_in_subcategory = [k for k in target_set if k in valid_sub_in_df]
        is_subcategory_hit = len(hits_in_subcategory) > 0

        # 顏色邏輯判定
        if is_subcategory_hit:
            df_plot['hl_score'] = df_plot['subcategory'].apply(
                lambda x: 1.0 if x in hits_in_subcategory else 0.2
            )
            color_col = "hl_score"
            c_scale_tree = ["#2c2c2c", "#00FFFF", "#FF007F"]
        else:
            color_col = "total_inv_cnt"
            c_scale_tree = "Viridis"

        # --- 渲染鎖定資訊 (保持原樣) ---
        if is_subcategory_hit:
            hit_rows = df_plot[df_plot['subcategory'].isin(hits_in_subcategory)]
            insight_html = "".join([f"""
                <div style="color: #65E8FF; font-size: 20px; padding: 10px 20px; border-left: 3px solid #65E8FF; margin: 10px 0;">
                    <b style="color: #FFFFFF;">● 鎖定中類：{row.subcategory}</b> 
                    <span style="opacity: 0.8; margin-left: 10px;">佔比分析：{row.ratio:.2%}</span>
                </div>
            """ for row in hit_rows.itertuples()])
            st.markdown(insight_html, unsafe_allow_html=True)

        # 💡 修正 3：將 display_text 加入 hover_data，避免 update_traces 強行覆蓋
        fig_treemap = px.treemap(
            df_plot,
            path=[px.Constant("全中分類"), "subcategory"],
            values="total_inv_cnt",
            color=color_col,
            color_continuous_scale=c_scale_tree,
            template="plotly_dark",
            custom_data=["銷售金額", "ratio", "display_text"] # 💡 把文字包進來
        )
        
        fig_treemap.update_traces(
            # 💡 修正 4：改用屬性對應，而非直接傳入 list
            texttemplate="%{customdata[2]}", # 💡 使用剛才傳入的 display_text
            textposition="middle center",      
            insidetextfont=dict(size=20, color="white", family="Arial"),
            hovertemplate=(
                "<b>中分類：%{label}</b><br>"
                "發票張數：%{value:,}<br>"
                "銷額：%{customdata[0]:,.0f}<br>"
                "發票佔比：%{customdata[1]:.2%}"
                "<extra></extra>"
            ),
            pathbar_visible=False              
        )
        
        fig_treemap.update_layout(
            height=600,
            margin=dict(l=10, r=10, t=10, b=10),
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_treemap, width=True)
        
    else:
        st.warning("暫無數據")
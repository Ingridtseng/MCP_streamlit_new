import streamlit as st  
import os
import duckdb
import pandas as pd
from anthropic import Anthropic
import json
from dotenv import load_dotenv
import re


# 載入環境變數
load_dotenv()

# 初始化 Anthropic 客戶端
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# --- 全域變數：只會加載一次 ---

@st.cache_resource
# def init_resources():
#     """
#     初始化所有靜態資源：
#     1. 載入銷售數據到 DuckDB
#     2. 載入分類描述檔並轉換為 AI 導航地圖 (Semantic Index)
#     """
#     print("⏳ [System] 正在初始化資源 (SQL 數據庫 & AI 導航地圖)...")
#     base_path = os.path.dirname(os.path.abspath(__file__))
    
#     # 1. 建立記憶體資料庫連線
#     con = duckdb.connect(database=':memory:')
    
#     # 加載銷售數據表
#     data_files = {
#         'city_summary': 'city_summary.xlsx',
#         'main_category_summary': 'main_category_summary.xlsx',
#         'sub_category': 'sub_category.xlsx'
#     }
    
#     for table_name, file_name in data_files.items():
#         path = os.path.join(base_path, file_name)
#         if os.path.exists(path):
#             df_tmp = pd.read_excel(path)
#             # 預處理：統一「台」字與空白
#             if 'city' in df_tmp.columns:
#                 df_tmp['city_clean'] = df_tmp['city'].astype(str).str.strip().str.replace('臺', '台')
#             for col in ['category', 'subcategory']:
#                 if col in df_tmp.columns:
#                     df_tmp[col] = df_tmp[col].astype(str).str.strip()
#             con.register(table_name, df_tmp)
    
#     # 2. 處理「AI 導航地圖」(原本的 category_des.xlsx)
#     # 我們在這裡就把 Excel 轉成 AI 讀得懂的字串，並快取起來
#     dict_path = os.path.join(base_path, 'category_des.xlsx')
#     nav_map_str = "字典讀取失敗或檔案不存在。"
    
#     if os.path.exists(dict_path):
#         df_def = pd.read_excel(dict_path).fillna('')
#         knowledge_list = []
#         for _, row in df_def.iterrows():
#             c_val = str(row.get('category', '')).strip()
#             s_val = str(row.get('subcategory', '')).strip()
#             desc = str(row.get('description', '')).strip()
            
#             # 💡 這裡加上更明確的路由標記
#             if s_val and s_val.lower() != 'nan':
#                 # 注意：中類對應表格 sub_category，欄位是 subcategory
#                 entry = f"- [中類] 名稱: '{s_val}', 對應表: sub_category, 欄位: subcategory, 涵蓋內容: {desc}"
#                 knowledge_list.append(entry)
#             elif c_val and c_val.lower() != 'nan':
#                 # 注意：大類對應表格 main_category_summary，欄位是 category
#                 entry = f"- [大類] 名稱: '{c_val}', 對應表: main_category_summary, 欄位: category, 涵蓋內容: {desc}"
#                 knowledge_list.append(entry)
#         nav_map_str = "\n".join(knowledge_list)

#     print("✅ [System] 資源初始化完成。")
    
#     # 回傳一個字典包裹所有資源
#     return {
#         "db_conn": con,
#         "ai_nav_map": nav_map_str
#     }
@st.cache_resource
def init_resources():
    """
    初始化所有靜態資源：
    1. 載入銷售數據到 DuckDB (實體 Table 模式)
    2. 載入分類描述檔並轉換為 AI 導航地圖 (Semantic Index)
    """
    print("⏳ [System] 正在初始化資源 (SQL 數據庫 & AI 導航地圖)...")
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # 1. 建立記憶體資料庫連線
    con = duckdb.connect(database=':memory:')
    
    # 加載銷售數據表
    data_files = {
        'city_summary': 'city_summary.xlsx',
        'main_category_summary': 'main_category_summary.xlsx',
        'sub_category': 'sub_category.xlsx'
    }
    
    for table_name, file_name in data_files.items():
        path = os.path.join(base_path, file_name)
        if os.path.exists(path):
            try:
                df_tmp = pd.read_excel(path)
                
                # 預處理：統一「台」字與空白
                if 'city' in df_tmp.columns:
                    df_tmp['city_clean'] = df_tmp['city'].astype(str).str.strip().str.replace('臺', '台')
                
                for col in ['category', 'subcategory']:
                    if col in df_tmp.columns:
                        df_tmp[col] = df_tmp[col].astype(str).str.strip()
                
                # --- 【關鍵修正：建立實體表而非虛擬視圖】 ---
                # 先將 DataFrame 註冊為臨時名稱
                temp_view_name = f"temp_{table_name}"
                con.register(temp_view_name, df_tmp)
                
                # 使用 SQL 建立真正的 DuckDB Table，這能解決序列化報錯 (PandasScan error)
                con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM {temp_view_name}")
                
                # 建立完實體表後，可以解除註冊臨時名稱以節省空間
                con.unregister(temp_view_name)
                print(f"✅ [Table] 已建立實體表: {table_name}")
                
            except Exception as e:
                print(f"❌ [Error] 載入 {file_name} 失敗: {str(e)}")
    
    # 2. 處理「AI 導航地圖」(原本的 category_des.xlsx)
    dict_path = os.path.join(base_path, 'category_des.xlsx')
    nav_map_str = "字典讀取失敗或檔案不存在。"
    
    if os.path.exists(dict_path):
        try:
            df_def = pd.read_excel(dict_path).fillna('')
            knowledge_list = []
            for _, row in df_def.iterrows():
                c_val = str(row.get('category', '')).strip()
                s_val = str(row.get('subcategory', '')).strip()
                desc = str(row.get('description', '')).strip()
                
                # 路由標記：讓 AI 知道要去哪個表查
                if s_val and s_val.lower() != 'nan' and s_val != '':
                    entry = f"- [中類] 名稱: '{s_val}', 對應表: sub_category, 欄位: subcategory, 涵蓋內容: {desc}"
                    knowledge_list.append(entry)
                elif c_val and c_val.lower() != 'nan' and c_val != '':
                    entry = f"- [大類] 名稱: '{c_val}', 對應表: main_category_summary, 欄位: category, 涵蓋內容: {desc}"
                    knowledge_list.append(entry)
            nav_map_str = "\n".join(knowledge_list)
        except Exception as e:
            nav_map_str = f"字典處理錯誤: {str(e)}"

    print("✅ [System] 資源初始化完成。")
    
    # 回傳字典包裹資源
    return {
        "db_conn": con,
        "ai_nav_map": nav_map_str
    }

def query_data_via_duckdb(sql_query):
    # 確保 sql_query 是字串且不為空
    if not isinstance(sql_query, str) or not sql_query.strip():
        return pd.DataFrame()  # 回傳空表而不是 None，確保後續 .empty 不報錯

    try:
        # 1. 取得現有連線
        resources = init_resources()
        con = resources["db_conn"]
        print(f"🚀 [DEBUG] 執行查詢:\n{sql_query}")

        # 2. 執行查詢
        result_rel = con.execute(sql_query)
        df = result_rel.df()
        
        return df

    except Exception as e:
        print(f"❌ [ERROR] DuckDB 查詢錯誤: {str(e)}")
        # 🔥 關鍵修正：出錯時回傳空的 DataFrame，而不是字串
        # 這樣你的 if df.empty 判斷會過，但不會報 AttributeError
        return pd.DataFrame()

def get_mcp_vision_insight(user_text):
    """
    MCP 核心 - 二階段處理
    """
    # 0. 取得快取的資源 (這裡不會重新讀取 Excel)
    resources = init_resources()
    nav_map = resources["ai_nav_map"]  # 這是給 AI 看的說明書
    con = resources["db_conn"]         # 這是 DuckDB 連線
    
    user_text = user_text.replace('臺', '台')
    # ==========================================
    # Phase 1: 生成 SQL (SQL Architect)
    # ==========================================
    
    # 定義強制使用的 SQL 模板
    sql_template = """
    SELECT 
        year, 
        month
        {COLUMNS_BLOCK}
        SUM(amt) as "銷售金額",
        SUM(qty) as "銷售數量",
        ROUND(SUM(amt) / NULLIF(SUM(inv_cnt), 0), 1) as "均發票金額",
        SUM(inv_cnt) as "發票張數",
        SUM(barcode_cnt) as "消費人數"
    FROM {TABLE_NAME}
    WHERE {WHERE_CLAUSE}
    GROUP BY year, month {GROUP_BY_BLOCK}
    ORDER BY year, month
    """

    sql_gen_system_prompt = f"""
你是一位精通 DuckDB 的高階資料工程師。你的任務是將用戶的自然語言需求轉換為標準 SQL。

### 📌 核心任務
**閱讀需求 -> 從清單選字 -> 判斷查詢情境 -> 套用模板生成 SQL。**

---
### 🚨 絕對死令 (Fatal Rules)
1. **禁止聯想**：你不是在做語意分析，你是在做「字串查找」。如果用戶說「火雞肉飯」，你必須從清單中找出最可能包含「火雞肉飯」的類別，並使用該類別的**名稱**。
2. **字元對齊**：清單中的名稱若包含前綴，SQL 裡的字串必須 **一字不漏、包含空格** 地寫入。
3. **單選原則**：嚴禁在 SQL 裡出現兩個以上的類別，嚴禁使用 OR。只選「最像」的一個。


### 📂 1. 合法分類清單 (The Source of Truth)
⚠️ **絕對禁令：嚴禁移除、修改或忽略名稱中的前綴 **。

必須與下方清單「逐字對齊」，包含前方的英數字與空格。
---------------------------------------------------
{nav_map}
---------------------------------------------------

---

### 🛠️ 2. 資料表架構說明
1. **`sub_category` 表**：查詢具體中類（如：防曬與美白）。
   - 關鍵欄位：`subcategory` (⚠️ 欄位名無底線)
2. **`main_category_summary` 表**：查詢廣泛大類（如：酒類）。
   - 關鍵欄位：`category`
3. **`city_summary` 表**：僅查詢城市總體數據（無具體品項）。
   - 關鍵欄位：僅 `city_clean`

---

### ⚙️ 3. 填空分流規則 (嚴格執行)

請根據用戶提問，判定屬於哪種情境並套用對應邏輯：

#### ● 情況 A：指定商品 + 指定城市 (例：台北火雞肉飯)
- **表名**：依清單判定為 `sub_category` 或 `main_category_summary`
- **{{COLUMNS_BLOCK}}**：`, city_clean as city, [分類欄位名],`
- **{{WHERE_CLAUSE}}**：`city_clean LIKE '城市%' AND [分類欄位名] = '清單選定字'`
- **{{GROUP_BY_BLOCK}}**：`, city_clean, [分類欄位名]`

#### ● 情況 B：指定商品 + 全台分析 (例：主食消費趨勢)
- **表名**：同上
- **{{COLUMNS_BLOCK}}**：`, '全台灣' as city, [分類欄位名],`
- **{{WHERE_CLAUSE}}**：`[分類欄位名] = '清單選定字'`
- **{{GROUP_BY_BLOCK}}**：`, [分類欄位名]`

#### ● 情況 C：無特定商品 + 指定城市 (例：嘉義消費分析)
- **表名**：`city_summary`
- **{{COLUMNS_BLOCK}}**：`, city_clean as city,`
- **{{WHERE_CLAUSE}}**：`city_clean LIKE '城市%'`
- **{{GROUP_BY_BLOCK}}**：`, city_clean`
- **⚠️ 警告**：此情況禁止出現 subcategory 或 category 欄位。

---

### ⚖️ 4. 決策優先順序與約束 (強迫單選)
1. **絕對唯一性 (Strict Singleton)**：不論用戶提問涵蓋多少潛在範疇，你「必須且只能」從清單中挑選「一個」最核心、最像的分類。
2. **禁止聯集**：嚴禁在 WHERE 子句中使用 `OR`、`IN (item1, item2)` 或多行過濾。
3. **匹配策略**：若無直接對應，採取「就近原則」。例如「火雞肉飯」-> 判定為「主食」，則只輸出 `'主食'`，不可同時輸出 `'便當'`。
4. **字串匹配**：`WHERE` 條件的分類名稱必須與清單**一字不差**；城市名稱請使用 `LIKE '城市%'`（例如：`LIKE '台北%'`）。

---

### 🧠 5. 生成前思考步驟 (Internal Monologue)
在生成 SQL 前，請在心中執行以下抉擇：
1. 用戶的商品標的是什麼？
2. 在 {nav_map} 中，哪一個字串與該標的相關性最高 (Top 1)？
3. 選定該字串後，放棄所有其他備選方案。


---
### 🚫 6. 負面約束 (Negative Constraints)
- **禁止聯覺**：WHERE 條件中，針對分類欄位的比較操作符 `= '清單選定字'` 只能出現「一次」。
- **禁止多選**：如果你的 SQL 中出現了 `OR` 或是重複的分類條件，這將被視為嚴重的語法錯誤。
- **嚴禁解釋**：只輸出 SQL 代碼，不准回答「我幫你選了XX與YY」。

---

5. **強制 SQL 模板**：
{sql_template}

請直接回傳 SQL 代碼，不要有 Markdown。
"""

    generated_sql = "" 

    try:
        # 呼叫 API 生成 SQL
        msg_sql = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001", 
            max_tokens=1000, 
            system=sql_gen_system_prompt,
            messages=[{"role": "user", "content": f"用戶需求：{user_text}\n請根據字典選字並生成 SQL。"}]
        )
        
        # 2. 將全文存入 generated_sql
        generated_sql = msg_sql.content[0].text.strip()

        # 3. 從 SELECT 開始截取，並切掉 Markdown 尾巴
        # 使用 re.search 找第一個 SELECT，找不到就維持現狀
        sql_match = re.search(r"(SELECT.*)", generated_sql, re.IGNORECASE | re.DOTALL)
        
        if sql_match:
            # 覆蓋為：從 SELECT 開始的部分，並切掉之後的 ```
            generated_sql = sql_match.group(1).split("```")[0].strip()
        # 如果沒對應到 SELECT，則維持第 2 步拿到的原始全文

    except Exception as e:
        return {"error": f"SQL生成失敗: {str(e)}"}

    # ==========================================
    # Phase 2: 執行 SQL
    # ==========================================
    
    try:
        df_result = query_data_via_duckdb(generated_sql)
        
        if isinstance(df_result, str):
            return {
                "sql": generated_sql,
                "insight": f"⚠️ 查詢失敗：{df_result}",
                "title": "錯誤",
                "chart_type": "none"
            }
        
        if df_result is None or df_result.empty:
            return {
                "sql": generated_sql,
                "insight": "查無數據。請確認您的關鍵字是否在字典檔案中。",
                "title": "無數據",
                "chart_type": "none"
            }
            
        data_context = df_result.to_markdown(index=False)
        
    except Exception as e:
        return {"insight": f"執行錯誤: {str(e)}", "sql": generated_sql}

    # ==========================================
    # Phase 3: 生成 Insight
    # ==========================================

    insight_system_prompt = f"""
你是一位資深商業數據顧問，請「嚴格依照下列分析框架」產出顧問導讀。
⚠️ 不可跳步、不可自由發揮。

【用戶問題】
{user_text}

【數據】
{data_context}

【分析流程（必須依序執行）】
1️⃣ 趨勢判讀  
說明整體是上升 / 下降 / 持平  
若有月份，請明確指出「起始 vs 最新」

2️⃣ 高低點觀察  
指出最高與最低月份（若有）
簡述可能原因（限一句）

3️⃣ 商業解讀  
從消費行為或市場角度解釋這個現象  
避免過度推測，不可編造外部事實

4️⃣ 行動建議（1–2 點）  
給「可執行」的建議  
不可使用空泛詞語（如：持續觀察）

【輸出規範】
Insight 必須為 4 個段落
每段 1–2 句
使用繁體中文
語氣專
業、穩定、偏顧問風格

【回傳 JSON】
{{
  "title": "一句話重點標題",
  "insight": "250字內的完整顧問導讀",
  "chart_type": "bar | line | pie",
  "x_axis": "year_month",
  "y_axis": "銷售金額"
}}
"""


    try:
        msg_insight = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001", 
            max_tokens=1500, 
            system=insight_system_prompt,
            messages=[{"role": "user", "content": "分析數據並回傳 JSON"}]
        )
        
        res_text = msg_insight.content[0].text
        start_idx = res_text.find('{')
        end_idx = res_text.rfind('}') + 1
        final_json = json.loads(res_text[start_idx:end_idx])
        final_json['sql'] = generated_sql
        
        return final_json

    except Exception as e:
        return {"sql": generated_sql, "insight": f"Insight 錯誤: {str(e)}"}
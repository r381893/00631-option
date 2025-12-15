import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import matplotlib.pyplot as plt
from matplotlib import rcParams, font_manager
import yfinance as yf
from datetime import date, timedelta

# ======== 修正中文亂碼 (設置 Matplotlib 字體) ========
chinese_fonts = ['Microsoft JhengHei', 'DFKai-SB', 'BiauKai', 'Arial Unicode MS']
font_found = False
for font in chinese_fonts:
    if font in font_manager.findSystemFonts(fontpaths=None, fontext='ttf'):
        rcParams['font.sans-serif'] = [font]
        font_found = True
        break
        
if not font_found:
    rcParams['font.sans-serif'] = chinese_fonts

rcParams['axes.unicode_minus'] = False

# ======== 頁面設定 ========
st.set_page_config(page_title="00631L 避險計算器", layout="wide")

# ======== CSS 樣式 ========
st.markdown(
    """
    <style>
    /* 基礎字體設定 */
    html, body, .stApp, .stApp * {
        font-family: 'Microsoft JhengHei', 'DFKai-SB', sans-serif !important;
        font-size: 15px;
    }
    
    :root {
        --card-bg: #ffffff;
        --page-bg: #f3f6fb;
        --accent: #0b5cff;
        --muted: #6b7280;
        --success: #10b981;
        --danger: #ef4444;
    }
    body { background-color: var(--page-bg); }
    
    /* 主標題 */
    .title {
        font-size: 32px;
        font-weight: 800;
        color: #04335a;
        margin-bottom: 4px;
        padding-top: 10px;
    }
    .subtitle {
        color: var(--muted);
        margin-top: -8px;
        margin-bottom: 20px;
        font-size: 16px;
    }
    
    /* 卡片樣式 */
    .card {
        background: var(--card-bg);
        padding: 18px 22px;
        border-radius: 12px;
        box-shadow: 0 8px 30px rgba(11,92,255,0.08);
        margin-bottom: 20px;
    }
    
    /* 區塊標題 */
    .section-title {
        font-size: 18px;
        font-weight: 700;
        color: #04335a;
        margin-bottom: 12px;
        border-bottom: 2px solid #eaeef7;
        padding-bottom: 5px;
    }
    
    /* 統計卡片 */
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px 20px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .stat-value {
        font-size: 24px;
        font-weight: 700;
    }
    .stat-label {
        font-size: 13px;
        opacity: 0.9;
    }
    
    /* 損益顏色 */
    .profit { color: #10b981; font-weight: bold; }
    .loss { color: #ef4444; font-weight: bold; }
    
    /* 倉位標籤 */
    .buy-tag { 
        background-color: #dbeafe; 
        color: #1d4ed8; 
        padding: 2px 8px; 
        border-radius: 4px; 
        font-weight: bold;
        font-size: 13px;
    }
    .sell-tag { 
        background-color: #fee2e2; 
        color: #dc2626; 
        padding: 2px 8px; 
        border-radius: 4px; 
        font-weight: bold;
        font-size: 13px;
    }
    .call-tag {
        background-color: #fef3c7;
        color: #d97706;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 13px;
    }
    .put-tag {
        background-color: #e0e7ff;
        color: #4338ca;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 13px;
    }
    
    hr { border: 0; height: 1px; background: #eaeef7; margin: 14px 0; }
    
    /* 按鈕樣式 */
    .stButton>button {
        border-radius: 8px;
        height: 38px;
        font-size: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">🛡️ 00631L 避險計算器</div>'
            '<div class="subtitle">使用選擇權組合策略保護 00631L 持股</div>', unsafe_allow_html=True)

# ======== 常數設定 ========
POSITIONS_FILE = "hedge_positions.json"
OPTION_MULTIPLIER = 50.0  # 選擇權每點 50 元
ETF_SHARES_PER_LOT = 1000  # 1張 = 1000股
LEVERAGE_00631L = 2.0  # 00631L 為 2 倍槓桿 ETF
PRICE_STEP = 100.0

# ======== 網路資料抓取函式 ========
@st.cache_data(ttl=600)
def get_tse_index_price(ticker="^TWII"):
    """從 Yahoo Finance 獲取加權指數的最新價格"""
    try:
        tse_ticker = yf.Ticker(ticker)
        info = tse_ticker.info
        price = info.get('regularMarketPrice') or info.get('regularMarketPreviousClose')
        if price and price > 1000:
            return float(price)
        return None
    except Exception as e:
        return None

@st.cache_data(ttl=600)
def get_00631L_price():
    """從 Yahoo Finance 獲取 00631L 的最新價格"""
    try:
        etf_ticker = yf.Ticker("00631L.TW")
        info = etf_ticker.info
        price = info.get('regularMarketPrice') or info.get('regularMarketPreviousClose')
        if price and price > 0:
            return float(price)
        return None
    except Exception as e:
        return None

# ======== 載入與儲存函式 ========
def load_data(fname=POSITIONS_FILE):
    """載入倉位資料"""
    if os.path.exists(fname):
        try:
            with open(fname, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            st.error(f"讀取儲存檔失敗: {e}", icon="❌")
            return None
    return None

def save_data(data, fname=POSITIONS_FILE):
    """儲存倉位資料"""
    try:
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}", icon="❌")
        return False

# ======== 初始化 session state ========
if "option_positions" not in st.session_state:
    st.session_state.option_positions = []  # 選擇權倉位列表

if "etf_lots" not in st.session_state:
    st.session_state.etf_lots = 0.0
if "etf_cost" not in st.session_state:
    st.session_state.etf_cost = 0.0
if "etf_current_price" not in st.session_state:
    st.session_state.etf_current_price = None
    
if "tse_index_price" not in st.session_state:
    st.session_state.tse_index_price = None

if "hedge_ratio" not in st.session_state:
    st.session_state.hedge_ratio = 0.2  # 預設避險比例

if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False

# ********* 初始抓取價格 *********
if st.session_state.tse_index_price is None:
    tse_price = get_tse_index_price()
    if tse_price and tse_price > 1000:
        st.session_state.tse_index_price = tse_price
    else:
        st.session_state.tse_index_price = 23000.0  # 備用值

if st.session_state.etf_current_price is None:
    etf_price = get_00631L_price()
    if etf_price:
        st.session_state.etf_current_price = etf_price
    else:
        st.session_state.etf_current_price = 100.0  # 備用值

# ********* 自動載入資料 *********
if not st.session_state.data_loaded:
    saved_data = load_data()
    if saved_data:
        st.session_state.etf_lots = float(saved_data.get("etf_lots", 0.0))
        st.session_state.etf_cost = float(saved_data.get("etf_cost", 0.0))
        st.session_state.hedge_ratio = float(saved_data.get("hedge_ratio", 0.2))
        st.session_state.option_positions = saved_data.get("option_positions", [])
        # 如果儲存的現價有值則使用，否則用自動抓取的
        saved_price = saved_data.get("etf_current_price", 0.0)
        if saved_price > 0:
            st.session_state.etf_current_price = float(saved_price)
    st.session_state.data_loaded = True

# ======== 側邊欄設定 ========
st.sidebar.markdown("## 📊 00631L 庫存設定")

# 儲存舊值
old_etf_lots = st.session_state.etf_lots
old_etf_cost = st.session_state.etf_cost
old_etf_current = st.session_state.etf_current_price
old_hedge_ratio = st.session_state.hedge_ratio

etf_lots = st.sidebar.number_input(
    "持有張數",
    value=float(st.session_state.etf_lots),
    step=0.1,
    min_value=0.0,
    format="%.2f",
    help="持有的 00631L 張數 (支援小數，如 0.5 張 = 500股)"
)

etf_cost = st.sidebar.number_input(
    "平均成本 (元)",
    value=float(st.session_state.etf_cost) if st.session_state.etf_cost > 0 else float(st.session_state.etf_current_price),
    step=0.1,
    min_value=0.0,
    format="%.2f",
    help="00631L 的平均買入成本"
)

etf_current = st.sidebar.number_input(
    "現價 (元)",
    value=float(st.session_state.etf_current_price),
    step=0.1,
    min_value=0.0,
    format="%.2f",
    help="00631L 的現價（自動抓取或手動輸入）"
)

st.sidebar.markdown("---")
st.sidebar.markdown("## 🛡️ 避險設定")

hedge_ratio = st.sidebar.number_input(
    "每張 ETF 避險口數",
    value=float(st.session_state.hedge_ratio),
    step=0.01,
    min_value=0.0,
    max_value=1.0,
    format="%.2f",
    help="每 1 張 00631L 需要多少口選擇權避險"
)

# 計算建議避險口數
suggested_hedge_lots = etf_lots * hedge_ratio

st.sidebar.markdown(f"""
<div style='padding: 10px; background-color: #f0f9ff; border-radius: 8px; margin-top: 10px;'>
    <p style='margin:0; font-weight:700; color:#0369a1;'>📌 建議避險口數</p>
    <p style='margin:5px 0 0 0; font-size:24px; font-weight:800; color:#0c4a6e;'>{suggested_hedge_lots:.1f} 口</p>
    <p style='margin:0; font-size:12px; color:#64748b;'>({etf_lots:.2f} 張 × {hedge_ratio:.2f})</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("## 📈 模擬設定")

PRICE_RANGE = st.sidebar.number_input(
    "模擬範圍 (±點數)",
    value=1500,
    step=100,
    min_value=100,
)

# 更新 session state
st.session_state.etf_lots = etf_lots
st.session_state.etf_cost = etf_cost
st.session_state.etf_current_price = etf_current
st.session_state.hedge_ratio = hedge_ratio

# 當前指數
center = st.session_state.tse_index_price

st.sidebar.markdown(f"""
<div style='font-size:14px; margin-top: 10px;'>
    <p><b>當前指數:</b> <span style="color:#04335a; font-weight:700;">{center:,.1f}</span></p>
</div>
""", unsafe_allow_html=True)

# ********* 自動儲存 *********
if (etf_lots != old_etf_lots or 
    etf_cost != old_etf_cost or 
    etf_current != old_etf_current or
    hedge_ratio != old_hedge_ratio):
    save_data({
        "etf_lots": etf_lots,
        "etf_cost": etf_cost,
        "etf_current_price": etf_current,
        "hedge_ratio": hedge_ratio,
        "option_positions": st.session_state.option_positions
    })
    st.sidebar.success("✅ 已自動儲存", icon="💾")

# ======== 主頁面 ========

# ======== 檔案操作區 ========
with st.container():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">📂 檔案操作</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        if st.button("🔄 重新載入", use_container_width=True):
            saved_data = load_data()
            if saved_data:
                st.session_state.etf_lots = float(saved_data.get("etf_lots", 0.0))
                st.session_state.etf_cost = float(saved_data.get("etf_cost", 0.0))
                st.session_state.hedge_ratio = float(saved_data.get("hedge_ratio", 0.2))
                st.session_state.option_positions = saved_data.get("option_positions", [])
                st.success("✅ 已載入資料")
                st.rerun()
            else:
                st.info("找不到儲存檔")
    with col2:
        if st.button("💾 手動儲存", use_container_width=True):
            ok = save_data({
                "etf_lots": st.session_state.etf_lots,
                "etf_cost": st.session_state.etf_cost,
                "etf_current_price": st.session_state.etf_current_price,
                "hedge_ratio": st.session_state.hedge_ratio,
                "option_positions": st.session_state.option_positions
            })
            if ok:
                st.success(f"✅ 已儲存到 {POSITIONS_FILE}")
    with col3:
        if st.button("🧹 清空所有", use_container_width=True):
            st.session_state.option_positions = []
            st.session_state.etf_lots = 0.0
            st.session_state.etf_cost = 0.0
            st.session_state.hedge_ratio = 0.2
            st.success("已清空所有資料")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ======== 00631L 庫存摘要 ========
if etf_lots > 0:
    etf_shares = etf_lots * ETF_SHARES_PER_LOT
    etf_market_value = etf_shares * etf_current
    etf_cost_value = etf_shares * etf_cost
    etf_unrealized_pnl = etf_market_value - etf_cost_value
    pnl_pct = (etf_unrealized_pnl / etf_cost_value * 100) if etf_cost_value > 0 else 0
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">💰 00631L 庫存摘要</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("持有張數", f"{etf_lots:.2f} 張", f"{etf_shares:,.0f} 股")
    with col2:
        st.metric("市值", f"{etf_market_value:,.0f} 元")
    with col3:
        st.metric("成本", f"{etf_cost_value:,.0f} 元")
    with col4:
        delta_color = "normal" if etf_unrealized_pnl >= 0 else "inverse"
        st.metric("未實現損益", f"{etf_unrealized_pnl:+,.0f} 元", f"{pnl_pct:+.2f}%", delta_color=delta_color)
    
    st.markdown(f"""
    <div style='margin-top: 10px; padding: 10px; background-color: #fef3c7; border-radius: 8px;'>
        <span style='font-weight:700; color:#92400e;'>📌 建議避險:</span> 
        持有 {etf_lots:.2f} 張，建議買入 <b>{suggested_hedge_lots:.1f} 口</b> 賣權進行保護
    </div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ======== 新增選擇權倉位 ========
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown('<div class="section-title">➕ 新增選擇權倉位</div>', unsafe_allow_html=True)

with st.form(key="add_option_form"):
    col1, col2, col3, col4, col5 = st.columns([1.2, 1.2, 1.5, 1, 1.5])
    
    with col1:
        opt_type = st.selectbox("類型", ["買權 (Call)", "賣權 (Put)"], key="new_opt_type")
    with col2:
        opt_direction = st.radio("方向", ["買進", "賣出"], horizontal=True, key="new_opt_direction")
    with col3:
        # 預設履約價為當前指數的整數
        default_strike = round(center / 100) * 100
        opt_strike = st.number_input("履約價", min_value=0.0, step=100.0, value=float(default_strike), key="new_opt_strike")
    with col4:
        opt_lots = st.number_input("口數", min_value=1, step=1, value=1, key="new_opt_lots")
    with col5:
        opt_premium = st.number_input("權利金 (點)", min_value=0.0, step=1.0, value=0.0, key="new_opt_premium")
    
    submitted = st.form_submit_button("✅ 新增倉位", use_container_width=True)
    
    if submitted:
        new_position = {
            "type": "Call" if "Call" in opt_type else "Put",
            "direction": opt_direction,
            "strike": float(opt_strike),
            "lots": int(opt_lots),
            "premium": float(opt_premium)
        }
        st.session_state.option_positions.append(new_position)
        # 自動儲存
        save_data({
            "etf_lots": st.session_state.etf_lots,
            "etf_cost": st.session_state.etf_cost,
            "etf_current_price": st.session_state.etf_current_price,
            "hedge_ratio": st.session_state.hedge_ratio,
            "option_positions": st.session_state.option_positions
        })
        st.success("已新增選擇權倉位")
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# ======== 現有選擇權倉位 ========
if st.session_state.option_positions:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">📋 現有選擇權倉位</div>', unsafe_allow_html=True)
    
    # 計算權利金收支
    total_premium_in = 0.0  # 收入（賣出）
    total_premium_out = 0.0  # 支出（買進）
    
    for i, pos in enumerate(st.session_state.option_positions):
        col_info, col_delete = st.columns([5, 1])
        
        type_tag = "call-tag" if pos["type"] == "Call" else "put-tag"
        type_label = "買權" if pos["type"] == "Call" else "賣權"
        dir_tag = "buy-tag" if pos["direction"] == "買進" else "sell-tag"
        
        premium_value = pos["premium"] * pos["lots"] * OPTION_MULTIPLIER
        if pos["direction"] == "賣出":
            total_premium_in += premium_value
            premium_display = f"+{premium_value:,.0f}"
            premium_style = "color: #10b981;"
        else:
            total_premium_out += premium_value
            premium_display = f"-{premium_value:,.0f}"
            premium_style = "color: #ef4444;"
        
        with col_info:
            st.markdown(f"""
            <div style='padding: 8px 0; display: flex; align-items: center; gap: 10px;'>
                <span style='color: #64748b;'>#{i+1}</span>
                <span class='{dir_tag}'>{pos['direction']}</span>
                <span class='{type_tag}'>{type_label}</span>
                <span style='font-weight: 700;'>{pos['strike']:,.0f}</span>
                <span>×{pos['lots']} 口</span>
                <span>@{pos['premium']:.0f} 點</span>
                <span style='margin-left: auto; font-weight: 700; {premium_style}'>{premium_display} 元</span>
            </div>
            """, unsafe_allow_html=True)
        
        with col_delete:
            if st.button("刪除", key=f"del_opt_{i}", type="secondary"):
                st.session_state.option_positions.pop(i)
                save_data({
                    "etf_lots": st.session_state.etf_lots,
                    "etf_cost": st.session_state.etf_cost,
                    "etf_current_price": st.session_state.etf_current_price,
                    "hedge_ratio": st.session_state.hedge_ratio,
                    "option_positions": st.session_state.option_positions
                })
                st.rerun()
        
        st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)
    
    # 權利金收支摘要
    net_premium = total_premium_in - total_premium_out
    net_style = "profit" if net_premium >= 0 else "loss"
    
    st.markdown(f"""
    <div style='margin-top: 10px; padding: 12px; background-color: #f8fafc; border-radius: 8px;'>
        <div style='display: flex; justify-content: space-between; margin-bottom: 5px;'>
            <span>賣出權利金收入:</span>
            <span class='profit'>+{total_premium_in:,.0f} 元</span>
        </div>
        <div style='display: flex; justify-content: space-between; margin-bottom: 5px;'>
            <span>買進權利金支出:</span>
            <span class='loss'>-{total_premium_out:,.0f} 元</span>
        </div>
        <hr style='margin: 8px 0;'>
        <div style='display: flex; justify-content: space-between; font-weight: 700; font-size: 16px;'>
            <span>淨權利金:</span>
            <span class='{net_style}'>{net_premium:+,.0f} 元</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

# ======== 損益計算與圖表 ========
if etf_lots > 0 or st.session_state.option_positions:
    
    # 計算損益函數
    def calc_option_pnl(pos, settlement_price):
        """計算單一選擇權倉位的損益"""
        strike = pos["strike"]
        lots = pos["lots"]
        premium = pos["premium"]
        
        # 計算內含價值
        if pos["type"] == "Call":
            intrinsic = max(0.0, settlement_price - strike)
        else:  # Put
            intrinsic = max(0.0, strike - settlement_price)
        
        # 計算損益 = (內含價值 - 權利金) × 口數 × 乘數
        if pos["direction"] == "買進":
            pnl = (intrinsic - premium) * lots * OPTION_MULTIPLIER
        else:  # 賣出
            pnl = (premium - intrinsic) * lots * OPTION_MULTIPLIER
        
        return pnl
    
    def calc_etf_pnl(index_price, base_index, etf_lots, etf_cost, etf_current):
        """計算 00631L 在不同指數價位下的損益"""
        if etf_lots <= 0 or base_index <= 0:
            return 0.0
        
        # 指數變動比例
        index_change_pct = (index_price - base_index) / base_index
        
        # 00631L 是 2 倍槓桿，價格變動 = 指數變動 × 2
        etf_price_change_pct = index_change_pct * LEVERAGE_00631L
        
        # 新的 ETF 價格
        new_etf_price = etf_current * (1 + etf_price_change_pct)
        
        # 計算損益 = (新價格 - 成本) × 股數
        shares = etf_lots * ETF_SHARES_PER_LOT
        profit = (new_etf_price - etf_cost) * shares
        
        return profit
    
    # 計算價格範圍
    offsets = np.arange(-PRICE_RANGE, PRICE_RANGE + 1e-6, PRICE_STEP)
    prices = [center + float(off) for off in offsets]
    
    # 計算各價位損益
    etf_profits = []
    option_profits = []
    combined_profits = []
    
    for p in prices:
        # ETF 損益
        etf_pnl = calc_etf_pnl(p, center, etf_lots, etf_cost, etf_current)
        etf_profits.append(etf_pnl)
        
        # 選擇權組合損益
        opt_pnl = sum(calc_option_pnl(pos, p) for pos in st.session_state.option_positions)
        option_profits.append(opt_pnl)
        
        # 總損益
        combined_profits.append(etf_pnl + opt_pnl)
    
    # ======== 損益曲線圖 ========
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">📈 損益曲線</div>', unsafe_allow_html=True)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 繪製各曲線
    if etf_lots > 0:
        ax.plot(prices, etf_profits, label="00631L", color="#3b82f6", linewidth=2, linestyle="--", alpha=0.7)
    
    if st.session_state.option_positions:
        ax.plot(prices, option_profits, label="選擇權組合", color="#f59e0b", linewidth=2, linestyle="--", alpha=0.7)
    
    ax.plot(prices, combined_profits, label="組合總損益", color="#10b981", linewidth=3)
    
    # 零線
    ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
    ax.axvline(x=center, color='red', linestyle='--', linewidth=1, alpha=0.5, label=f"現價 {center:,.0f}")
    
    ax.set_xlabel("結算指數", fontsize=12)
    ax.set_ylabel("損益 (元)", fontsize=12)
    ax.set_title("組合損益曲線", fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    # 格式化 Y 軸
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
    
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # ======== 損益試算表 ========
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">📊 損益試算表</div>', unsafe_allow_html=True)
    
    # 建立表格資料
    table_data = {
        "結算指數": [f"{p:,.0f}" for p in prices],
        "指數變動": [f"{p - center:+,.0f}" for p in prices],
    }
    
    if etf_lots > 0:
        table_data["00631L"] = [f"{pnl:+,.0f}" for pnl in etf_profits]
    
    if st.session_state.option_positions:
        table_data["選擇權組合"] = [f"{pnl:+,.0f}" for pnl in option_profits]
    
    table_data["總損益"] = [f"{pnl:+,.0f}" for pnl in combined_profits]
    
    df = pd.DataFrame(table_data)
    
    # 樣式函數
    def style_pnl(val):
        try:
            num = float(val.replace(",", "").replace("+", ""))
            if num > 0:
                return 'color: #10b981; font-weight: bold'
            elif num < 0:
                return 'color: #ef4444; font-weight: bold'
        except:
            pass
        return ''
    
    # 顯示表格
    styled_df = df.style.map(style_pnl, subset=["總損益"])
    if etf_lots > 0:
        styled_df = styled_df.map(style_pnl, subset=["00631L"])
    if st.session_state.option_positions:
        styled_df = styled_df.map(style_pnl, subset=["選擇權組合"])
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

# ======== 頁尾資訊 ========
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; color: #64748b; font-size: 13px;'>
    <p>💡 選擇權乘數: {OPTION_MULTIPLIER:.0f} 元/點 | 00631L 槓桿: {LEVERAGE_00631L}x</p>
    <p>資料更新時間: {date.today().strftime('%Y-%m-%d')}</p>
</div>
""", unsafe_allow_html=True)

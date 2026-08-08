import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="منصة SMC التفاعلية للأسواق", layout="wide")

# القائمة الجانبية لإدارة الأصول والأطر الزمنية
st.sidebar.header("⚙️ إعدادات التداول")

ASSETS = {
    "🥇 الذهب (XAU/USD)": "GC=F",
    "🛢️ النفط الخام (Crude Oil)": "CL=F",
    "📈 مؤشر النازداك (NASDAQ)": "NQ=F",
    "📊 مؤشر الداو جونز (US30)": "YM=F",
}

TIMEFRAMES = {
    "5 دقائق (5M)": {"interval": "5m", "period": "1d"},
    "15 دقيقة (15M)": {"interval": "15m", "period": "5d"},
    "ساعة (1H)": {"interval": "1h", "period": "7d"},
    "4 ساعات (4H)": {"interval": "1h", "period": "60d"},
    "يومي (1D)": {"interval": "1d", "period": "1y"},
}

selected_asset_label = st.sidebar.selectbox("اختر الأصل المالي:", list(ASSETS.keys()))
symbol = ASSETS[selected_asset_label]

selected_tf_label = st.sidebar.selectbox("اختر الفريم المالي للتداول:", list(TIMEFRAMES.keys()))

st.title(f"🎯 لوحة إشارات وتحليل {selected_asset_label}")

@st.cache_data(ttl=30)
def load_smc_data(ticker, interval, period):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # 1. المتوسطات المتحركة الهيكلية
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # 2. حساب ATR لحساب الستوب والأهداف ديناميكياً
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['ATR'] = np.max(ranges, axis=1).rolling(14).mean()
    
    # 3. حساب مؤشر RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    # 4. رصد الفجوات السعرية (FVG)
    df['Bullish_FVG'] = (df['Low'] > df['High'].shift(2))
    df['Bearish_FVG'] = (df['High'] < df['Low'].shift(2))

    # 5. رصد سحب السيولة (Liquidity Sweep)
    df['Lowest_10'] = df['Low'].shift(1).rolling(10).min()
    df['Highest_10'] = df['High'].shift(1).rolling(10).max()
    
    df['Bull_Sweep'] = (df['Low'] < df['Lowest_10']) & (df['Close'] > df['Lowest_10'])
    df['Bear_Sweep'] = (df['High'] > df['Highest_10']) & (df['Close'] < df['Highest_10'])

    return df

main_tf_params = TIMEFRAMES[selected_tf_label]
df = load_smc_data(symbol, main_tf_params['interval'], main_tf_params['period'])

last = df.iloc[-1]
prev_bars = df.iloc[-5:]

close_p = float(last['Close'])
ema50_p = float(last['EMA_50'])
ema200_p = float(last['EMA_200'])
atr_p = float(last['ATR']) if not np.isnan(last['ATR']) else (close_p * 0.002)
rsi_p = float(last['RSI'])

# خوارزمية التوافق والذكاء (Confluence Engine)
score_buy = 0
score_sell = 0

# شروط الشراء
if close_p > ema50_p: score_buy += 25
if ema50_p > ema200_p: score_buy += 15
if prev_bars['Bullish_FVG'].any(): score_buy += 25
if prev_bars['Bull_Sweep'].any(): score_buy += 25
if 40 <= rsi_p <= 65: score_buy += 10

# شروط البيع
if close_p < ema50_p: score_sell += 25
if ema50_p < ema200_p: score_sell += 15
if prev_bars['Bearish_FVG'].any(): score_sell += 25
if prev_bars['Bear_Sweep'].any(): score_sell += 25
if 35 <= rsi_p <= 60: score_sell += 10

st.subheader("🎯 الصفقة المقترحة والتوصية (SMC Signal)")

if score_buy >= 70 and score_buy > score_sell:
    sl = close_p - (atr_p * 1.5)
    tp1 = close_p + (atr_p * 2.0)
    tp2 = close_p + (atr_p * 4.0)
    
    st.success(f"### 🟢 فرصة شراء عالية الثقة على {selected_asset_label} ({score_buy}% Confluence)")
    st.write("📌 **الأسباب:** توافق الاتجاه + وجود فجوة سعرية (FVG) / سحب سيولة للقاع.")
    
    c1, c2 = st.columns(2)
    c1.metric("سعر الدخول الحالي", f"${close_p:.2f}")
    c2.metric("وقف الخسارة (SL)", f"${sl:.2f}")
    c1.metric("الهدف الأول (TP1)", f"${tp1:.2f}")
    c2.metric("الهدف الثاني (TP2)", f"${tp2:.2f}")

elif score_sell >= 70 and score_sell > score_buy:
    sl = close_p + (atr_p * 1.5)
    tp1 = close_p - (atr_p * 2.0)
    tp2 = close_p - (atr_p * 4.0)
    
    st.error(f"### 🔴 فرصة بيع عالية الثقة على {selected_asset_label} ({score_sell}% Confluence)")
    st.write("📌 **الأسباب:** توافق الاتجاه الهابط + اختراق فجوة سعرية / سحب سيولة للقمة.")
    
    c1, c2 = st.columns(2)
    c1.metric("سعر الدخول الحالي", f"${close_p:.2f}")
    c2.metric("وقف الخسارة (SL)", f"${sl:.2f}")
    c1.metric("الهدف الأول (TP1)", f"${tp1:.2f}")
    c2.metric("الهدف الثاني (TP2)", f"${tp2:.2f}")

else:
    st.warning(f"### ⚪ لا توجد صفقة واضحة حالياً على {selected_asset_label}")
    st.info(f"جاهزية الشراء: **{score_buy}%** | جاهزية البيع: **{score_sell}%** (يلزم وصول النسبة إلى 70%+ لظهور الصفقة).")

st.divider()

# رسم الشارت التفاعلي
st.subheader(f"📈 الشارت التفاعلي لـ {selected_asset_label} - فريم {selected_tf_label}")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

fig.add_trace(go.Candlestick(
    x=df.index, open=df['Open'], high=df['High'],
    low=df['Low'], close=df['Close'], name=selected_asset_label
), row=1, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='orange', width=1.5), name="EMA 50"), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df['EMA_200'], line=dict(color='blue', width=1.5), name="EMA 200"), row=1, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple', width=1.5), name="RSI"), row=2, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, use_container_width=True)

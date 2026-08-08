import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

# إعداد التحديث التلقائي (كل 60 ثانية)
st_autorefresh(interval=60000, key="datarefresh")

st.set_page_config(page_title="منصة SMC التفاعلية", layout="wide")

# القائمة الجانبية
st.sidebar.header("⚙️ إعدادات التداول")
ASSETS = {"🥇 الذهب (XAU/USD)": "GC=F", "🪙 البيتكوين (BTC/USD)": "BTC-USD", "🛢️ النفط": "CL=F"}
TIMEFRAMES = {"5 دقائق": "5m", "15 دقيقة": "15m", "ساعة": "1h", "4 ساعات": "1h", "يومي": "1d"}

selected_asset = st.sidebar.selectbox("الأصل:", list(ASSETS.keys()))
symbol = ASSETS[selected_asset]
interval = st.sidebar.selectbox("الفريم:", list(TIMEFRAMES.keys()))
tf_code = TIMEFRAMES[interval]

@st.cache_data(ttl=60)
def load_data(ticker, interval):
    df = yf.download(ticker, period="5d" if interval in ["5m", "15m"] else "1mo", interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    df['EMA_50'] = df['Close'].ewm(span=50).mean()
    df['EMA_200'] = df['Close'].ewm(span=200).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    return df

df = load_data(symbol, tf_code)
last = df.iloc[-1]

# منطق الصفقة
signal = None
sl, tp1, tp2 = 0, 0, 0
close = float(last['Close'])
atr = float(last['ATR'])

if close > float(last['EMA_50']):
    signal = "BUY"
    sl, tp1, tp2 = close - (atr*1.5), close + (atr*2), close + (atr*4)
elif close < float(last['EMA_50']):
    signal = "SELL"
    sl, tp1, tp2 = close + (atr*1.5), close - (atr*2), close - (atr*4)

# العرض
st.title(f"📈 تحليل {selected_asset}")
col1, col2 = st.columns([1, 3])

with col1:
    if signal == "BUY":
        st.success("🟢 فرصة شراء")
        st.metric("دخول", f"{close:.2f}")
        st.metric("Stop Loss", f"{sl:.2f}")
        st.metric("Target", f"{tp1:.2f}")
    elif signal == "SELL":
        st.error("🔴 فرصة بيع")
        st.metric("دخول", f"{close:.2f}")
        st.metric("Stop Loss", f"{sl:.2f}")
        st.metric("Target", f"{tp1:.2f}")

with col2:
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    
    # إضافة المؤشرات
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], name="EMA 50", line=dict(color='yellow', width=1)))
    
    # رسم خطوط الصفقة على الشارت
    if signal:
        fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="SL")
        fig.add_hline(y=tp1, line_dash="dash", line_color="green", annotation_text="TP1")
        fig.add_hline(y=tp2, line_dash="solid", line_color="green", annotation_text="TP2")

    # تحسينات التفاعل
    fig.update_layout(
        template="plotly_dark",
        xaxis=dict(
            rangeslider=dict(visible=False),
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1h", step="hour", stepmode="backward"),
                    dict(count=1, label="1d", step="day", stepmode="backward"),
                    dict(step="all")
                ])
            )
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

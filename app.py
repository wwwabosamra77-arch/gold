import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="أداة توصيات وتحليل الذهب", layout="wide")

st.title("🥇 لوحة تحليل وإشارات الذهب (XAU/USD)")

symbol = "GC=F"

TIMEFRAMES = {
    "15 دقيقة (15M)": {"interval": "15m", "period": "5d"},
    "ساعة (1H)": {"interval": "1h", "period": "7d"},
    "4 ساعات (4H)": {"interval": "1h", "period": "60d"},
    "يومي (1D)": {"interval": "1d", "period": "1y"},
}

selected_tf = st.sidebar.selectbox("اختر فريم التداول لحساب الصفقة:", list(TIMEFRAMES.keys()))

@st.cache_data(ttl=60)
def load_data(ticker, interval, period):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # حساب المتوسطات المتحركة
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # حساب RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # حساب ATR لتحديد وقف الخسارة والأهداف
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    return df

main_tf_params = TIMEFRAMES[selected_tf]
df = load_data(symbol, main_tf_params['interval'], main_tf_params['period'])

# جلب البيانات الحالية
last_row = df.iloc[-1]
close_price = float(last_row['Close'])
rsi_val = float(last_row['RSI'])
ema20 = float(last_row['EMA_20'])
ema50 = float(last_row['EMA_50'])
ema200 = float(last_row['EMA_200'])
atr_val = float(last_row['ATR']) if not np.isnan(last_row['ATR']) else 5.0

# منطق توليد الصفقات والتوصيات
signal = "NO_SIGNAL"
signal_text = "⚪ لا توجد صفقة واضحة الآن - السوق في حالة تذبذب"
signal_color = "info"

# شروط الشراء
if close_price > ema50 and ema20 > ema50 and rsi_val > 45 and rsi_val < 68:
    signal = "BUY"
    signal_text = "🟢 فرصة شراء (BUY SETUP)"
    stop_loss = close_price - (atr_val * 1.5)
    tp1 = close_price + (atr_val * 1.5)
    tp2 = close_price + (atr_val * 3.0)

# شروط البيع
elif close_price < ema50 and ema20 < ema50 and rsi_val < 55 and rsi_val > 32:
    signal = "SELL"
    signal_text = "🔴 فرصة بيع (SELL SETUP)"
    stop_loss = close_price + (atr_val * 1.5)
    tp1 = close_price - (atr_val * 1.5)
    tp2 = close_price - (atr_val * 3.0)

# عرض التوصية المباشرة
st.subheader("🎯 صفقة التداول المقترحة (Live Signal)")

if signal == "BUY":
    st.success(f"### {signal_text}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("سعر الدخول المقترح", f"${close_price:.2f}")
    c2.metric("وقف الخسارة (SL)", f"${stop_loss:.2f}")
    c3.metric("الهدف الأول (TP1)", f"${tp1:.2f}")
    c4.metric("الهدف الثاني (TP2)", f"${tp2:.2f}")

elif signal == "SELL":
    st.error(f"### {signal_text}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("سعر الدخول المقترح", f"${close_price:.2f}")
    c2.metric("وقف الخسارة (SL)", f"${stop_loss:.2f}")
    c3.metric("الهدف الأول (TP1)", f"${tp1:.2f}")
    c4.metric("الهدف الثاني (TP2)", f"${tp2:.2f}")

else:
    st.warning(f"### {signal_text}")
    st.write("ينصح بانتظار إغلاق شمعة جديدة أو خروج المؤشرات من منطقة التذبذب.")

st.divider()

# الرسم البياني
st.subheader(f"📈 الرسم البياني - فريم {selected_tf}")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

fig.add_trace(go.Candlestick(
    x=df.index, open=df['Open'], high=df['High'],
    low=df['Low'], close=df['Close'], name="XAU/USD"
), row=1, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], line=dict(color='yellow', width=1), name="EMA 20"), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='orange', width=1.5), name="EMA 50"), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df['EMA_200'], line=dict(color='blue', width=1.5), name="EMA 200"), row=1, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple', width=1.5), name="RSI"), row=2, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, use_container_width=True)

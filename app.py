import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="أداة تحليل الذهب Multi-TF", layout="wide")

st.title("🥇 لوحة تحليل الذهب المتعددة الأطر الزمنية (XAU/USD)")

symbol = "GC=F"

TIMEFRAMES = {
    "أسبوعي (1W)": {"interval": "1wk", "period": "2y"},
    "يومي (1D)": {"interval": "1d", "period": "1y"},
    "4 ساعات (4H)": {"interval": "1h", "period": "60d"},
    "ساعة (1H)": {"interval": "1h", "period": "7d"},
    "نصف ساعة (30M)": {"interval": "30m", "period": "5d"},
    "15 دقيقة (15M)": {"interval": "15m", "period": "5d"},
    "5 دقائق (5M)": {"interval": "5m", "period": "1d"},
}

selected_tf = st.sidebar.selectbox("اختر الفريم الرئيسي للعرض:", list(TIMEFRAMES.keys()))

@st.cache_data(ttl=60)
def load_data(ticker, interval, period):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # حساب المتوسطات المتحركة
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # حساب مؤشر RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

tf_summary = {}

for name, params in TIMEFRAMES.items():
    try:
        data = load_data(symbol, params['interval'], params['period'])
        if not data.empty and len(data) > 50:
            last_close = float(data['Close'].iloc[-1])
            ema_50 = float(data['EMA_50'].iloc[-1])
            ema_200 = float(data['EMA_200'].iloc[-1])
            rsi = float(data['RSI'].iloc[-1])
            
            if last_close > ema_50 and ema_50 > ema_200:
                bias = "🟢 صاعد قوي"
            elif last_close > ema_50:
                bias = "🟢 صاعد"
            elif last_close < ema_50 and ema_50 < ema_200:
                bias = "🔴 هابط قوي"
            else:
                bias = "🔴 هابط"
                
            tf_summary[name] = {"السعر": f"{last_close:.2f}", "الانحياز": bias, "RSI": f"{rsi:.1f}"}
    except Exception:
        tf_summary[name] = {"السعر": "N/A", "الانحياز": "غير متوفر", "RSI": "N/A"}

st.subheader("📊 ملخص اتجاهات الأطر الزمنية (Top-Down Bias)")
cols = st.columns(len(TIMEFRAMES))
for i, (tf_name, info) in enumerate(tf_summary.items()):
    with cols[i]:
        st.metric(label=tf_name, value=info["السعر"], delta=info["الانحياز"])
        st.caption(f"RSI: {info['RSI']}")

st.divider()

main_tf_params = TIMEFRAMES[selected_tf]
df_main = load_data(symbol, main_tf_params['interval'], main_tf_params['period'])

st.subheader(f"📈 الرسم البياني التفاعلي - فريم {selected_tf}")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

fig.add_trace(go.Candlestick(
    x=df_main.index, open=df_main['Open'], high=df_main['High'],
    low=df_main['Low'], close=df_main['Close'], name="XAU/USD"
), row=1, col=1)

fig.add_trace(go.Scatter(x=df_main.index, y=df_main['EMA_50'], line=dict(color='orange', width=1.5), name="EMA 50"), row=1, col=1)
fig.add_trace(go.Scatter(x=df_main.index, y=df_main['EMA_200'], line=dict(color='blue', width=1.5), name="EMA 200"), row=1, col=1)

fig.add_trace(go.Scatter(x=df_main.index, y=df_main['RSI'], line=dict(color='purple', width=1.5), name="RSI"), row=2, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

fig.update_layout(xaxis_rangeslider_visible=False, height=600, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, use_container_width=True)

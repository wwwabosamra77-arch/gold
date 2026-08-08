import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

# إعداد التحديث التلقائي كل 60 ثانية
st_autorefresh(interval=60000, key="datarefresh")

st.set_page_config(page_title="منصة SMC التفاعلية للأسواق", layout="wide")

# تهيئة سجل الصفقات في الذاكرة المؤقتة (Session State)
if 'trade_log' not in st.session_state:
    st.session_state.trade_log = []

# القائمة الجانبية لإدارة الأصول والأطر الزمنية
st.sidebar.header("⚙️ إعدادات التداول")

ASSETS = {
    "🥇 الذهب (XAU/USD)": "GC=F",
    "🪙 البيتكوين (BTC/USD)": "BTC-USD",
    "🛢️ النفط الخام (Crude Oil)": "CL=F",
    "📈 مؤشر النازداك (NASDAQ)": "NQ=F",
    "📊 مؤشر الداو جونز (US30)": "YM=F",
}

TIMEFRAMES = {
    "دقيقة (1M)": {"interval": "1m", "period": "1d"},
    "5 دقائق (5M)": {"interval": "5m", "period": "1d"},
    "15 دقيقة (15M)": {"interval": "15m", "period": "5d"},
    "30 دقيقة (30M)": {"interval": "30m", "period": "5d"},
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
    
    # 1. المتوسطات المتحركة
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # 2. حساب ATR
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['ATR'] = np.max(ranges, axis=1).rolling(14).mean()
    
    # 3. حساب RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 4. رصد FVG
    df['Bullish_FVG'] = (df['Low'] > df['High'].shift(2))
    df['Bearish_FVG'] = (df['High'] < df['Low'].shift(2))

    # 5. رصد Liquidity Sweep
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

# تحديد المستويات الهيكلية
swing_low = float(df['Low'].iloc[-20:-1].min())
swing_high = float(df['High'].iloc[-20:-1].max())
major_high = float(df['High'].iloc[-50:-1].max())
major_low = float(df['Low'].iloc[-50:-1].min())

# خوارزمية التوافق SMC
score_buy = 0
score_sell = 0
reasons_buy = []
reasons_sell = []

if close_p > ema50_p:
    score_buy += 25
    reasons_buy.append("السعر أعلى متوسط EMA 50")
if ema50_p > ema200_p:
    score_buy += 15
    reasons_buy.append("تقاطع إيجابي EMA 50/200")
if prev_bars['Bullish_FVG'].any():
    score_buy += 25
    reasons_buy.append("فجوة سعرية شرائية (Bullish FVG)")
if prev_bars['Bull_Sweep'].any():
    score_buy += 25
    reasons_buy.append("سحب سيولة القاع (Liquidity Sweep)")
if 40 <= rsi_p <= 65:
    score_buy += 10
    reasons_buy.append("زخم RSI إيجابي")

if close_p < ema50_p:
    score_sell += 25
    reasons_sell.append("السعر أسفل متوسط EMA 50")
if ema50_p < ema200_p:
    score_sell += 15
    reasons_sell.append("تقاطع سلبي EMA 50/200")
if prev_bars['Bearish_FVG'].any():
    score_sell += 25
    reasons_sell.append("فجوة سعرية بيعية (Bearish FVG)")
if prev_bars['Bear_Sweep'].any():
    score_sell += 25
    reasons_sell.append("سحب سيولة القمة (Liquidity Sweep)")
if 35 <= rsi_p <= 60:
    score_sell += 10
    reasons_sell.append("زخم RSI سلبي")

sl, tp1, tp2 = None, None, None
active_signal = None
entry_p = close_p
signal_reason = ""

st.subheader("🎯 الصفقة المقترحة والتوصية الحالية")

if score_buy >= 70 and score_buy > score_sell:
    active_signal = "BUY"
    sl = min(swing_low - (atr_p * 0.2), close_p - (atr_p * 1.0))
    risk = close_p - sl
    tp1 = max(swing_high, close_p + (risk * 1.5))
    tp2 = max(major_high, close_p + (risk * 3.0))
    signal_reason = " | ".join(reasons_buy)

elif score_sell >= 70 and score_sell > score_buy:
    active_signal = "SELL"
    sl = max(swing_high + (atr_p * 0.2), close_p + (atr_p * 1.0))
    risk = sl - close_p
    tp1 = min(swing_low, close_p - (risk * 1.5))
    tp2 = min(major_low, close_p - (risk * 3.0))
    signal_reason = " | ".join(reasons_sell)

# متابعة صفقات السجل المفتوحة وتحديثها
for trade in st.session_state.trade_log:
    if trade['status'] == "نشطة (Active)" and trade['asset'] == selected_asset_label:
        curr_high = float(last['High'])
        curr_low = float(last['Low'])
        
        if trade['type'] == "BUY":
            if curr_low <= trade['sl']:
                trade['status'] = "❌ خسارة (Hit SL)"
                trade['exit_reason'] = "كسر السعر القاع الهيكلي واخترق مستوى الستوب لوز."
            elif curr_high >= trade['tp1']:
                trade['status'] = "✅ نجاح (Hit TP1)"
                trade['exit_reason'] = "وصل السعر لمنطقة سيولة القمة السابقة وضرب الهدف بنجاح."
        elif trade['type'] == "SELL":
            if curr_high >= trade['sl']:
                trade['status'] = "❌ خسارة (Hit SL)"
                trade['exit_reason'] = "اخترق السعر القمة الهيكلية وأغلق اعلى خط الستوب لوز."
            elif curr_low <= trade['tp1']:
                trade['status'] = "✅ نجاح (Hit TP1)"
                trade['exit_reason'] = "وصل السعر لمنطقة سيولة القاع السابقة وضرب الهدف بنجاح."

# تسجيل الصفقة الجديدة
if active_signal:
    already_logged = any(
        t['asset'] == selected_asset_label and t['type'] == active_signal and t['status'] == "نشطة (Active)"
        for t in st.session_state.trade_log
    )
    if not already_logged:
        st.session_state.trade_log.insert(0, {
            "time": str(df.index[-1].strftime('%H:%M - %Y/%m/%d')),
            "asset": selected_asset_label,
            "type": active_signal,
            "entry": entry_p,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "status": "نشطة (Active)",
            "entry_reason": signal_reason,
            "exit_reason": "الصفقة ما زالت مستمرة وتتابع حركة الشموع الحالية."
        })

# عرض تفاصيل الصفقة الحالية بتنسيق واضح لجميع الشاشات
if active_signal == "BUY":
    rr = (tp1 - entry_p) / (entry_p - sl) if (entry_p - sl) > 0 else 0
    st.success(f"### 🟢 فرصة شراء SMC عالية الثقة ({score_buy}% Confluence)")
    st.write(f"📌 **أسباب الدخول:** {signal_reason} | **R:R:** 1:{rr:.1f}")
    
    col1, col2 = st.columns(2)
    col1.metric("🔵 سعر الدخول (Entry)", f"${entry_p:,.2f}")
    col2.metric("🔴 وقف الخسارة (SL)", f"${sl:,.2f}")
    
    col3, col4 = st.columns(2)
    col3.metric("🟢 الهدف الأول (TP1)", f"${tp1:,.2f}")
    col4.metric("🟢 الهدف الثاني (TP2)", f"${tp2:,.2f}")

elif active_signal == "SELL":
    rr = (entry_p - tp1) / (sl - entry_p) if (sl - entry_p) > 0 else 0
    st.error(f"### 🔴 فرصة بيع SMC عالية الثقة ({score_sell}% Confluence)")
    st.write(f"📌 **أسباب الدخول:** {signal_reason} | **R:R:** 1:{rr:.1f}")
    
    col1, col2 = st.columns(2)
    col1.metric("🔵 سعر الدخول (Entry)", f"${entry_p:,.2f}")
    col2.metric("🔴 وقف الخسارة (SL)", f"${sl:,.2f}")
    
    col3, col4 = st.columns(2)
    col3.metric("🟢 الهدف الأول (TP1)", f"${tp1:,.2f}")
    col4.metric("🟢 الهدف الثاني (TP2)", f"${tp2:,.2f}")

else:
    st.warning(f"### ⚪ لا توجد صفقة واضحة حالياً على {selected_asset_label}")
    st.info(f"جاهزية الشراء: **{score_buy}%** | جاهزية البيع: **{score_sell}%** (يلزم وصول النسبة إلى 70%+).")

st.divider()

# الشارت التفاعلي (آخر 20 شمعة مع إمكانية السحب والتنقل)
st.subheader(f"📈 الشارت التفاعلي المكبّر - {selected_asset_label} (آخر 20 شمعة)")

df_chart = df.tail(20)

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

# الشموع
fig.add_trace(go.Candlestick(
    x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
    low=df_chart['Low'], close=df_chart['Close'], name=selected_asset_label
), row=1, col=1)

# EMA 50
fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_50'], line=dict(color='orange', width=1.5), name="EMA 50"), row=1, col=1)

# خطوط الصفقة
if active_signal and sl and tp1:
    fig.add_hline(y=entry_p, line_dash="solid", line_color="cyan", line_width=2, annotation_text=f"🔵 Entry: ${entry_p:,.2f}", row=1, col=1)
    fig.add_hline(y=sl, line_dash="dash", line_color="red", line_width=1.5, annotation_text=f"🔴 SL: ${sl:,.2f}", row=1, col=1)
    fig.add_hline(y=tp1, line_dash="dash", line_color="lime", line_width=1.5, annotation_text=f"🟢 TP1: ${tp1:,.2f}", row=1, col=1)

    # المنطقة المظللة المصلحة
    box_color = "rgba(0, 255, 0, 0.12)" if active_signal == "BUY" else "rgba(255, 0, 0, 0.12)"
    fig.add_shape(
        type="rect",
        x0=df_chart.index[0], x1=df_chart.index[-1],
        y0=min(entry_p, tp1), y1=max(entry_p, tp1),
        fillcolor=box_color, line_width=0,
        row=1, col=1
    )

# RSI
fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='purple', width=1.5), name="RSI"), row=2, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

# إعدادات الشارت للسحب والتحكم الكامل وإلغاء التقريب عند الضغط
fig.update_layout(
    xaxis_rangeslider_visible=False,
    height=550,
    template="plotly_dark",
    margin=dict(l=10, r=10, t=30, b=10),
    dragmode='pan'  # تفعيل أداة السحب في جميع الاتجاهات
)

fig.update_xaxes(fixedrange=False)  # التمرير الأفقي (يمين/يسار)
fig.update_yaxes(fixedrange=False)  # التمرير العمودي (فوق/تحت)

st.plotly_chart(
    fig, 
    use_container_width=True,
    config={
        'doubleClick': False,      # إلغاء الزوم المزعج عند الضغط المزدوج
        'scrollZoom': False,       # إلغاء الزوم عند التمرير باللمس
        'displayModeBar': True,    # إظهار شريط الأدوات العلوي
        'modeBarButtonsToRemove': ['zoom2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d']
    }
)

st.divider()

# سجل الصفقات والتحليل التاريخي
st.subheader("📜 سجل الصفقات والتحليل (Trade History Log)")

if len(st.session_state.trade_log) > 0:
    for trade in st.session_state.trade_log[:10]:
        badge = "🟢" if "نجاح" in trade['status'] else ("🔴" if "خسارة" in trade['status'] else "🔵")
        with st.expander(f"{badge} [{trade['time']}] {trade['asset']} | الصفقة: {trade['type']} | الحالة: {trade['status']}"):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**سعر الدخول:** ${trade['entry']:,.2f}")
            c2.write(f"**وقف الخسارة:** ${trade['sl']:,.2f}")
            c3.write(f"**الهدف:** ${trade['tp1']:,.2f}")
            
            st.write(f"💡 **سبب فتح الصفقة:** {trade['entry_reason']}")
            st.write(f"🏁 **تحليل النتيجة:** {trade['exit_reason']}")
else:
    st.info("لم يتم تسجيل أي صفقات بعد في هذه الجلسة. ستظهر الصفقات وتُحفظ تلقائياً بمجرد تشكّل أي فرصة.")

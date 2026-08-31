import io
import requests
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import warnings

# Suppress yfinance warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Market Breadth Analyzer", layout="wide")

st.title("📈 S&P 500 & Nasdaq 100 Market Breadth")
st.markdown("Analyze how many stocks are moving up, down, or flat, and see how they are performing against key moving averages.")

# --- 1. DATA RETRIEVAL FUNCTIONS ---

@st.cache_data(show_spinner="Fetching index components from Wikipedia...")
def get_tickers():
    """Scrapes Wikipedia for the current S&P 500 and Nasdaq 100 tickers with a custom User-Agent."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    sp500_tickers = []
    nasdaq_tickers = []
    
    # Fetch S&P 500 tickers
    try:
        sp500_url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        resp_sp = requests.get(sp500_url, headers=headers)
        sp500_tables = pd.read_html(io.StringIO(resp_sp.text))
        
        # Look through tables to find the one with 'Symbol'
        for table in sp500_tables:
            if 'Symbol' in table.columns:
                sp500_tickers = table['Symbol'].str.replace('.', '-', regex=False).tolist()
                break
    except Exception as e:
        st.error(f"Error fetching S&P 500 tickers: {e}")
    
    # Fetch Nasdaq 100 tickers
    try:
        nasdaq_url = "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"
        resp_nasdaq = requests.get(nasdaq_url, headers=headers)
        nasdaq_tables = pd.read_html(io.StringIO(resp_nasdaq.text))
        
        # Look through tables to find the one with 'Ticker' or 'Symbol'
        for table in nasdaq_tables:
            if 'Ticker' in table.columns:
                nasdaq_tickers = table['Ticker'].str.replace('.', '-', regex=False).tolist()
                break
            elif 'Symbol' in table.columns:
                nasdaq_tickers = table['Symbol'].str.replace('.', '-', regex=False).tolist()
                break
    except Exception as e:
        st.error(f"Error fetching Nasdaq 100 tickers: {e}")
            
    return sp500_tickers, nasdaq_tickers

@st.cache_data(show_spinner="Downloading maximum historical data (this may take 1-3 minutes)...")
def get_stock_data(tickers):
    """Downloads historical daily close prices for the provided tickers."""
    
    # Safeguard: Do not attempt download if the ticker list is empty
    if not tickers:
        st.warning("No tickers found to download. Please check the data source.")
        return pd.DataFrame()
        
    data = yf.download(tickers, period="max", threads=True, progress=False)
    
    # Safeguard: Ensure data isn't empty before trying to parse columns
    if data.empty:
        return pd.DataFrame()
        
    # yfinance returns a MultiIndex column structure when querying multiple tickers
    if isinstance(data.columns, pd.MultiIndex) and 'Close' in data.columns.levels[0]:
        return data['Close']
    elif 'Close' in data.columns:
        return data['Close'] # Fallback for single tickers or different yfinance versions
    else:
        return data

# --- 2. SIDEBAR & USER INPUTS ---

st.sidebar.header("Settings")

index_choice = st.sidebar.selectbox(
    "Select Index", 
    ("S&P 500", "Nasdaq 100", "Both (Combined)")
)

timeframe_choice = st.sidebar.selectbox(
    "Select Timeframe for % Change", 
    ("Daily", "Weekly", "Monthly", "Quarterly", "Yearly")
)

# --- 3. DATA PROCESSING ---

# Get tickers
sp500_tickers, nasdaq_tickers = get_tickers()

if index_choice == "S&P 500":
    selected_tickers = sp500_tickers
elif index_choice == "Nasdaq 100":
    selected_tickers = nasdaq_tickers
else:
    selected_tickers = list(set(sp500_tickers + nasdaq_tickers)) # Remove duplicates

# Get data
if st.sidebar.button("Load/Refresh Data"):
    st.cache_data.clear()

df_close = get_stock_data(selected_tickers)

if not df_close.empty:
    
    # --- CALCULATIONS: Price Change ---
    # Map selection to pandas resample frequency strings
    resample_map = {
        "Daily": "D",
        "Weekly": "W",
        "Monthly": "ME",
        "Quarterly": "QE",
        "Yearly": "YE"
    }
    freq = resample_map[timeframe_choice]
    
    # Resample data to the chosen timeframe, taking the last close price of that period
    df_resampled = df_close.resample(freq).last()
    
    # Calculate percentage change and get the very last row (the current/most recent period)
    pct_change_latest = df_resampled.pct_change().iloc[-1]
    
    # Count Up, Down, Flat
    up_count = (pct_change_latest > 0).sum()
    down_count = (pct_change_latest < 0).sum()
    flat_count = (pct_change_latest == 0).sum()
    total_valid = up_count + down_count + flat_count
    
    # Percentages
    up_pct = (up_count / total_valid) * 100 if total_valid > 0 else 0
    down_pct = (down_count / total_valid) * 100 if total_valid > 0 else 0
    flat_pct = (flat_count / total_valid) * 100 if total_valid > 0 else 0
    
    # --- CALCULATIONS: Moving Averages ---
    # Calculated on standard daily data
    current_prices = df_close.iloc[-1]
    
    sma_20 = df_close.rolling(window=20).mean().iloc[-1]
    sma_50 = df_close.rolling(window=50).mean().iloc[-1]
    sma_200 = df_close.rolling(window=200).mean().iloc[-1]
    
    above_20 = (current_prices > sma_20).sum()
    above_50 = (current_prices > sma_50).sum()
    above_200 = (current_prices > sma_200).sum()
    total_ma = len(current_prices.dropna()) # Total stocks with current data
    
    # --- 4. DASHBOARD VISUALIZATION ---
    
    st.markdown("---")
    
    # Row 1: Breadth Metrics
    st.subheader(f"Price Change ({timeframe_choice})")
    col1, col2, col3 = st.columns(3)
    col1.metric("Stocks Up 🟢", f"{up_count}", f"{up_pct:.1f}%")
    col2.metric("Stocks Down 🔴", f"{down_count}", f"-{down_pct:.1f}%")
    col3.metric("Stocks Flat ⚪", f"{flat_count}", f"{flat_pct:.1f}%")
    
    # Row 1 Charts
    c1, c2 = st.columns(2)
    with c1:
        # Pie chart for Up/Down/Flat
        fig_pie = px.pie(
            values=[up_count, down_count, flat_count], 
            names=['Up', 'Down', 'Flat'],
            title=f"{timeframe_choice} Breadth Distribution",
            color=['Up', 'Down', 'Flat'],
            color_discrete_map={'Up':'#00cc96', 'Down':'#ef553b', 'Flat':'#ab63fa'}
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c2:
        # Moving Averages Bar Chart
        x_labels = ['> 20-Day SMA', '> 50-Day SMA', '> 200-Day SMA']
        y_values = [above_20, above_50, above_200]
        y_pct = [(v/total_ma)*100 for v in y_values]
        
        fig_bar = go.Figure(data=[
            go.Bar(x=x_labels, y=y_values, text=[f"{p:.1f}%" for p in y_pct], textposition='auto')
        ])
        fig_bar.update_layout(title="Stocks Above Moving Averages", yaxis_title="Number of Stocks")
        st.plotly_chart(fig_bar, use_container_width=True)
        
    # Row 2: Moving Averages Breakdown Text
    st.subheader("Moving Average Summary")
    c3, c4, c5 = st.columns(3)
    c3.metric(label="Above 20-Day SMA", value=f"{above_20} / {total_ma}", delta=f"{(above_20/total_ma)*100:.1f}%")
    c4.metric(label="Above 50-Day SMA", value=f"{above_50} / {total_ma}", delta=f"{(above_50/total_ma)*100:.1f}%")
    c5.metric(label="Above 200-Day SMA", value=f"{above_200} / {total_ma}", delta=f"{(above_200/total_ma)*100:.1f}%")


    # Row 3: Historical Breadth Line Chart ---
    st.markdown("---")
    st.subheader("Historical Market Breadth (% of Stocks Above SMA)")
    
    with st.spinner("Calculating historical moving averages..."):
        # 1. Calculate historical SMAs for the entire dataframe
        sma_20_hist = df_close.rolling(window=20).mean()
        sma_50_hist = df_close.rolling(window=50).mean()
        sma_200_hist = df_close.rolling(window=200).mean()
        
        # 2. Count active stocks per day (ignores NaNs for stocks that IPO'd recently)
        daily_active_stocks = df_close.count(axis=1)
        
        # 3. Calculate historical percentage of stocks above their SMA
        pct_above_20_hist = ((df_close > sma_20_hist).sum(axis=1) / daily_active_stocks) * 100
        pct_above_50_hist = ((df_close > sma_50_hist).sum(axis=1) / daily_active_stocks) * 100
        pct_above_200_hist = ((df_close > sma_200_hist).sum(axis=1) / daily_active_stocks) * 100
        
        # 4. Limit to the last 5 years to keep the chart performant and readable
        # (Optional: remove '.last("5Y")' to show the absolute maximum history)
        plot_dates = df_close.tail(1000).index
        
        # 5. Build the Plotly line chart
        fig_line = go.Figure()
        
        fig_line.add_trace(go.Scatter(
            x=plot_dates, y=pct_above_20_hist.loc[plot_dates], 
            mode='lines', name='> 20-Day SMA', line=dict(width=1, color='#00cc96')
        ))
        fig_line.add_trace(go.Scatter(
            x=plot_dates, y=pct_above_50_hist.loc[plot_dates], 
            mode='lines', name='> 50-Day SMA', line=dict(width=1, color='#ab63fa')
        ))
        fig_line.add_trace(go.Scatter(
            x=plot_dates, y=pct_above_200_hist.loc[plot_dates], 
            mode='lines', name='> 200-Day SMA', line=dict(width=1.5, color='#ef553b')
        ))
        
        # 6. Format the chart layout
        fig_line.update_layout(
            xaxis_title="Date",
            yaxis_title="Percentage of Stocks (%)",
            hovermode="x unified", # Shows all 3 values in a single tooltip on hover
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=30, b=0)
        )
        
        st.plotly_chart(fig_line, use_container_width=True)


else:
    st.error("Could not retrieve data. Please check your internet connection or try again later.")
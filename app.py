import os
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

st.title("📈 Market Breadth Analyzer")
st.markdown("Analyze how many stocks are moving up, down, or flat, and see how they are performing against key moving averages.")

# --- 1. DATA RETRIEVAL FUNCTIONS ---

@st.cache_data(show_spinner="Fetching index components and weights from Slickcharts...")
def get_tickers():
    """Scrapes Slickcharts for index tickers and their weights."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    def fetch_index(url):
        try:
            resp = requests.get(url, headers=headers)
            tables = pd.read_html(io.StringIO(resp.text))
            
            for table in tables:
                if 'Symbol' in table.columns and 'Weight' in table.columns:
                    df = table[['Symbol', 'Weight']].copy()
                    df['Symbol'] = df['Symbol'].astype(str).str.replace('.', '-', regex=False)
                    
                    # Force clean the weight column into numeric floats safely
                    df['Weight'] = df['Weight'].astype(str).str.replace('%', '', regex=False)
                    df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce').fillna(0.0)
                    
                    return df
        except Exception as e:
            st.error(f"Error fetching from {url}: {e}")
            
        return pd.DataFrame(columns=['Symbol', 'Weight'])

    df_sp500 = fetch_index('https://www.slickcharts.com/sp500')
    df_nasdaq = fetch_index('https://www.slickcharts.com/nasdaq100')
    df_dow = fetch_index('https://www.slickcharts.com/dowjones')
            
    return df_sp500, df_nasdaq, df_dow

@st.cache_data(show_spinner="Loading historical data (checking local CSVs first)...")
def get_stock_data(tickers):
    """Retrieves data from local CSVs. Downloads and saves missing data."""
    if not tickers:
        st.warning("No tickers found to process. Please check the data source.")
        return pd.DataFrame()
        
    close_prices = {}
    missing_tickers = []
    
    # 1. Check local files first
    for ticker in tickers:
        filename = f"{ticker}.csv"
        if os.path.exists(filename):
            try:
                # Read CSV and set the date as index
                df = pd.read_csv(filename, index_col=0, parse_dates=True)
                close_prices[ticker] = df['Close']
            except Exception:
                missing_tickers.append(ticker)
        else:
            missing_tickers.append(ticker)
            
    # 2. Download any missing tickers
    if missing_tickers:
        st.info(f"Downloading data for {len(missing_tickers)} missing ticker(s)...")
        data = yf.download(missing_tickers, period="max", threads=True, progress=False)
        
        if not data.empty:
            # Handle MultiIndex (multiple tickers) vs Single Index (one ticker)
            if isinstance(data.columns, pd.MultiIndex):
                if 'Close' in data.columns.levels[0]:
                    close_data = data['Close']
                else:
                    close_data = pd.DataFrame()
            else:
                if 'Close' in data.columns:
                    close_data = data[['Close']]
                    close_data.columns = [missing_tickers[0]] # Rename single column to ticker symbol
                else:
                    close_data = pd.DataFrame()
                    
            # Extract valid data and save each to its own CSV
            for ticker in missing_tickers:
                if ticker in close_data.columns:
                    ts = close_data[ticker].dropna()
                    if not ts.empty:
                        close_prices[ticker] = ts
                        # Save specifically to current directory as a CSV
                        ts.to_frame(name='Close').to_csv(f"{ticker}.csv")
                        
    # 3. Combine everything into a single DataFrame
    if not close_prices:
        return pd.DataFrame()
        
    df_combined = pd.DataFrame(close_prices)
    df_combined = df_combined.sort_index()
    
    return df_combined

# --- 2. SIDEBAR & USER INPUTS ---

st.sidebar.header("Settings")

index_choice = st.sidebar.selectbox(
    "Select Index", 
    ("S&P 500", "Nasdaq 100", "Dow Jones", "All (Combined)")
)

timeframe_choice = st.sidebar.selectbox(
    "Select Timeframe for % Change", 
    ("Daily", "Weekly", "Monthly", "Quarterly", "Yearly")
)

history_days = st.sidebar.slider(
    "Historical Plot Lookback (Days)", 
    min_value=30, 
    max_value=2520, 
    value=1260, 
    step=30,
    help="Adjust how many trading days to show on the line chart (252 days ≈ 1 year)."
)

if st.sidebar.button("Clear App Cache"):
    st.cache_data.clear()

# --- 3. DATA PROCESSING ---

# Get DataFrames containing tickers and weights
df_sp500, df_nasdaq, df_dow = get_tickers()

if index_choice == "S&P 500":
    df_weights = df_sp500
elif index_choice == "Nasdaq 100":
    df_weights = df_nasdaq
elif index_choice == "Dow Jones":
    df_weights = df_dow
else:
    # Combine all, group by symbol to handle overlaps, and recalculate relative weights to sum to 100%
    df_weights = pd.concat([df_sp500, df_nasdaq, df_dow]).groupby('Symbol').mean().reset_index()
    if df_weights['Weight'].sum() > 0:
        df_weights['Weight'] = (df_weights['Weight'] / df_weights['Weight'].sum()) * 100

selected_tickers = df_weights['Symbol'].tolist()

df_close = get_stock_data(selected_tickers)

if not df_close.empty:
    
    # --- CALCULATIONS: Price Change ---
    resample_map = {
        "Daily": "B",      
        "Weekly": "W",
        "Monthly": "ME",   
        "Quarterly": "QE", 
        "Yearly": "YE"     
    }
    freq = resample_map.get(timeframe_choice, "B")
    
    # Resample and drop any days where the market was closed (all NaNs)
    df_resampled = df_close.resample(freq).last().dropna(how='all')
    
    # Calculate percentage change for the latest period
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
    current_prices = df_close.iloc[-1]
    
    sma_20 = df_close.rolling(window=20).mean().iloc[-1]
    sma_50 = df_close.rolling(window=50).mean().iloc[-1]
    sma_200 = df_close.rolling(window=200).mean().iloc[-1]
    
    above_20 = (current_prices > sma_20).sum()
    above_50 = (current_prices > sma_50).sum()
    above_200 = (current_prices > sma_200).sum()
    total_ma = len(current_prices.dropna()) 
    
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
        fig_pie = px.pie(
            values=[up_count, down_count, flat_count], 
            names=['Up', 'Down', 'Flat'],
            title=f"{timeframe_choice} Breadth Distribution",
            color=['Up', 'Down', 'Flat'],
            color_discrete_map={'Up':'#00cc96', 'Down':'#ef553b', 'Flat':'#ab63fa'}
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c2:
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

    # Row 3: Historical Breadth Line Chart
    st.markdown("---")
    st.subheader("Historical Market Breadth (% of Stocks Above SMA)")
    
    with st.spinner("Calculating historical moving averages..."):
        sma_20_hist = df_close.rolling(window=20).mean()
        sma_50_hist = df_close.rolling(window=50).mean()
        sma_200_hist = df_close.rolling(window=200).mean()
        
        daily_active_stocks = df_close.count(axis=1)
        
        pct_above_20_hist = ((df_close > sma_20_hist).sum(axis=1) / daily_active_stocks) * 100
        pct_above_50_hist = ((df_close > sma_50_hist).sum(axis=1) / daily_active_stocks) * 100
        pct_above_200_hist = ((df_close > sma_200_hist).sum(axis=1) / daily_active_stocks) * 100
        
        plot_dates = df_close.tail(history_days).index 
        
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
        
        fig_line.update_layout(
            xaxis_title="Date",
            yaxis_title="Percentage of Stocks (%)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=30, b=0)
        )
        
        st.plotly_chart(fig_line, use_container_width=True)

    # Row 4: Component Contribution Table
    st.markdown("---")
    st.subheader(f"Component Performance & Index Contribution ({timeframe_choice})")
    
    df_table = df_weights.set_index('Symbol').copy()
    
    df_table['Price Change (%)'] = pct_change_latest * 100
    
    df_table['Weight'] = pd.to_numeric(df_table['Weight'], errors='coerce').fillna(0.0)
    df_table['Contribution (%)'] = df_table['Price Change (%)'] * (df_table['Weight'] / 100)
    
    df_table = df_table.dropna().reset_index()
    df_table = df_table.sort_values(by='Contribution (%)', ascending=False)
    
    if df_table.empty:
        st.warning("No valid data available to construct the contribution table for this period.")
    else:
        styled_table = df_table.style.format({
            'Weight': '{:.4f}%',
            'Price Change (%)': '{:.2f}%',
            'Contribution (%)': '{:.4f}%'
        }).background_gradient(subset=['Contribution (%)', 'Price Change (%)'], cmap='RdYlGn')
        
        st.dataframe(styled_table, use_container_width=True, height=500)

else:
    st.error("Could not retrieve data. Please check your internet connection or try again later.")

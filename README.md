# Market Breadth Analyzer 📈

A powerful and interactive Streamlit web application that analyzes the market breadth of the S&P 500 and Nasdaq 100 indices. 

## Overview
This tool provides a comprehensive view of market momentum by calculating the percentage of stocks moving up, down, or staying flat across various customizable timeframes. Additionally, it tracks and visualizes how many stocks are currently trading above their key moving averages (20-day, 50-day, and 200-day).

## Features
* **Dynamic Ticker Scraping:** Automatically fetches the most up-to-date list of S&P 500 and Nasdaq 100 components from Wikipedia.
* **Comprehensive Data:** Retrieves historical data using `yfinance`.
* **Flexible Timeframes:** Analyze price changes on a Daily, Weekly, Monthly, Quarterly, or Yearly basis.
* **Moving Average Tracking:** Instantly see the number of stocks trending above their 20-day, 50-day, and 200-day Simple Moving Averages (SMA).
* **Interactive Visualizations:** Beautiful, responsive charts built with Plotly.

## Prerequisites
Before running the application, ensure you have Python installed. Then, install the necessary dependencies:

```bash
pip install streamlit yfinance pandas plotly lxml html5lib
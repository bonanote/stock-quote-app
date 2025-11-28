from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yfinance as yf
from datetime import datetime, date
import logging
from typing import Dict, Optional, List, Tuple

app = FastAPI()
app.mount("/static", StaticFiles(directory="templates"), name="static")
templates = Jinja2Templates(directory="templates")
logging.getLogger("yfinance").setLevel(logging.WARNING)

YEARS = [2000, 2005, 2010, 2015, 2020, 2025]  # 2025 is YTD

def get_historical_data(ticker: yf.Ticker) -> List[Dict]:
    """Fetch year-end closes and % changes for specific years"""
    historical = []
    info = ticker.info
    symbol = info.get("symbol", "Unknown")
    
    try:
        # Fetch full history from 1999 to today
        hist = ticker.history(start="1999-12-01", end=date.today().isoformat())
        if hist.empty:
            return [{"year": year, "price": None, "pct_change": None, "date": None} for year in YEARS]
        
        prev_close = None
        prev_date = None
        
        for year in YEARS:
            if year == 2025:
                # YTD 2025: Use current price (latest close)
                current_price = info.get("regularMarketPrice") or info.get("currentPrice") or hist["Close"].iloc[-1]
                close_price = round(current_price, 2)
                close_date = datetime.now().strftime("%Y-%m-%d")
                pct_change = ((close_price - (prev_close or close_price)) / (prev_close or close_price)) * 100 if prev_close else 0
                historical.append({
                    "year": "2025 YTD",
                    "price": close_price,
                    "pct_change": round(pct_change, 2),
                    "date": close_date,
                    "symbol": symbol
                })
                break  # Last one
            
            # For past years: Last trading day in December
            year_hist = hist[(hist.index.year == year) & (hist.index.month == 12)]
            if year_hist.empty:
                historical.append({
                    "year": year,
                    "price": None,
                    "pct_change": None,
                    "date": None,
                    "symbol": symbol
                })
                prev_close = None
                continue
            
            close_price = round(year_hist["Close"].iloc[-1], 2)
            close_date = year_hist.index[-1].strftime("%Y-%m-%d")
            
            if prev_close is not None:
                pct_change = ((close_price - prev_close) / prev_close) * 100
            else:
                pct_change = None  # No prior year
            
            historical.append({
                "year": year,
                "price": close_price,
                "pct_change": round(pct_change, 2) if pct_change is not None else None,
                "date": close_date,
                "symbol": symbol
            })
            
            prev_close = close_price
            prev_date = close_date
        
        return historical
    except Exception as e:
        print(f"Historical data error for {symbol}: {e}")
        return [{"year": year, "price": None, "pct_change": None, "date": None, "symbol": symbol} for year in YEARS]

def get_stock_data(query: str):
    """Fetch stock info, YTD, and historical performance"""
    try:
        ticker = yf.Ticker(query)
        info = ticker.info
        hist = ticker.history(period="ytd")
        
        if hist.empty:
            return {"error": f"No data found for '{query}'. Try a valid ticker or company name."}
        
        # Current price
        current_price = info.get("regularMarketPrice") or info.get("currentPrice") or hist["Close"].iloc[-1]
        
        # Current YTD %
        ytd_start_price = hist["Close"].iloc[0]
        ytd_change_pct = ((current_price - ytd_start_price) / ytd_start_price) * 100
        
        # Historical
        historical = get_historical_data(ticker)
        
        return {
            "symbol": info.get("symbol", query.upper()),
            "name": info.get("longName") or info.get("shortName", query),
            "exchange": info.get("exchange", ""),
            "price": round(current_price, 2),
            "ytd_percent": round(ytd_change_pct, 2),
            "currency": info.get("currency", "USD"),
            "historical": historical,
            "error": None
        }
    except Exception as e:
        print(f"Error fetching {query}: {e}")
        return {"error": f"No data found for '{query}'. Try a valid ticker or company name."}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = Form(...)):
    data = get_stock_data(q.strip())
    return templates.TemplateResponse("index.html", {"request": request, "result": data, "query": q})

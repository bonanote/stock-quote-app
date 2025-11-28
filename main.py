from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yfinance as yf
import logging

app = FastAPI()
app.mount("/static", StaticFiles(directory="templates"), name="static")
templates = Jinja2Templates(directory="templates")
logging.getLogger("yfinance").setLevel(logging.WARNING)

def get_stock_data(query: str):
    try:
        ticker = yf.Ticker(query)
        info = ticker.info
        hist = ticker.history(period="ytd")
        if hist.empty:
            return None
        current_price = info.get("regularMarketPrice") or info.get("currentPrice") or hist["Close"].iloc[-1]
        ytd_start_price = hist["Close"].iloc[0]
        ytd_change_pct = ((current_price - ytd_start_price) / ytd_start_price) * 100
        return {
            "symbol": info.get("symbol", query.upper()),
            "name": info.get("longName") or info.get("shortName", query),
            "exchange": info.get("exchange", ""),
            "price": round(current_price, 2),
            "ytd_percent": round(ytd_change_pct, 2),
            "currency": info.get("currency", "USD"),
            "error": None
        }
    except:
        return {"error": f"No data found for '{query}'. Try a valid ticker or company name."}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = Form(...)):
    data = get_stock_data(q.strip())
    return templates.TemplateResponse("index.html", {"request": request, "result": data, "query": q})

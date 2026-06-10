
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio, json
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

app = FastAPI()

PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X",
    "USD/JPY": "JPY=X",
    "USD/CAD": "CAD=X",
    "USD/CHF": "CHF=X",
}

def prepare_close(df):
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return pd.to_numeric(close, errors="coerce").dropna()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))

def macd(series):
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9).mean()
    return macd_line.iloc[-1], signal.iloc[-1]

def bollinger(series):
    ma = series.rolling(20).mean()
    std = series.rolling(20).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    return upper.iloc[-1], lower.iloc[-1]

def get_entry_time():
    now = datetime.now()
    nxt = now + timedelta(minutes=5 - (now.minute % 5))
    return nxt.strftime("%H:%M")

def analyze(pair, ticker):
    try:
        df = yf.download(ticker, interval="5m", period="10d", progress=False, auto_adjust=True, threads=False)

        close = prepare_close(df)
        price = float(close.iloc[-1])

        ema20 = close.ewm(span=20).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1]
        ema100 = close.ewm(span=100).mean().iloc[-1]

        r = float(rsi(close).iloc[-1])
        macd_line, macd_signal = macd(close)
        bb_up, bb_low = bollinger(close)

        score_up = 0
        score_down = 0

        if ema20 > ema50: score_up += 20
        else: score_down += 20

        if ema50 > ema100: score_up += 20
        else: score_down += 20

        if r > 55: score_up += 20
        elif r < 45: score_down += 20

        if macd_line > macd_signal: score_up += 20
        else: score_down += 20

        if price > (bb_up + bb_low) / 2: score_up += 20
        else: score_down += 20

        if score_up > score_down:
            direction = "ВВЕРХ"
            confidence = min(99, score_up)
        elif score_down > score_up:
            direction = "ВНИЗ"
            confidence = min(99, score_down)
        else:
            direction = "ОЖИДАНИЕ"
            confidence = 50

        return {
            "pair": pair,
            "direction": direction,
            "confidence": confidence,
            "price": round(price, 5),
            "rsi5": round(r, 1),
            "rsi15": round(r, 1),
            "entry_after": "Подтверждение EMA + RSI + MACD + Bollinger",
            "expiration": "5 минут",
            "entry_time": get_entry_time()
        }
    except Exception as e:
        return {"pair": pair, "direction": "ОШИБКА", "confidence": 0, "price": 0, "rsi5": 0, "rsi15": 0, "entry_after": str(e), "expiration": "-", "entry_time": "-"}

@app.get("/")
async def home():
    return HTMLResponse(open("index.html","r",encoding="utf-8").read())

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_text(json.dumps([analyze(p,t) for p,t in PAIRS.items()]))
        await asyncio.sleep(5)

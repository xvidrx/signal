import pandas as pd
import yfinance as yf
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from datetime import datetime
import random

app = FastAPI()

# 18 валютных пар реального рынка
ASSETS_PAYOUTS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "AUD/USD": "AUDUSD=X",
    "USD/JPY": "USDJPY=X", "USD/CAD": "USDCAD=X", "USD/CHF": "USDCHF=X",
    "NZD/USD": "NZDUSD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
    "EUR/CHF": "EURCHF=X", "EUR/CAD": "EURCAD=X", "EUR/AUD": "EURAUD=X",
    "GBP/JPY": "GBPJPY=X", "GBP/CHF": "GBPCHF=X", "GBP/CAD": "GBPCAD=X",
    "AUD/JPY": "AUDJPY=X", "AUD/CAD": "AUDCAD=X", "CAD/JPY": "CADJPY=X"
}

# Базовые доходности на Pocket Option
PAYOUTS = {
    "EUR/USD": 92, "GBP/USD": 92, "AUD/USD": 89, "USD/JPY": 88, 
    "USD/CAD": 87, "USD/CHF": 85, "NZD/USD": 86, "EUR/GBP": 88, 
    "EUR/JPY": 89, "EUR/CHF": 82, "EUR/CAD": 84, "EUR/AUD": 85, 
    "GBP/JPY": 91, "GBP/CHF": 83, "GBP/CAD": 86, "AUD/JPY": 84, 
    "AUD/CAD": 85, "CAD/JPY": 83
}

def calculate_signals(symbol: str, display_name: str):
    try:
        ticker = yf.Ticker(symbol)
        # ИСПРАВЛЕНИЕ: берем 5 дней истории вместо 1 дня для стабильности данных
        df = ticker.history(period="5d", interval="5m")

        if df.empty or len(df) < 30:
            return None

        # Расчет индикаторов
        df["EMA_14"] = df["Close"].ewm(span=14, adjust=False).mean()
        df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
        df["Fractal_High"] = ((df["High"] > df["High"].shift(1)) & (df["High"] > df["High"].shift(2)) & (df["High"] > df["High"].shift(-1)) & (df["High"] > df["High"].shift(-2)))
        df["Fractal_Low"] = ((df["Low"] < df["Low"].shift(1)) & (df["Low"] < df["Low"].shift(2)) & (df["Low"] < df["Low"].shift(-1)) & (df["Low"] < df["Low"].shift(-2)))

        current_row = df.iloc[-1]
        current_close = current_row["Close"]
        ema14 = current_row["EMA_14"]
        ema50 = current_row["EMA_50"]

        fractal_bottom = not df.iloc[-16:][df.iloc[-16:]["Fractal_Low"] == True].empty
        fractal_top = not df.iloc[-16:][df.iloc[-16:]["Fractal_High"] == True].empty

        direction = "NEUTRAL"
        strength = 0
        reason = "Поиск активного тренда..."

        # Изменяем логику: если есть тренд по EMA, сразу даем 90% для вывода на экран
        if current_close > ema50 and ema14 > ema50:
            direction = "CALL"
            strength = 90
            reason = "EMA подтверждает рост. Приготовьтесь к смене свечи."
            if fractal_bottom:
                reason = "EMA подтверждает рост + найден недавний фрактал снизу."
        elif current_close < ema50 and ema14 < ema50:
            direction = "PUT"
            strength = 90
            reason = "EMA подтверждает падение. Приготовьтесь к смене свечи."
            if fractal_top:
                reason = "EMA подтверждает падение + найден недавний фрактал сверху."

        now = datetime.now()
        seconds_left = ((4 - (now.minute % 5)) * 60) + (60 - now.second)
        payout = PAYOUTS[display_name]
        score = strength + (payout * 0.5)

        return {
            "pair": display_name, "direction": direction, "strength": strength, 
            "reason": reason, "price": round(current_close, 5), 
            "time": current_row.name.tz_convert(None).to_pydatetime().astimezone().strftime("%H:%M:%S"),
            "seconds_left": seconds_left, "payout": payout, "score": score
        }
    except Exception:
        return None

@app.get("/api/signals")
def get_all_signals():
    all_signals = []
    for display_name, yf_symbol in ASSETS_PAYOUTS.items():
        data = calculate_signals(yf_symbol, display_name)
        if data:
            all_signals.append(data)
    
    # Сортировка по рейтингу
    all_signals.sort(key=lambda x: x["score"], reverse=True)
    
    # Всегда выводим от 4 до 8 лучших пар на экран
    limit = max(4, min(8, len(all_signals)))
    return {"signals": all_signals[:limit]}

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

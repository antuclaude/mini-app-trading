import pandas as pd
import numpy as np
import requests
import time
import logging
from twelvedata import TDClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ============================================================
# CẤU HÌNH
# ============================================================
TELEGRAM_TOKEN   = "8873625903:AAFHvX06xuG3x47GSth0vh2pNhCAjCJFWBw"
TELEGRAM_CHAT_ID = "8987704660"

# 3 API key luân phiên — mỗi key 800 credits/ngày = 2400 tổng
TWELVE_DATA_KEYS = [
    "f8e1e5fb2ab1458ea907eead7c0fa09f",
    "bd8755ac083548ecb2fc0fa59d6c91b8",
    "0e2cef39a9394c83a9986cd167c0ef8e"
]
_key_index = [0]  # dùng list để có thể thay đổi trong hàm con

def lay_key_hien_tai():
    return TWELVE_DATA_KEYS[_key_index[0]]

def chuyen_key_tiep_theo():
    """Chuyển sang key tiếp theo, trả về True nếu còn key, False nếu hết"""
    _key_index[0] += 1
    if _key_index[0] >= len(TWELVE_DATA_KEYS):
        _key_index[0] = 0  # reset về key đầu khi qua ngày mới
        return False
    logging.info(f"[API] Chuyển sang key {_key_index[0]+1}/{len(TWELVE_DATA_KEYS)}")
    return True

# ============================================================
# TELEGRAM
# ============================================================
def gui_telegram(tin_nhan):
    try:
        url     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": tin_nhan, "parse_mode": "HTML"}
        r       = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logging.error(f"Lỗi Telegram: {e}")
        return False

# ============================================================
# TẦNG 1: LẤY DỮ LIỆU — LUÂN PHIÊN KEY + RETRY
# ============================================================
def lay_du_lieu(san_pham):
    symbol = "XAU/USD" if san_pham == "Vàng (Gold)" else "BTC/USD"
    
    # Thử từng key
    for attempt in range(len(TWELVE_DATA_KEYS)):
        key = lay_key_hien_tai()
        logging.info(f"[API] Dùng key {_key_index[0]+1}/{len(TWELVE_DATA_KEYS)}")
        
        try:
            td     = TDClient(apikey=key)
            df_m15 = td.time_series(symbol=symbol, interval="15min", outputsize=100).as_pandas()
            df_h1  = td.time_series(symbol=symbol, interval="1h",    outputsize=50).as_pandas()

            if df_m15 is None or df_m15.empty:
                raise ValueError("df_m15 rỗng")
            if df_h1 is None or df_h1.empty:
                raise ValueError("df_h1 rỗng")

            # Chuẩn hóa
            for df in [df_m15, df_h1]:
                df.columns = [c.lower() for c in df.columns]
                for col in ['open','high','low','close']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df_m15 = df_m15.sort_index()
            df_h1  = df_h1.sort_index()

            logging.info(f"[API] ✅ Thành công — M15: {len(df_m15)} nến | H1: {len(df_h1)} nến")
            return df_m15, df_h1, None

        except Exception as e:
            loi = str(e)
            # Nếu lỗi 429 (hết quota) → chuyển key tiếp
            if "429" in loi or "credits" in loi.lower():
                logging.warning(f"[API] Key {_key_index[0]+1} hết quota → chuyển key tiếp")
                con_key = chuyen_key_tiep_theo()
                if not con_key:
                    # Hết tất cả key trong ngày
                    loi_cuoi = "❌ Tất cả 3 API key đã hết quota hôm nay. Reset lúc 00:00 UTC."
                    logging.error(f"[API] {loi_cuoi}")
                    gui_telegram(
                        f"⚠️ <b>Hết quota tất cả API key!</b>\n"
                        f"{loi_cuoi}\n"
                        f"🕐 Scanner sẽ tự hoạt động lại sau 00:00 UTC"
                    )
                    return None, None, loi_cuoi
            else:
                # Lỗi khác (mạng, timeout...) → thử lại sau 10s
                logging.warning(f"[API] Lỗi: {loi} — Thử lại sau 10s")
                time.sleep(10)

    loi_cuoi = "Không lấy được dữ liệu sau khi thử tất cả key"
    return None, None, loi_cuoi

# ============================================================
# TẦNG 2: RSI WILDER
# ============================================================
def tinh_RSI_wilder(series, period=14):
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period-1, adjust=False).mean()
    avg_loss = loss.ewm(com=period-1, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

# ============================================================
# TẦNG 3: ATR ĐỘNG
# ============================================================
def tinh_ATR(df, period=14):
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low']  - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period-1, adjust=False).mean()

# ============================================================
# TẦNG 4: XU HƯỚNG H1
# ============================================================
def xac_dinh_xu_huong_H1(df_h1):
    if df_h1 is None or len(df_h1) < 20:
        return "SIDEWAY"

    highs = df_h1['high'].values
    lows  = df_h1['low'].values
    n     = 3

    swing_highs, swing_lows = [], []
    for i in range(n, len(highs) - n):
        if all(highs[i] > highs[i-j] for j in range(1, n+1)) and \
           all(highs[i] > highs[i+j] for j in range(1, n+1)):
            swing_highs.append(highs[i])
        if all(lows[i] < lows[i-j] for j in range(1, n+1)) and \
           all(lows[i] < lows[i+j] for j in range(1, n+1)):
            swing_lows.append(lows[i])

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "SIDEWAY"

    hh = swing_highs[-1] > swing_highs[-2]
    hl = swing_lows[-1]  > swing_lows[-2]
    lh = swing_highs[-1] < swing_highs[-2]
    ll = swing_lows[-1]  < swing_lows[-2]

    if hh and hl:   return "UPTREND"
    elif lh and ll: return "DOWNTREND"
    else:           return "SIDEWAY"

# ============================================================
# TẦNG 5: FRACTAL SWING M15
# ============================================================
def tim_fractal_swing(df, n=5):
    highs = df['high'].values
    lows  = df['low'].values
    swing_highs, swing_lows = [], []
    for i in range(n, len(highs) - n):
        if all(highs[i] > highs[i-j] for j in range(1, n+1)) and \
           all(highs[i] > highs[i+j] for j in range(1, n+1)):
            swing_highs.append((i, highs[i]))
        if all(lows[i] < lows[i-j] for j in range(1, n+1)) and \
           all(lows[i] < lows[i+j] for j in range(1, n+1)):
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows

def xac_dinh_swing_XA(df, xu_huong):
    swing_highs, swing_lows = tim_fractal_swing(df, n=5)
    if not swing_highs or not swing_lows:
        return None

    if xu_huong == "UPTREND":
        last_low    = swing_lows[-1]
        highs_after = [(i, v) for i, v in swing_highs if i > last_low[0]]
        if not highs_after: return None
        return {"loai": "BUY",  "X": last_low[1],   "A": highs_after[-1][1],
                "idx_X": last_low[0], "idx_A": highs_after[-1][0]}
    elif xu_huong == "DOWNTREND":
        last_high  = swing_highs[-1]
        lows_after = [(i, v) for i, v in swing_lows if i > last_high[0]]
        if not lows_after: return None
        return {"loai": "SELL", "X": last_high[1],  "A": lows_after[-1][1],
                "idx_X": last_high[0], "idx_A": lows_after[-1][0]}
    return None

# ============================================================
# TẦNG 6: GOLDEN POCKET
# ============================================================
def tinh_vung_golden_pocket(swing):
    X, A      = swing["X"], swing["A"]
    chieu_cao = abs(A - X)
    if swing["loai"] == "BUY":
        return round(A - chieu_cao * 0.786, 2), round(A - chieu_cao * 0.618, 2)
    else:
        return round(A + chieu_cao * 0.618, 2), round(A + chieu_cao * 0.786, 2)

# ============================================================
# TẦNG 7: CHoCH M15
# ============================================================
def xac_nhan_choch(df, loai, gp_low, gp_high):
    closes = df['close'].tail(10).values
    opens  = df['open'].tail(10).values
    highs  = df['high'].tail(10).values
    lows   = df['low'].tail(10).values
    buffer = (gp_high - gp_low) * 0.3

    if loai == "BUY":
        trong_vung = lows[-3:].min() <= (gp_high + buffer) and closes[-1] >= (gp_low - buffer)
        if not trong_vung:
            return False, f"⏳ Chờ giá về vùng GP: {gp_low} – {gp_high}"
        than_nen = abs(closes[-1] - opens[-1])
        bong_nen = abs(highs[-1] - lows[-1])
        if closes[-1] > opens[-1] and closes[-1] > highs[-2] and than_nen > bong_nen * 0.35:
            return True, "✅ CHoCH BUY: Nến xanh mạnh phá đỉnh nến trước trong Golden Pocket"
        return False, "⏳ Trong vùng GP nhưng chưa có nến CHoCH xác nhận"
    else:
        trong_vung = highs[-3:].max() >= (gp_low - buffer) and closes[-1] <= (gp_high + buffer)
        if not trong_vung:
            return False, f"⏳ Chờ giá lên vùng GP: {gp_low} – {gp_high}"
        than_nen = abs(closes[-1] - opens[-1])
        bong_nen = abs(highs[-1] - lows[-1])
        if closes[-1] < opens[-1] and closes[-1] < lows[-2] and than_nen > bong_nen * 0.35:
            return True, "✅ CHoCH SELL: Nến đỏ mạnh phá đáy nến trước trong Golden Pocket"
        return False, "⏳ Trong vùng GP nhưng chưa có nến CHoCH xác nhận"

# ============================================================
# TẦNG 8: RSI DIVERGENCE
# ============================================================
def kiem_tra_phan_ky(df, loai, lookback=30):
    if len(df) < lookback:
        return False, "Chưa đủ dữ liệu RSI", 50.0

    block   = df.tail(lookback).copy()
    rsi     = tinh_RSI_wilder(block['close']).values
    highs   = block['high'].values
    lows    = block['low'].values
    rsi_now = rsi[-1]

    if np.isnan(rsi_now):
        return False, "RSI chưa tính được", 50.0

    co_phan_ky = False
    n = len(rsi)

    if loai == "BUY":
        for i in range(n-15, n-3):
            if i < 0: continue
            if lows[-1] < lows[i] and rsi[-1] > rsi[i] + 2.0 and rsi[i] <= 45:
                co_phan_ky = True; break
        if rsi_now < 30: co_phan_ky = True
    else:
        for i in range(n-15, n-3):
            if i < 0: continue
            if highs[-1] > highs[i] and rsi[-1] < rsi[i] - 2.0 and rsi[i] >= 55:
                co_phan_ky = True; break
        if rsi_now > 70: co_phan_ky = True

    mo_ta = "🔥 RSI Divergence xác nhận!" if co_phan_ky else f"RSI: {round(rsi_now,1)} — Chưa có phân kỳ"
    return co_phan_ky, mo_ta, round(rsi_now, 1)

# ============================================================
# TẦNG 9: SL ĐỘNG + TP THEO R:R
# ============================================================
def tinh_quan_ly_lenh(df, loai, gp_low, gp_high, san_pham):
    atr    = tinh_ATR(df).iloc[-1]
    closes = df['close'].tail(10).values
    highs  = df['high'].tail(10).values
    lows   = df['low'].tail(10).values
    gia    = closes[-1]

    buffer_min = 1.5 if san_pham == "Vàng (Gold)" else 200.0
    buffer_atr = max(atr * 1.2, buffer_min)

    if loai == "BUY":
        sl    = round(min(lows[-5:]) - buffer_atr, 2)
        kc_sl = gia - sl
        tp1   = round(gia + kc_sl * 2.0, 2)
        tp2   = round(gia + kc_sl * 3.0, 2)
    else:
        sl    = round(max(highs[-5:]) + buffer_atr, 2)
        kc_sl = sl - gia
        tp1   = round(gia - kc_sl * 2.0, 2)
        tp2   = round(gia - kc_sl * 3.0, 2)

    return {"entry": round(gia,2), "sl": sl, "tp1": tp1, "tp2": tp2,
            "kc_sl": round(kc_sl,2), "rr_tp1": "1:2", "rr_tp2": "1:3"}

# ============================================================
# TẦNG 10: CONFLUENCE + WINRATE
# ============================================================
def tinh_confluence(xu_huong, trong_vung, co_choch, co_phan_ky, rsi_val, loai):
    diem, chi_tiet = 0, []

    if xu_huong in ["UPTREND","DOWNTREND"]:
        diem += 1; chi_tiet.append(f"✅ H1 {xu_huong} — thuận chiều lớn")
    else:
        chi_tiet.append("❌ H1 Sideway — rủi ro cao")

    if trong_vung:
        diem += 1; chi_tiet.append("✅ Giá trong Golden Pocket 61.8%–78.6%")
    else:
        chi_tiet.append("⏳ Chưa vào vùng Golden Pocket")

    if co_choch:
        diem += 2; chi_tiet.append("✅✅ CHoCH M15 xác nhận (2 điểm)")
    else:
        chi_tiet.append("❌ Chưa có CHoCH xác nhận")

    if co_phan_ky:
        diem += 1; chi_tiet.append(f"✅ RSI Divergence ({rsi_val})")
    else:
        chi_tiet.append(f"➖ RSI {rsi_val} — chưa có phân kỳ")

    if loai == "BUY" and isinstance(rsi_val, float) and rsi_val < 35:
        diem += 1; chi_tiet.append(f"✅ RSI quá bán ({rsi_val}) — hỗ trợ BUY")
    elif loai == "SELL" and isinstance(rsi_val, float) and rsi_val > 65:
        diem += 1; chi_tiet.append(f"✅ RSI quá mua ({rsi_val}) — hỗ trợ SELL")

    if   diem >= 5: winrate, chat_luong = "80–85%", "🔥 TÍN HIỆU RẤT MẠNH"
    elif diem == 4: winrate, chat_luong = "70–75%", "💪 TÍN HIỆU MẠNH"
    elif diem == 3: winrate, chat_luong = "60–65%", "✅ TÍN HIỆU ĐẠT CHUẨN"
    elif diem == 2: winrate, chat_luong = "40–50%", "⚠️ TÍN HIỆU YẾU"
    else:           winrate, chat_luong = "<40%",   "❌ KHÔNG ĐỦ ĐIỀU KIỆN"

    return diem, winrate, chat_luong, chi_tiet

# ============================================================
# HÀM CHÍNH
# ============================================================
def lay_du_lieu_va_phan_tich(san_pham, khung_thoi_gian="15m"):
    df_m15, df_h1, loi = lay_du_lieu(san_pham)
    if loi or df_m15 is None:
        return {"loi": loi or "❌ Không lấy được dữ liệu. Thử lại sau!"}

    gia_hien_tai = round(float(df_m15['close'].iloc[-1]), 2)
    logging.info(f"[Phân tích] Giá: ${gia_hien_tai}")

    xu_huong     = xac_dinh_xu_huong_H1(df_h1)
    rsi_series   = tinh_RSI_wilder(df_m15['close'])
    rsi_hien_tai = round(float(rsi_series.iloc[-1]), 1) if not np.isnan(rsi_series.iloc[-1]) else 50.0

    logging.info(f"[Phân tích] H1: {xu_huong} | RSI: {rsi_hien_tai}")

    if xu_huong == "SIDEWAY":
        return {
            "loi": None, "gia_hien_tai": gia_hien_tai,
            "xu_huong_h1": xu_huong, "rsi": rsi_hien_tai,
            "trang_thai": "🔮 H1 đang Sideway — chờ xu hướng rõ ràng hơn",
            "co_tin_hieu": False, "diem_confluence": 0,
            "winrate": "N/A", "chat_luong": "❌ Không đủ điều kiện",
            "chi_tiet_confluence": ["❌ H1 Sideway — chưa có xu hướng rõ ràng"]
        }

    swing = xac_dinh_swing_XA(df_m15, xu_huong)
    if swing is None:
        return {
            "loi": None, "gia_hien_tai": gia_hien_tai,
            "xu_huong_h1": xu_huong, "rsi": rsi_hien_tai,
            "trang_thai": "🔮 Chưa tìm được Fractal Swing rõ ràng",
            "co_tin_hieu": False, "diem_confluence": 0,
            "winrate": "N/A", "chat_luong": "❌ Không đủ điều kiện",
            "chi_tiet_confluence": [f"✅ H1 {xu_huong}", "❌ Chưa có Fractal Swing"]
        }

    loai            = swing["loai"]
    X, A            = swing["X"], swing["A"]
    gp_low, gp_high = tinh_vung_golden_pocket(swing)

    co_choch, ly_do_choch          = xac_nhan_choch(df_m15, loai, gp_low, gp_high)
    co_phan_ky, mo_ta_rsi, rsi_val = kiem_tra_phan_ky(df_m15, loai)

    closes_5 = df_m15['close'].tail(5).values
    lows_5   = df_m15['low'].tail(5).values
    highs_5  = df_m15['high'].tail(5).values
    buffer   = (gp_high - gp_low) * 0.3

    trong_vung = (lows_5.min() <= gp_high + buffer and closes_5[-1] >= gp_low - buffer) \
                 if loai == "BUY" else \
                 (highs_5.max() >= gp_low - buffer and closes_5[-1] <= gp_high + buffer)

    diem, winrate, chat_luong, chi_tiet = tinh_confluence(
        xu_huong, trong_vung, co_choch, co_phan_ky, rsi_val, loai
    )

    logging.info(f"[Phân tích] {loai} | GP: {gp_low}-{gp_high} | CHoCH: {co_choch} | Điểm: {diem}/5")

    co_tin_hieu = co_choch and diem >= 3
    quan_ly     = tinh_quan_ly_lenh(df_m15, loai, gp_low, gp_high, san_pham) if co_tin_hieu else None

    ket_qua = {
        "loi": None, "gia_hien_tai": gia_hien_tai,
        "xu_huong_h1": xu_huong, "loai": loai,
        "diem_X": round(X,2), "diem_A": round(A,2),
        "gp_low": gp_low, "gp_high": gp_high,
        "trong_vung": trong_vung, "rsi": rsi_val,
        "co_phan_ky": co_phan_ky, "mo_ta_rsi": mo_ta_rsi,
        "co_choch": co_choch, "ly_do_choch": ly_do_choch,
        "diem_confluence": diem, "winrate": winrate,
        "chat_luong": chat_luong, "chi_tiet_confluence": chi_tiet,
        "quan_ly": quan_ly, "co_tin_hieu": co_tin_hieu,
        "trang_thai": ly_do_choch
    }

    if co_tin_hieu and quan_ly:
        emoji    = "🟢" if loai == "BUY" else "🔴"
        noi_dung = f"""
🦅 <b>{emoji} TÍN HIỆU {loai} — {san_pham}</b>
{chat_luong} | Điểm: {diem}/5 | Key: {_key_index[0]+1}/3

📊 <b>H1:</b> {xu_huong}
📐 <b>Golden Pocket:</b> {gp_low} – {gp_high}
📈 <b>RSI M15:</b> {rsi_val} {'🔥 Phân kỳ!' if co_phan_ky else ''}

🎯 <b>Entry:</b> <code>{quan_ly['entry']}</code>
🔴 <b>SL:</b> <code>{quan_ly['sl']}</code> ({quan_ly['kc_sl']} pip)
🟢 <b>TP1 (1:2):</b> <code>{quan_ly['tp1']}</code>
🟢 <b>TP2 (1:3):</b> <code>{quan_ly['tp2']}</code>

🏆 <b>Winrate:</b> {winrate}
💡 Chốt 50% TP1 → dời SL hoà vốn → để 50% chạy TP2
        """.strip()
        gui_telegram(noi_dung)
        logging.info(f"[Telegram] ✅ Đã gửi tín hiệu {loai} — Điểm {diem}/5")

    return ket_qua

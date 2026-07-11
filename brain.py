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
TWELVE_DATA_KEY  = "f8e1e5fb2ab1458ea907eead7c0fa09f"

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
# TẦNG 1: LẤY DỮ LIỆU — CÓ RETRY + LOG RÕ LÝ DO LỖI
# ============================================================
def lay_du_lieu(san_pham, so_lan_thu=3, cho_giua_lan=10):
    """
    Thử lấy dữ liệu tối đa so_lan_thu lần.
    Trả về (df_m15, df_h1, loi_message)
    loi_message = None nếu thành công
    """
    symbol = "XAU/USD" if san_pham == "Vàng (Gold)" else "BTC/USD"

    for lan in range(1, so_lan_thu + 1):
        try:
            logging.info(f"[Dữ liệu] Lần thử {lan}/{so_lan_thu} — {symbol}")
            td = TDClient(apikey=TWELVE_DATA_KEY)

            df_m15 = td.time_series(symbol=symbol, interval="15min", outputsize=200).as_pandas()
            df_h1  = td.time_series(symbol=symbol, interval="1h",    outputsize=100).as_pandas()

            # Kiểm tra dữ liệu có hợp lệ không
            if df_m15 is None or df_m15.empty:
                raise ValueError("df_m15 rỗng — Twelve Data không trả về dữ liệu")
            if df_h1 is None or df_h1.empty:
                raise ValueError("df_h1 rỗng — Twelve Data không trả về dữ liệu")

            # Chuẩn hóa cột
            for df in [df_m15, df_h1]:
                df.columns = [c.lower() for c in df.columns]
                for col in ['open', 'high', 'low', 'close']:
                    if col not in df.columns:
                        raise ValueError(f"Thiếu cột '{col}' trong dữ liệu")
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df_m15 = df_m15.sort_index()
            df_h1  = df_h1.sort_index()

            # Kiểm tra NaN quá nhiều
            if df_m15['close'].isna().sum() > 10:
                raise ValueError("Dữ liệu M15 có quá nhiều giá trị NaN")

            logging.info(f"[Dữ liệu] ✅ Lấy thành công — M15: {len(df_m15)} nến | H1: {len(df_h1)} nến")
            return df_m15, df_h1, None

        except Exception as e:
            loi = str(e)
            logging.warning(f"[Dữ liệu] ❌ Lần {lan} thất bại: {loi}")
            if lan < so_lan_thu:
                logging.info(f"[Dữ liệu] Chờ {cho_giua_lan}s rồi thử lại...")
                time.sleep(cho_giua_lan)

    # Hết số lần thử
    loi_cuoi = f"❌ Không lấy được dữ liệu sau {so_lan_thu} lần thử. Lỗi: {loi}"
    logging.error(f"[Dữ liệu] {loi_cuoi}")
    gui_telegram(f"⚠️ <b>Scanner gặp lỗi dữ liệu!</b>\n{loi_cuoi}\n🕐 Sẽ thử lại lần quét tiếp theo.")
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
    if df_h1 is None or len(df_h1) < 30:
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
        last_high   = highs_after[-1]
        return {"loai": "BUY", "X": last_low[1], "A": last_high[1],
                "idx_X": last_low[0], "idx_A": last_high[0]}

    elif xu_huong == "DOWNTREND":
        last_high  = swing_highs[-1]
        lows_after = [(i, v) for i, v in swing_lows if i > last_high[0]]
        if not lows_after: return None
        last_low   = lows_after[-1]
        return {"loai": "SELL", "X": last_high[1], "A": last_low[1],
                "idx_X": last_high[0], "idx_A": last_low[0]}
    return None

# ============================================================
# TẦNG 6: GOLDEN POCKET
# ============================================================
def tinh_vung_golden_pocket(swing):
    loai      = swing["loai"]
    X, A      = swing["X"], swing["A"]
    chieu_cao = abs(A - X)
    if loai == "BUY":
        gp_high = A - chieu_cao * 0.618
        gp_low  = A - chieu_cao * 0.786
    else:
        gp_low  = A + chieu_cao * 0.618
        gp_high = A + chieu_cao * 0.786
    return round(gp_low, 2), round(gp_high, 2)

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
        nen_xanh = closes[-1] > opens[-1]
        pha_dinh = closes[-1] > highs[-2]
        than_nen = abs(closes[-1] - opens[-1])
        bong_nen = abs(highs[-1] - lows[-1])
        du_manh  = than_nen > bong_nen * 0.35
        if nen_xanh and pha_dinh and du_manh:
            return True, "✅ CHoCH BUY: Nến xanh mạnh phá đỉnh nến trước trong Golden Pocket"
        return False, "⏳ Trong vùng GP nhưng chưa có nến CHoCH xác nhận"
    else:
        trong_vung = highs[-3:].max() >= (gp_low - buffer) and closes[-1] <= (gp_high + buffer)
        if not trong_vung:
            return False, f"⏳ Chờ giá lên vùng GP: {gp_low} – {gp_high}"
        nen_do   = closes[-1] < opens[-1]
        pha_day  = closes[-1] < lows[-2]
        than_nen = abs(closes[-1] - opens[-1])
        bong_nen = abs(highs[-1] - lows[-1])
        du_manh  = than_nen > bong_nen * 0.35
        if nen_do and pha_day and du_manh:
            return True, "✅ CHoCH SELL: Nến đỏ mạnh phá đáy nến trước trong Golden Pocket"
        return False, "⏳ Trong vùng GP nhưng chưa có nến CHoCH xác nhận"

# ============================================================
# TẦNG 8: RSI DIVERGENCE
# ============================================================
def kiem_tra_phan_ky(df, loai, lookback=30):
    if len(df) < lookback:
        return False, "Chưa đủ dữ liệu RSI", 50.0

    block  = df.tail(lookback).copy()
    rsi    = tinh_RSI_wilder(block['close']).values
    highs  = block['high'].values
    lows   = block['low'].values
    rsi_now = rsi[-1]

    if np.isnan(rsi_now):
        return False, "RSI chưa tính được", 50.0

    co_phan_ky = False
    n = len(rsi)

    if loai == "BUY":
        for i in range(n - 15, n - 3):
            if i < 0: continue
            if lows[-1] < lows[i] and rsi[-1] > rsi[i] + 2.0 and rsi[i] <= 45:
                co_phan_ky = True
                break
        if rsi_now < 30:
            co_phan_ky = True
    else:
        for i in range(n - 15, n - 3):
            if i < 0: continue
            if highs[-1] > highs[i] and rsi[-1] < rsi[i] - 2.0 and rsi[i] >= 55:
                co_phan_ky = True
                break
        if rsi_now > 70:
            co_phan_ky = True

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
        diem += 1
        chi_tiet.append(f"✅ H1 {xu_huong} — thuận chiều lớn")
    else:
        chi_tiet.append("❌ H1 Sideway — rủi ro cao")

    if trong_vung:
        diem += 1
        chi_tiet.append("✅ Giá trong Golden Pocket 61.8%–78.6%")
    else:
        chi_tiet.append("⏳ Chưa vào vùng Golden Pocket")

    if co_choch:
        diem += 2
        chi_tiet.append("✅✅ CHoCH M15 xác nhận (2 điểm)")
    else:
        chi_tiet.append("❌ Chưa có CHoCH xác nhận")

    if co_phan_ky:
        diem += 1
        chi_tiet.append(f"✅ RSI Divergence ({rsi_val})")
    else:
        chi_tiet.append(f"➖ RSI {rsi_val} — chưa có phân kỳ")

    if loai == "BUY" and isinstance(rsi_val, float) and rsi_val < 35:
        diem += 1
        chi_tiet.append(f"✅ RSI quá bán ({rsi_val}) — hỗ trợ BUY")
    elif loai == "SELL" and isinstance(rsi_val, float) and rsi_val > 65:
        diem += 1
        chi_tiet.append(f"✅ RSI quá mua ({rsi_val}) — hỗ trợ SELL")

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
    # 1. Lấy dữ liệu — có retry và log rõ lỗi
    df_m15, df_h1, loi = lay_du_lieu(san_pham)
    if loi:
        return {"loi": f"❌ Lỗi dữ liệu: {loi}"}
    if df_m15 is None or df_m15.empty:
        return {"loi": "❌ Không lấy được dữ liệu. Thử lại sau!"}

    gia_hien_tai = round(float(df_m15['close'].iloc[-1]), 2)
    logging.info(f"[Phân tích] Giá hiện tại: ${gia_hien_tai}")

    # 2. Xu hướng H1
    xu_huong = xac_dinh_xu_huong_H1(df_h1)
    logging.info(f"[Phân tích] H1: {xu_huong}")

    # 3. RSI M15
    rsi_series   = tinh_RSI_wilder(df_m15['close'])
    rsi_hien_tai = round(float(rsi_series.iloc[-1]), 1) if not np.isnan(rsi_series.iloc[-1]) else 50.0

    if xu_huong == "SIDEWAY":
        logging.info("[Phân tích] H1 Sideway — bỏ qua lần quét này")
        return {
            "loi": None,
            "gia_hien_tai": gia_hien_tai,
            "xu_huong_h1": xu_huong,
            "rsi": rsi_hien_tai,
            "trang_thai": "🔮 H1 đang Sideway — chờ xu hướng rõ ràng hơn",
            "co_tin_hieu": False,
            "diem_confluence": 0,
            "winrate": "N/A",
            "chat_luong": "❌ Không đủ điều kiện",
            "chi_tiet_confluence": ["❌ H1 Sideway — chưa có xu hướng rõ ràng"]
        }

    # 4. Fractal Swing
    swing = xac_dinh_swing_XA(df_m15, xu_huong)
    if swing is None:
        logging.info("[Phân tích] Chưa tìm được Fractal Swing")
        return {
            "loi": None,
            "gia_hien_tai": gia_hien_tai,
            "xu_huong_h1": xu_huong,
            "rsi": rsi_hien_tai,
            "trang_thai": "🔮 Chưa tìm được Fractal Swing rõ ràng",
            "co_tin_hieu": False,
            "diem_confluence": 0,
            "winrate": "N/A",
            "chat_luong": "❌ Không đủ điều kiện",
            "chi_tiet_confluence": [f"✅ H1 {xu_huong}", "❌ Chưa có Fractal Swing"]
        }

    loai   = swing["loai"]
    X, A   = swing["X"], swing["A"]

    # 5-8. Phân tích
    gp_low, gp_high         = tinh_vung_golden_pocket(swing)
    co_choch, ly_do_choch   = xac_nhan_choch(df_m15, loai, gp_low, gp_high)
    co_phan_ky, mo_ta_rsi, rsi_val = kiem_tra_phan_ky(df_m15, loai)

    closes_5 = df_m15['close'].tail(5).values
    lows_5   = df_m15['low'].tail(5).values
    highs_5  = df_m15['high'].tail(5).values
    buffer   = (gp_high - gp_low) * 0.3

    if loai == "BUY":
        trong_vung = lows_5.min() <= (gp_high + buffer) and closes_5[-1] >= (gp_low - buffer)
    else:
        trong_vung = highs_5.max() >= (gp_low - buffer) and closes_5[-1] <= (gp_high + buffer)

    # 9. Confluence
    diem, winrate, chat_luong, chi_tiet = tinh_confluence(
        xu_huong, trong_vung, co_choch, co_phan_ky, rsi_val, loai
    )

    logging.info(f"[Phân tích] {loai} | GP: {gp_low}-{gp_high} | Trong GP: {trong_vung} | CHoCH: {co_choch} | Điểm: {diem}/5")

    # 10. Quản lý lệnh
    quan_ly     = None
    co_tin_hieu = co_choch and diem >= 3
    if co_tin_hieu:
        quan_ly = tinh_quan_ly_lenh(df_m15, loai, gp_low, gp_high, san_pham)

    ket_qua = {
        "loi": None,
        "gia_hien_tai": gia_hien_tai,
        "xu_huong_h1": xu_huong,
        "loai": loai,
        "diem_X": round(X, 2),
        "diem_A": round(A, 2),
        "gp_low": gp_low,
        "gp_high": gp_high,
        "trong_vung": trong_vung,
        "rsi": rsi_val,
        "co_phan_ky": co_phan_ky,
        "mo_ta_rsi": mo_ta_rsi,
        "co_choch": co_choch,
        "ly_do_choch": ly_do_choch,
        "diem_confluence": diem,
        "winrate": winrate,
        "chat_luong": chat_luong,
        "chi_tiet_confluence": chi_tiet,
        "quan_ly": quan_ly,
        "co_tin_hieu": co_tin_hieu,
        "trang_thai": ly_do_choch
    }

    # 11. Gửi Telegram
    if co_tin_hieu and quan_ly:
        emoji    = "🟢" if loai == "BUY" else "🔴"
        noi_dung = f"""
🦅 <b>{emoji} TÍN HIỆU {loai} — {san_pham}</b>
{chat_luong} | Điểm: {diem}/5

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

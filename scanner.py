import time
import logging
from datetime import datetime
from brain import lay_du_lieu_va_phan_tich, gui_telegram

# Cấu hình log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S %d/%m/%Y'
)

INTERVAL_GIAY = 300  # 5 phút
SAN_PHAM = "Vàng (Gold)"

def quet_mot_lan():
    logging.info(f"🔍 Bắt đầu quét {SAN_PHAM}...")
    try:
        res = lay_du_lieu_va_phan_tich(SAN_PHAM)

        if res.get("loi"):
            logging.warning(f"Lỗi: {res['loi']}")
            return

        gia       = res.get('gia_hien_tai', 'N/A')
        xu_huong  = res.get('xu_huong_h1', 'N/A')
        rsi       = res.get('rsi', 'N/A')
        diem      = res.get('diem_confluence', 0)
        winrate   = res.get('winrate', 'N/A')
        co_tin    = res.get('co_tin_hieu', False)

        logging.info(f"Giá: ${gia} | H1: {xu_huong} | RSI: {rsi} | Điểm: {diem}/5 | Winrate: {winrate}")

        if co_tin:
            logging.info(f"✅ TÍN HIỆU {res.get('loai')} — Điểm {diem}/5 — Đã gửi Telegram!")
        else:
            logging.info(f"⏳ Chưa đủ điều kiện ({diem}/5) — Tiếp tục theo dõi...")

    except Exception as e:
        logging.error(f"❌ Lỗi quét: {e}")
        try:
            gui_telegram(f"⚠️ Scanner gặp lỗi: {str(e)}")
        except:
            pass

def main():
    logging.info("🦅 SMC Scanner khởi động...")
    logging.info(f"📦 Sản phẩm: {SAN_PHAM}")
    logging.info(f"⏱️ Quét mỗi: {INTERVAL_GIAY // 60} phút")

    # Gửi thông báo khởi động
    gui_telegram(
        f"🦅 <b>SMC Scanner đã khởi động!</b>\n"
        f"📦 Sản phẩm: {SAN_PHAM}\n"
        f"⏱️ Quét mỗi {INTERVAL_GIAY // 60} phút\n"
        f"🕐 {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
    )

    while True:
        quet_mot_lan()
        logging.info(f"💤 Nghỉ {INTERVAL_GIAY // 60} phút...")
        time.sleep(INTERVAL_GIAY)

if __name__ == "__main__":
    main()

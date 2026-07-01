import streamlit as st
import time
import threading
from datetime import datetime
from brain import lay_du_lieu_va_phan_tich, gui_telegram

st.set_page_config(page_title="SMC Trading Signal", page_icon="🦅", layout="wide")

st.markdown("""
<style>
.signal-box {
    background: linear-gradient(135deg, #0d2b0d, #1a4a1a);
    border: 2px solid #00ff88;
    border-radius: 12px;
    padding: 20px;
    margin: 10px 0;
}
.wait-box {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 1px solid #555;
    border-radius: 12px;
    padding: 20px;
    margin: 10px 0;
}
.dieu-kien-pass {
    background: #0d2b0d;
    border-left: 4px solid #00ff88;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 5px 0;
    color: #00ff88;
    font-size: 14px;
}
.dieu-kien-fail {
    background: #2b0d0d;
    border-left: 4px solid #ff4444;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 5px 0;
    color: #ff6666;
    font-size: 14px;
}
.dieu-kien-wait {
    background: #1a1a0d;
    border-left: 4px solid #ffaa00;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 5px 0;
    color: #ffcc44;
    font-size: 14px;
}
.score-bar {
    background: #1e2329;
    border-radius: 10px;
    padding: 15px 20px;
    margin: 10px 0;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# BACKGROUND SCANNER — chạy ngầm mỗi 5 phút
# ============================================================
_scanner_started = False

def _background_scan():
    """Chạy ngầm liên tục, không phụ thuộc vào giao diện"""
    while True:
        try:
            res = lay_du_lieu_va_phan_tich("Vàng (Gold)")
            st.session_state['ket_qua_bg'] = res
            st.session_state['lan_cuoi_bg'] = datetime.now()
        except Exception as e:
            print(f"[Scanner] Lỗi: {e}")
        time.sleep(300)  # 5 phút

def khoi_dong_scanner():
    global _scanner_started
    if not _scanner_started:
        t = threading.Thread(target=_background_scan, daemon=True)
        t.start()
        _scanner_started = True

khoi_dong_scanner()

# ============================================================
# HEADER
# ============================================================
st.title("🦅 SMC Trading Signal")
st.caption("SMC + Fractal Swing + Golden Pocket + RSI Divergence + CHoCH M15 | R:R 1:2 / 1:3")
st.divider()

# ============================================================
# ĐIỀU KHIỂN
# ============================================================
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    san_pham = st.selectbox("📦 Sản phẩm:", ["Vàng (Gold)", "Bitcoin (BTC)"])
with c2:
    st.write(""); st.write("")
    nut_quet = st.button("⚡ QUÉT NGAY", use_container_width=True, type="primary")
with c3:
    st.write(""); st.write("")
    if st.button("🗑️ Xóa", use_container_width=True):
        for k in ['ket_qua', 'lan_cuoi']:
            if k in st.session_state: del st.session_state[k]
        st.rerun()

st.divider()

vung = st.empty()

# ============================================================
# HÀM RENDER ĐIỀU KIỆN
# ============================================================
def render_dieu_kien(label, trang_thai, mo_ta):
    if trang_thai == 'pass':
        icon, css = "✅", "dieu-kien-pass"
    elif trang_thai == 'fail':
        icon, css = "❌", "dieu-kien-fail"
    else:
        icon, css = "⏳", "dieu-kien-wait"
    return f"""
    <div class="{css}">
        <strong>{icon} {label}</strong><br>
        <span style="opacity:0.85;font-size:13px">{mo_ta}</span>
    </div>"""

# ============================================================
# HÀM HIỂN THỊ KẾT QUẢ
# ============================================================
def hien_thi(res):
    with vung.container():
        if res.get("loi"):
            st.error(res["loi"])
            return

        st.caption(f"🕐 Cập nhật lúc: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}")

        # METRICS
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Giá hiện tại",  f"${res.get('gia_hien_tai','N/A')}")
        c2.metric("📊 Xu hướng H1",   res.get('xu_huong_h1','N/A'))
        c3.metric("📈 RSI M15",        res.get('rsi','N/A'))
        c4.metric("🏆 Winrate",        res.get('winrate','N/A'))

        st.write("")

        co_tin_hieu = res.get('co_tin_hieu', False)
        diem        = res.get('diem_confluence', 0)
        loai        = res.get('loai', '')

        # BOX TRẠNG THÁI
        if co_tin_hieu:
            st.markdown(f"""
            <div class="signal-box">
                <h2 style="color:#00ff88;margin:0">{res.get('chat_luong','')}</h2>
                <h3 style="color:#fff;margin:8px 0">{res.get('trang_thai','')}</h3>
                <p style="color:#aaa;margin:0">Tổng điểm: <b style="color:#00ff88">{diem}/5</b></p>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="wait-box">
                <h3 style="color:#ffaa00;margin:0">{res.get('chat_luong','')}</h3>
                <p style="color:#ccc;margin:8px 0">{res.get('trang_thai','')}</p>
                <p style="color:#888;margin:0">Điểm: <b style="color:#ffaa00">{diem}/5</b> — Chưa đủ điều kiện</p>
            </div>""", unsafe_allow_html=True)

        st.write("")

        # CHECKLIST
        st.subheader("🔍 Checklist điều kiện — Lần quét này")

        xu_huong   = res.get('xu_huong_h1', 'SIDEWAY')
        trong_vung = res.get('trong_vung', False)
        co_choch   = res.get('co_choch', False)
        co_phan_ky = res.get('co_phan_ky', False)
        rsi_val    = res.get('rsi', 50)
        gp_low     = res.get('gp_low', 'N/A')
        gp_high    = res.get('gp_high', 'N/A')
        diem_X     = res.get('diem_X', 'N/A')
        diem_A     = res.get('diem_A', 'N/A')
        mo_ta_rsi  = res.get('mo_ta_rsi', '')

        html = ""

        # ĐK 1: H1 Trend
        if xu_huong == "UPTREND":
            html += render_dieu_kien("Điều kiện 1/5 — Xu hướng H1 (1đ)", "pass",
                "H1 UPTREND → Chỉ tìm BUY. Higher High + Higher Low xác nhận.")
        elif xu_huong == "DOWNTREND":
            html += render_dieu_kien("Điều kiện 1/5 — Xu hướng H1 (1đ)", "pass",
                "H1 DOWNTREND → Chỉ tìm SELL. Lower High + Lower Low xác nhận.")
        else:
            html += render_dieu_kien("Điều kiện 1/5 — Xu hướng H1 (0đ)", "fail",
                "H1 SIDEWAY — Không có xu hướng rõ. Chờ breakout khỏi vùng tích lũy.")

        # ĐK 2: Fractal Swing
        if diem_X != 'N/A' and diem_A != 'N/A':
            html += render_dieu_kien("Điều kiện 2/5 — Fractal Swing X→A tìm được", "pass",
                f"X = {diem_X} | A = {diem_A} | Hướng: {loai}")
        else:
            html += render_dieu_kien("Điều kiện 2/5 — Fractal Swing X→A", "fail",
                "Chưa tìm được swing rõ ràng. Thị trường có thể đang tích lũy phức tạp.")

        # ĐK 3: Golden Pocket
        if trong_vung:
            html += render_dieu_kien("Điều kiện 3/5 — Golden Pocket 61.8%–78.6% (1đ)", "pass",
                f"Giá đang trong vùng vàng: {gp_low} – {gp_high}. Vùng tổ chức hay đặt lệnh nhất.")
        else:
            html += render_dieu_kien("Điều kiện 3/5 — Golden Pocket 61.8%–78.6% (0đ)", "wait",
                f"Chờ giá hồi về vùng: {gp_low} – {gp_high} trước khi xét tiếp.")

        # ĐK 4: CHoCH (2 điểm)
        if co_choch:
            html += render_dieu_kien("Điều kiện 4/5 — CHoCH M15 ⭐ (2đ — quan trọng nhất)", "pass",
                f"{res.get('ly_do_choch','')} — Xác nhận cấu trúc đảo chiều thực sự.")
        elif trong_vung:
            html += render_dieu_kien("Điều kiện 4/5 — CHoCH M15 ⭐ (0đ — quan trọng nhất)", "wait",
                f"Giá đã vào GP nhưng chưa có CHoCH. Chờ nến {'xanh mạnh phá đỉnh' if loai=='BUY' else 'đỏ mạnh phá đáy'} nến trước.")
        else:
            html += render_dieu_kien("Điều kiện 4/5 — CHoCH M15 ⭐ (0đ — quan trọng nhất)", "fail",
                "Cần giá vào vùng GP trước, sau đó mới xét CHoCH.")

        # ĐK 5: RSI
        if co_phan_ky:
            html += render_dieu_kien("Điều kiện 5/5 — RSI Divergence (1đ)", "pass",
                f"{mo_ta_rsi} | RSI hiện tại: {rsi_val}")
        elif (loai == "BUY"  and isinstance(rsi_val, float) and rsi_val < 35) or \
             (loai == "SELL" and isinstance(rsi_val, float) and rsi_val > 65):
            html += render_dieu_kien("Điều kiện 5/5 — RSI Cực trị (1đ)", "pass",
                f"RSI {rsi_val} — {'Quá bán hỗ trợ BUY' if loai=='BUY' else 'Quá mua hỗ trợ SELL'}")
        else:
            html += render_dieu_kien("Điều kiện 5/5 — RSI Divergence (0đ)", "wait",
                f"RSI: {rsi_val} — Chưa có phân kỳ. Vẫn hợp lệ nếu đủ 3 điểm khác.")

        st.markdown(html, unsafe_allow_html=True)

        # THANH ĐIỂM
        st.write("")
        mau = "#00ff88" if diem >= 3 else "#ffaa00" if diem == 2 else "#ff4444"
        nhan = {5:"🔥 RẤT MẠNH — Winrate 80-85%", 4:"💪 MẠNH — Winrate 70-75%",
                3:"✅ ĐẠT CHUẨN — Winrate 60-65%", 2:"⚠️ YẾU — CHƯA NÊN VÀO",
                1:"❌ RẤT YẾU — KHÔNG VÀO", 0:"❌ KHÔNG ĐỦ — KHÔNG VÀO"}
        st.markdown(f"""
        <div class="score-bar">
            <h3 style="color:{mau};margin:0">Tổng điểm: {diem}/5 — {nhan.get(diem,'')}</h3>
            <p style="color:#888;margin:5px 0;font-size:13px">
            Vào lệnh an toàn ≥3đ | Tốt nhất ≥4đ | 5đ = cơ hội vàng
            </p>
        </div>""", unsafe_allow_html=True)

        st.write("")
        st.divider()

        # THÔNG SỐ VÀO LỆNH
        st.subheader("🎯 Thông số vào lệnh")
        ql = res.get('quan_ly')
        if ql and co_tin_hieu:
            st.markdown(f"### Entry: `{ql['entry']}`")
            cs, ct1, ct2 = st.columns(3)
            cs.error( f"🔴 **SL**\n\n`{ql['sl']}`\n\n{ql['kc_sl']} pip")
            ct1.success(f"🟢 **TP1 — 1:2**\n\n`{ql['tp1']}`\n\n+{round(ql['kc_sl']*2,2)} pip")
            ct2.success(f"🟢 **TP2 — 1:3**\n\n`{ql['tp2']}`\n\n+{round(ql['kc_sl']*3,2)} pip")
            st.write("")
            st.info("💡 Chốt 50% tại TP1 → Dời SL về hoà vốn → Để 50% chạy TP2")
            st.success("📱 Tín hiệu đã gửi Telegram!")
        else:
            st.info("⏳ Chưa đủ điều kiện — Sẽ tự gửi Telegram khi đủ ≥3 điểm.")

# ============================================================
# LOGIC QUÉT THỦ CÔNG
# ============================================================
if nut_quet:
    with st.spinner("🔍 Đang phân tích..."):
        st.session_state['ket_qua'] = lay_du_lieu_va_phan_tich(san_pham)
        st.session_state['lan_cuoi'] = datetime.now()

if 'ket_qua' in st.session_state:
    hien_thi(st.session_state['ket_qua'])

# THÔNG TIN SCANNER NGẦM
st.divider()
lan_cuoi_bg = st.session_state.get('lan_cuoi_bg')
if lan_cuoi_bg:
    st.caption(f"🤖 Scanner tự động — lần quét cuối: {lan_cuoi_bg.strftime('%H:%M:%S %d/%m/%Y')}")
else:
    st.caption("🤖 Scanner tự động đang khởi động...")

st.caption("⚠️ Chỉ mang tính tham khảo. Mọi quyết định giao dịch là trách nhiệm của bạn.")

import streamlit as st
import time
from datetime import datetime
from brain import lay_du_lieu_va_phan_tich

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
.metric-card {
    background: #1e2329;
    border-radius: 8px;
    padding: 15px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# HEADER
st.title("🦅 SMC Trading Signal")
st.caption("SMC + Fractal Swing + Golden Pocket + RSI Divergence + CHoCH M15 | R:R 1:2 / 1:3")
st.divider()

# ĐIỀU KHIỂN
c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
with c1:
    san_pham = st.selectbox("📦 Sản phẩm:", ["Vàng (Gold)", "Bitcoin (BTC)"])
with c2:
    che_do = st.selectbox("⏱️ Chế độ:", ["Thủ công", "Tự động mỗi 5 phút"])
with c3:
    st.write(""); st.write("")
    nut_quet = st.button("⚡ QUÉT NGAY", use_container_width=True, type="primary")
with c4:
    st.write(""); st.write("")
    if st.button("🗑️ Xóa", use_container_width=True):
        for k in ['ket_qua', 'lan_cuoi']:
            if k in st.session_state: del st.session_state[k]
        st.rerun()

st.divider()

# HIỂN THỊ KẾT QUẢ
vung = st.empty()

def hien_thi(res):
    with vung.container():
        if res.get("loi"):
            st.error(res["loi"])
            return

        st.caption(f"🕐 Cập nhật lúc: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}")

        # Dòng metric
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Giá hiện tại", f"${res.get('gia_hien_tai','N/A')}")
        c2.metric("📊 Xu hướng H1", res.get('xu_huong_h1','N/A'))
        c3.metric("📈 RSI M15", res.get('rsi','N/A'))
        c4.metric("🏆 Winrate", res.get('winrate','N/A'))

        st.write("")

        # Box trạng thái
        co_tin_hieu = res.get('co_tin_hieu', False)
        diem = res.get('diem_confluence', 0)

        if co_tin_hieu:
            st.markdown(f"""
            <div class="signal-box">
                <h2 style="color:#00ff88;margin:0">{res.get('chat_luong','')}</h2>
                <h3 style="color:#fff;margin:8px 0">{res.get('trang_thai','')}</h3>
                <p style="color:#aaa;margin:0">Điểm Confluence: {diem}/5</p>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="wait-box">
                <h3 style="color:#ffaa00;margin:0">{res.get('chat_luong','')}</h3>
                <p style="color:#ccc;margin:8px 0">{res.get('trang_thai','')}</p>
                <p style="color:#888;margin:0">Điểm: {diem}/5 — Chưa đủ điều kiện</p>
            </div>""", unsafe_allow_html=True)

        st.write("")

        # 2 cột: Confluence | Vào lệnh
        cl, cr = st.columns(2)

        with cl:
            st.subheader("📋 Phân tích Confluence")
            if res.get('loai'):
                loai = res['loai']
                mau  = "🟢" if loai == "BUY" else "🔴"
                st.markdown(f"**Hướng:** {mau} **{loai}**")
                st.markdown(f"**Swing X:** `{res.get('diem_X','N/A')}`")
                st.markdown(f"**Swing A:** `{res.get('diem_A','N/A')}`")
                st.markdown(f"**Golden Pocket:** `{res.get('gp_low','N/A')} – {res.get('gp_high','N/A')}`")
                st.markdown(f"**Trong GP:** {'✅' if res.get('trong_vung') else '❌'}")
                st.markdown(f"**RSI:** {res.get('mo_ta_rsi','N/A')}")
            st.write("")
            st.markdown("**Chi tiết điểm:**")
            for item in res.get('chi_tiet_confluence', []):
                st.markdown(f"• {item}")

        with cr:
            st.subheader("🎯 Thông số vào lệnh")
            ql = res.get('quan_ly')
            if ql and co_tin_hieu:
                loai = res.get('loai','BUY')
                st.markdown(f"### Entry: `{ql['entry']}`")
                cs, ct1, ct2 = st.columns(3)
                cs.error(f"🔴 **SL**\n\n`{ql['sl']}`\n\n{ql['kc_sl']} pip")
                ct1.success(f"🟢 **TP1**\n\n`{ql['tp1']}`\n\nR:R 1:2")
                ct2.success(f"🟢 **TP2**\n\n`{ql['tp2']}`\n\nR:R 1:3")
                st.write("")
                st.info("💡 Chốt 50% tại TP1 → dời SL về hoà vốn → để 50% chạy TP2")
                st.success("📱 Đã gửi tín hiệu lên Telegram!")
            else:
                st.markdown("""
                <div style="background:#1a1a2e;border-radius:8px;padding:30px;text-align:center">
                    <h4 style="color:#888">⏳ Đang theo dõi thị trường...</h4>
                    <p style="color:#666">Sẽ tự động gửi Telegram<br>khi có tín hiệu đủ mạnh (≥3 điểm)</p>
                </div>""", unsafe_allow_html=True)

# LOGIC QUÉT
if nut_quet:
    with st.spinner("🔍 Đang phân tích..."):
        st.session_state['ket_qua'] = lay_du_lieu_va_phan_tich(san_pham)
        st.session_state['lan_cuoi'] = datetime.now()

if 'ket_qua' in st.session_state:
    hien_thi(st.session_state['ket_qua'])

# TỰ ĐỘNG 5 PHÚT
if che_do == "Tự động mỗi 5 phút":
    lan_cuoi = st.session_state.get('lan_cuoi')
    if lan_cuoi:
        da_qua  = (datetime.now() - lan_cuoi).seconds
        con_lai = max(0, 300 - da_qua)
        st.progress(min(da_qua/300, 1.0),
                    text=f"⏱️ Quét tiếp sau: {con_lai}s | Lần cuối: {lan_cuoi.strftime('%H:%M:%S')}")
        if da_qua >= 300:
            with st.spinner("🔄 Tự động quét..."):
                st.session_state['ket_qua'] = lay_du_lieu_va_phan_tich(san_pham)
                st.session_state['lan_cuoi'] = datetime.now()
            st.rerun()
        else:
            time.sleep(30)
            st.rerun()
    else:
        st.info("👆 Nhấn **QUÉT NGAY** để bắt đầu chế độ tự động")

st.divider()
st.caption("⚠️ Chỉ mang tính tham khảo. Mọi quyết định giao dịch là trách nhiệm của bạn.")

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import re
from datetime import datetime

# ==========================================
# 1. KẾT NỐI HỆ THỐNG
# ==========================================
st.set_page_config(page_title="Hệ Thống Chỉ Huy XSMB", layout="wide")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zd0OcKa3GtEJqoBp6nH7Sr3mZ646oIcKPJ6KPiMJSSE/edit?gid=616470749#gid=616470749"

@st.cache_resource
def get_client():
    key_dict = json.loads(st.secrets["gcp_service_account"]["json_key"], strict=False)
    return gspread.authorize(Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]))

@st.cache_data(ttl=60)
def load_data():
    try:
        ws = get_client().open_by_url(SHEET_URL).worksheet("Database")
        all_rows = ws.get_all_values()
        if len(all_rows) < 2: return pd.DataFrame(), pd.DataFrame(), ""

        raw_cols = [str(c).strip() for c in all_rows[0]]
        df_db = pd.DataFrame(all_rows[1:], columns=raw_cols)
        col_ngay = [c for c in df_db.columns if 'ngày' in c.lower()][0]
        col_data = [c for c in df_db.columns if 'danh_sach' in c.lower() or 'giai_full' in c.lower()][0]
        
        # Lọc dữ liệu chuẩn 27 giải
        df_db['clean_str'] = df_db[col_data].str.replace(r'[^0-9]', '', regex=True)
        df_db = df_db[df_db['clean_str'].str.len() >= 100]
        df_db['Date_Obj'] = pd.to_datetime(df_db[col_ngay], dayfirst=True, errors='coerce')
        df_db = df_db.dropna(subset=['Date_Obj']).sort_values('Date_Obj').reset_index(drop=True)
        
        ws_kt = get_client().open_by_url(SHEET_URL).worksheet("KeToan")
        df_kt = pd.DataFrame(ws_kt.get_all_values()[1:], columns=ws_kt.get_all_values()[0]) if len(ws_kt.get_all_values()) > 1 else pd.DataFrame()
        
        return df_db, df_kt, col_data
    except Exception as e:
        st.error(f"Lỗi: {e}")
        return pd.DataFrame(), pd.DataFrame(), ""

df, df_ketoan, col_full = load_data()

# ==========================================
# 2. BỘ NÃO QUANT (TÍNH TOÁN DNA)
# ==========================================
@st.cache_data(ttl=60)
def compute_engine(df_in, col_name):
    day_strs, day_sets, gan_tracker = [], [], {str(i).zfill(2): 0 for i in range(100)}
    gap_cts = {str(i).zfill(2): {g: 0 for g in range(16)} for i in range(100)}
    total_hits = {str(i).zfill(2): 0 for i in range(100)}

    for idx, row in df_in.iterrows():
        raw_list = re.findall(r'\d{2,5}', str(row[col_name]))
        full_str = "".join(raw_list)
        l2 = [n[-2:] for n in raw_list]
        day_strs.append(full_str); day_sets.append(set(l2))
        
        for i in range(100):
            n_s = str(i).zfill(2)
            if n_s in l2:
                if idx > 0: gap_cts[n_s][min(gan_tracker[n_s], 15)] += 1; total_hits[n_s] += 1
                gan_tracker[n_s] = 0
            else: gan_tracker[n_s] += 1
    return day_strs, day_sets, gan_tracker, gap_cts, total_hits

if not df.empty:
    d_strs, d_sets, g_tracker, gap_cts, t_hits = compute_engine(df, col_full)

# ==========================================
# 3. GIAO DIỆN CHỈ HUY (BẢN XÚC TÍCH)
# ==========================================
st.sidebar.success(f"Dữ liệu: {len(df)} ngày")

tab1, tab2, tab3 = st.tabs(["🦅 ĐỀ XUẤT CHIẾN THUẬT", "🔍 SOI CẦU CHI TIẾT", "📝 NHẬP LIỆU"])

with tab1:
    st.markdown("## 📊 BÁO CÁO TẤN CÔNG HÔM NAY")
    
    if len(d_strs) >= 5:
        s0, preds = d_strs[-1], set()
        for p1 in range(len(s0)):
            for p2 in range(len(s0)):
                is_bridge = True
                for d in range(1, 4):
                    if p1 >= len(d_strs[-1-d]) or p2 >= len(d_strs[-1-d]): is_bridge = False; break
                    if d_strs[-1-d][p1] + d_strs[-1-d][p2] not in d_sets[-d]: is_bridge = False; break
                if is_bridge: preds.add(s0[p1] + s0[p2])

        if preds:
            dai_bang, rua = [], []
            for num in preds:
                curr_g = g_tracker.get(num, 0)
                best_g, max_p = 0, -1
                for g in range(16):
                    p = gap_cts[num][g] / max(1, t_hits[num])
                    if p > max_p: max_p = p; best_g = g
                
                info = {"Số": num, "Gan": curr_g, "DNA": best_g}
                if curr_g == best_g: dai_bang.append(info)
                else: rua.append(info)

            # --- HIỂN THỊ XÚC TÍCH ---
            c1, c2 = st.columns(2)
            with c1:
                st.error("🦅 DANH MỤC: ĐẠI BÀNG (Đúng DNA)")
                if dai_bang:
                    for item in dai_bang:
                        st.metric(label=f"Lô {item['Số']}", value=f"Gan {item['Gan']} ngày", delta="ĐỈNH NỔ")
                else: st.write("Hôm nay chưa có mã Đại Bàng.")

            with c2:
                st.success("🐢 DANH MỤC: RÙA BỌC THÉP (Thăm dò)")
                if rua:
                    for item in rua:
                        st.write(f"**Lô {item['Số']}** | Gan: {item['Gan']}d (DNA: {item['DNA']}d)")
                else: st.write("Không có mã Rùa.")
        else:
            st.info("Hệ thống chưa tìm thấy đường cầu nào đủ tin cậy cho hôm nay.")
    
    st.divider()
    st.subheader("💰 Sổ Kế Toán")
    with st.expander("Ghi lệnh đánh mới"):
        with st.form("f_kt"):
            so = st.text_input("Số lô:", max_chars=2)
            diem = st.number_input("Điểm:", min_value=1, value=10)
            if st.form_submit_button("Lưu lên Cloud"):
                get_client().open_by_url(SHEET_URL).worksheet("KeToan").append_row([datetime.now().strftime("%d-%m-%Y"), so, diem, diem*1000, 0, 0, "⏳ Chờ"])
                st.cache_data.clear(); st.rerun()

    if not df_ketoan.empty:
        st.dataframe(df_ketoan.tail(10), use_container_width=True, hide_index=True)

with tab3:
    st.subheader("📥 Cập nhật kết quả")
    d_in = st.date_input("Ngày:", value=datetime.now())
    txt = st.text_area("Dán 27 giải:")
    if st.button("Đồng bộ"):
        nums = re.findall(r'\d+', txt)
        if len(nums) >= 27:
            get_client().open_by_url(SHEET_URL).worksheet("Database").append_row([d_in.strftime("%d-%m-%Y"), "," + ",".join(nums[:27]) + ",", "27"])
            st.cache_data.clear(); st.success("Xong!"); st.rerun()

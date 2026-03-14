import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import re
from datetime import datetime

# ==========================================
# 1. KẾT NỐI & LÀM SẠCH DỮ LIỆU
# ==========================================
st.set_page_config(page_title="XSMB Quant Pro", layout="wide")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zd0OcKa3GtEJqoBp6nH7Sr3mZ646oIcKPJ6KPiMJSSE/edit?gid=616470749#gid=616470749"

@st.cache_resource
def get_client():
    key_dict = json.loads(st.secrets["gcp_service_account"]["json_key"], strict=False)
    return gspread.authorize(Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]))

@st.cache_data(ttl=60)
def load_and_fix_data():
    try:
        ws = get_client().open_by_url(SHEET_URL).worksheet("Database")
        all_rows = ws.get_all_values()
        if len(all_rows) < 2: return pd.DataFrame(), pd.DataFrame(), ""

        # Chuẩn hóa tiêu đề
        raw_cols = [str(c).strip() for c in all_rows[0]]
        df_db = pd.DataFrame(all_rows[1:], columns=raw_cols)
        
        col_ngay = [c for c in df_db.columns if 'ngày' in c.lower()][0]
        col_data = [c for c in df_db.columns if 'danh_sach' in c.lower() or 'giai_full' in c.lower()][0]
        
        # LỌC NGHIÊM NGẶT: Chỉ lấy dòng có ít nhất 100 ký tự số (đủ 27 giải)
        df_db['clean_str'] = df_db[col_data].str.replace(r'[^0-9]', '', regex=True)
        df_db = df_db[df_db['clean_str'].str.len() >= 100]
        
        df_db['Date_Obj'] = pd.to_datetime(df_db[col_ngay], dayfirst=True, errors='coerce')
        df_db = df_db.dropna(subset=['Date_Obj']).sort_values('Date_Obj').reset_index(drop=True)
        
        # Đọc KeToan
        ws_kt = get_client().open_by_url(SHEET_URL).worksheet("KeToan")
        raw_kt = ws_kt.get_all_values()
        df_kt = pd.DataFrame(raw_kt[1:], columns=raw_kt[0]) if len(raw_kt) > 1 else pd.DataFrame()
        
        return df_db, df_kt, col_data
    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu: {e}")
        return pd.DataFrame(), pd.DataFrame(), ""

df, df_ketoan, col_full = load_and_fix_data()

# ==========================================
# 2. BỘ NÃO QUANT (TỐI ƯU TRÁNH LỖI INDEX)
# ==========================================
@st.cache_data(ttl=60)
def compute_dna(df_in, col_name):
    day_strs, day_sets, gan_tracker = [], [], {str(i).zfill(2): 0 for i in range(100)}
    gap_cts = {str(i).zfill(2): {g: 0 for g in range(16)} for i in range(100)}
    total_hits = {str(i).zfill(2): 0 for i in range(100)}

    for idx, row in df_in.iterrows():
        # Chỉ lấy chuỗi số thuần túy để tọa độ p1, p2 luôn khớp nhau
        raw_list = re.findall(r'\d{2,5}', str(row[col_name]))
        full_str = "".join(raw_list)
        l2 = [n[-2:] for n in raw_list]
        
        day_strs.append(full_str)
        day_sets.append(set(l2))
        
        for i in range(100):
            n_s = str(i).zfill(2)
            if n_s in l2:
                if idx > 0:
                    gap_cts[n_s][min(gan_tracker[n_s], 15)] += 1
                    total_hits[n_s] += 1
                gan_tracker[n_s] = 0
            else: gan_tracker[n_s] += 1
    return day_strs, day_sets, gan_tracker, gap_cts, total_hits

if not df.empty:
    d_strs, d_sets, g_tracker, gap_cts, t_hits = compute_dna(df, col_full)
else:
    st.stop()

# ==========================================
# 3. GIAO DIỆN & SOI CẦU AN TOÀN
# ==========================================
st.sidebar.success(f"✅ Dữ liệu chuẩn: {len(df)} ngày")

tab1, tab2, tab3 = st.tabs(["🎯 DỰ ĐOÁN", "🔍 SOI CẦU", "📝 NHẬP LIỆU"])

with tab1:
    st.subheader("💡 Gợi ý hôm nay (DNA nổ)")
    if len(d_strs) >= 5:
        s0, preds = d_strs[-1], set()
        # Duyệt tọa độ p1, p2
        for p1 in range(len(s0)):
            for p2 in range(len(s0)):
                is_bridge = True
                for d in range(1, 4):
                    # KIỂM TRA ĐỘ DÀI: Nếu ngày quá khứ ngắn hơn hiện tại thì bỏ qua tọa độ này
                    if p1 >= len(d_strs[-1-d]) or p2 >= len(d_strs[-1-d]):
                        is_bridge = False; break
                    
                    pair = d_strs[-1-d][p1] + d_strs[-1-d][p2]
                    if pair not in d_sets[-d]:
                        is_bridge = False; break
                
                if is_bridge: preds.add(s0[p1] + s0[p2])
        
        if preds:
            for num in sorted(preds):
                curr_g = g_tracker.get(num, 0)
                best_g, max_p = 0, -1
                for g in range(16):
                    p = gap_cts[num][g] / max(1, t_hits[num])
                    if p > max_p: max_p = p; best_g = g
                
                st.markdown(f"### 🎯 Lô: **{num}**")
                st.write(f"📊 Gan hiện tại: **{curr_g}** | 🧬 Đỉnh DNA: **{best_g}**")
                if curr_g == best_g: st.error("🦅 CHIẾN THUẬT: ĐẠI BÀNG")
                elif 3 <= curr_g <= 8: st.success("🐢 CHIẾN THUẬT: RÙA")
                st.divider()
        else: st.info("Hôm nay chưa tìm thấy cầu thông 3 ngày thỏa mãn.")
    else: st.warning("Cần thêm dữ liệu lịch sử để kích hoạt bộ não Quant.")

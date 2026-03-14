import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import re
from datetime import datetime, time

# ==========================================
# 1. KẾT NỐI HỆ THỐNG
# ==========================================
st.set_page_config(page_title="Hệ Thống Chỉ Huy XSMB", layout="wide")

# CSS để phóng to cỡ chữ toàn hệ thống và tùy chỉnh màu sắc
st.markdown("""
    <style>
    html, body, [class*="css"]  {
        font-size: 20px !important;
    }
    .dai-bang { color: #FF8C00; font-weight: bold; font-size: 24px; }
    .rua { color: #1E90FF; font-weight: bold; font-size: 24px; }
    .stMetric label { font-size: 20px !important; }
    .stMetric div { font-size: 30px !important; }
    </style>
    """, unsafe_allow_html=True)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1zd0OcKa3GtEJqoBp6nH7Sr3mZ646oIcKPJ6KPiMJSSE/edit?gid=616470749#gid=616470749"

@st.cache_resource
def get_client():
    key_dict = json.loads(st.secrets["gcp_service_account"]["json_key"], strict=False)
    return gspread.authorize(Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]))

@st.cache_data(ttl=60)
def load_data():
    client = get_client()
    sh = client.open_by_url(SHEET_URL)
    ws_db = sh.worksheet("Database")
    all_db = ws_db.get_all_values()
    df_db = pd.DataFrame(all_db[1:], columns=all_db[0])
    df_db['Date_Obj'] = pd.to_datetime(df_db['Ngày'], dayfirst=True, errors='coerce')
    df_db = df_db.dropna(subset=['Date_Obj']).sort_values('Date_Obj').reset_index(drop=True)
    
    ws_kt = sh.worksheet("KeToan")
    df_kt = pd.DataFrame(ws_kt.get_all_values()[1:], columns=ws_kt.get_all_values()[0])
    return df_db, df_kt

df, df_ketoan = load_data()

# ==========================================
# 2. BỘ NÃO QUANT & GỢI Ý
# ==========================================
@st.cache_data(ttl=60)
def get_suggestions(df_in):
    day_strs, day_sets, gan_tracker = [], [], {str(i).zfill(2): 0 for i in range(100)}
    gap_cts = {str(i).zfill(2): {g: 0 for g in range(16)} for i in range(100)}
    total_hits = {str(i).zfill(2): 0 for i in range(100)}

    for idx, row in df_in.iterrows():
        raw_list = re.findall(r'\d{2,5}', str(row['Danh_Sach_Giai_Full']))
        l2 = [n[-2:] for n in raw_list]
        day_strs.append("".join(raw_list)); day_sets.append(set(l2))
        for i in range(100):
            n_s = str(i).zfill(2)
            if n_s in l2:
                if idx > 0: gap_cts[n_s][min(gan_tracker[n_s], 15)] += 1; total_hits[n_s] += 1
                gan_tracker[n_s] = 0
            else: gan_tracker[n_s] += 1
            
    s0, preds = day_strs[-1], set()
    for p1 in range(len(s0)):
        for p2 in range(len(s0)):
            is_bridge = True
            for d in range(1, 4):
                if p1 >= len(day_strs[-1-d]) or p2 >= len(day_strs[-1-d]): is_bridge = False; break
                if day_strs[-1-d][p1] + day_strs[-1-d][p2] not in day_sets[-d]: is_bridge = False; break
            if is_bridge: preds.add(s0[p1] + s0[p2])
            
    results = []
    for num in preds:
        curr_g = gan_tracker[num]
        best_g, max_p = 0, -1
        for g in range(16):
            p = gap_cts[num][g] / max(1, total_hits[num])
            if p > max_p: max_p = p; best_g = g
        results.append({"Số": num, "Gan": curr_g, "DNA": best_g, "Loại": "Đại Bàng" if curr_g == best_g else "Rùa"})
    return results

suggestions = get_suggestions(df)

# ==========================================
# 3. GIAO DIỆN ĐIỀU HÀNH CHIẾN THUẬT
# ==========================================
st.sidebar.markdown(f"## 📊 Dữ liệu: {len(df)} ngày")
now = datetime.now()
is_before_cutoff = now.time() < time(18, 0)

# Khởi tạo trạng thái checkbox nếu chưa có
if 'check_all' not in st.session_state: st.session_state.check_all = True

tab1, tab2 = st.tabs(["🚀 LỆNH TẤN CÔNG", "📥 NHẬP KẾ QUẢ"])

with tab1:
    st.header("🦅 Bảng Chốt Số (Cỡ chữ lớn)")
    
    # Nút Check All / Uncheck All
    c_btn1, c_btn2 = st.columns(2)
    if c_btn1.button("✅ Chọn tất cả"): st.session_state.check_all = True; st.rerun()
    if c_btn2.button("❌ Bỏ chọn tất cả"): st.session_state.check_all = False; st.rerun()

    input_data = []
    for s in suggestions:
        color_class = "dai-bang" if s['Loại'] == "Đại Bàng" else "rua"
        input_data.append({
            "Chọn": st.session_state.check_all,
            "Số": s['Số'],
            "Loại": s['Loại'],
            "Điểm": 20 if s['Loại'] == "Đại Bàng" else 10,
            "Phân tích": f"Gan {s['Gan']} (Đỉnh {s['DNA']})"
        })
    
    if input_data:
        # Hiển thị bảng màu sắc
        edited_df = st.data_editor(pd.DataFrame(input_data), use_container_width=True, hide_index=True)
        
        # Tạo lệnh Copy-Paste cấu trúc: sốxđiểm, sốxđiểm
        picks = edited_df[edited_df['Chọn'] == True]
        cmd_text = ", ".join([f"{r['Số']}x{r['Điểm']}" for _, r in picks.iterrows()])
        
        st.subheader("📋 Lệnh dán Web cá cược")
        st.code(cmd_text, language="text") # Click 1 nhát vào icon góc phải để copy

        if st.button("🔥 LƯU LỊCH SỬ CHỐT SỐ", type="primary"):
            if is_before_cutoff:
                ws_kt = get_client().open_by_url(SHEET_URL).worksheet("KeToan")
                for _, r in picks.iterrows():
                    ws_kt.append_row([now.strftime("%d-%m-%Y"), r['Số'], r['Điểm'], r['Điểm']*23000, 0, 0, "⏳ Đang đánh"])
                st.success("Đã chốt lệnh thành công!")
            else: st.error("Đã quá 18:00 - Không thể lưu thêm.")

with tab2:
    st.subheader("📥 Cập nhật KQXS & Quyết toán")
    txt = st.text_area("Dán 27 giải:")
    if st.button("Đồng bộ & Quyết toán tiền"):
        nums = re.findall(r'\d+', txt)
        if len(nums) >= 27:
            ws_db = get_client().open_by_url(SHEET_URL).worksheet("Database")
            ws_db.append_row([now.strftime("%d-%m-%Y"), "," + ",".join(nums[:27]) + ",", "27"])
            
            ws_kt = get_client().open_by_url(SHEET_URL).worksheet("KeToan")
            records = ws_kt.get_all_values()
            l2 = [n[-2:] for n in nums]
            for i, row in enumerate(records):
                if row[0] == now.strftime("%d-%m-%Y") and row[6] == "⏳ Đang đánh":
                    hits = l2.count(row[1])
                    thu = hits * int(row[2]) * 80000
                    ws_kt.update_cell(i+1, 5, thu)
                    ws_kt.update_cell(i+1, 6, thu - int(row[3]))
                    ws_kt.update_cell(i+1, 7, f"✅ Ăn {hits}" if hits > 0 else "❌ Trượt")
            st.cache_data.clear(); st.success("Xong!"); st.rerun()

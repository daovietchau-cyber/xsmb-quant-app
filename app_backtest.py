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
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zd0OcKa3GtEJqoBp6nH7Sr3mZ646oIcKPJ6KPiMJSSE/edit?gid=616470749#gid=616470749"

@st.cache_resource
def get_client():
    key_dict = json.loads(st.secrets["gcp_service_account"]["json_key"], strict=False)
    return gspread.authorize(Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]))

@st.cache_data(ttl=60)
def load_data():
    client = get_client()
    sh = client.open_by_url(SHEET_URL)
    
    # Database
    ws_db = sh.worksheet("Database")
    all_db = ws_db.get_all_values()
    df_db = pd.DataFrame(all_db[1:], columns=all_db[0])
    df_db['clean_str'] = df_db['Danh_Sach_Giai_Full'].str.replace(r'[^0-9]', '', regex=True)
    df_db['Date_Obj'] = pd.to_datetime(df_db['Ngày'], dayfirst=True, errors='coerce')
    df_db = df_db.dropna(subset=['Date_Obj']).sort_values('Date_Obj').reset_index(drop=True)
    
    # KeToan
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
        full_str = "".join(raw_list)
        l2 = [n[-2:] for n in raw_list]
        day_strs.append(full_str); day_sets.append(set(l2))
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
# 3. GIAO DIỆN CHỈ HUY & LỆNH ĐÁNH
# ==========================================
st.sidebar.success(f"Dữ liệu: {len(df)} ngày")
now = datetime.now()
is_before_cutoff = now.time() < time(18, 0)

tab1, tab2 = st.tabs(["🚀 LỆNH TẤN CÔNG", "📥 NHẬP KẾ QUẢ"])

with tab1:
    st.header("🦅 Bảng Chốt Số Chiến Thuật")
    
    # 1. Bảng nhập liệu điền sẵn
    input_data = []
    for s in suggestions:
        # Đề xuất: Đại bàng 20đ, Rùa 10đ
        default_point = 20 if s['Loại'] == "Đại Bàng" else 10
        input_data.append({"Chọn": True, "Số": s['Số'], "Điểm": default_point, "Loại": s['Loại']})
    
    if input_data:
        df_input = pd.DataFrame(input_data)
        edited_df = st.data_editor(df_input, use_container_width=True, hide_index=True)
        
        # 2. Tạo lệnh Copy-Paste
        final_picks = edited_df[edited_df['Chọn'] == True]
        cmd_list = [f"{row['Số']}x{row['Điểm']}" for _, row in final_picks.iterrows()]
        cmd_text = ", ".join(cmd_list)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.text_area("📋 Lệnh dán Web cá cược (Copy dòng này):", value=cmd_text, height=70)
        with c2:
            if is_before_cutoff:
                if st.button("🔥 CHỐT LỆNH & LƯU CLOUD"):
                    # Lưu vào KeToan với trạng thái Chờ
                    ws_kt = get_client().open_by_url(SHEET_URL).worksheet("KeToan")
                    for _, r in final_picks.iterrows():
                        ws_kt.append_row([now.strftime("%d-%m-%Y"), r['Số'], r['Điểm'], r['Điểm']*23000, 0, 0, "⏳ Đang đánh"])
                    st.success("Đã chốt lệnh thành công!")
            else:
                st.error("🚫 Đã sau 18:00. Hệ thống ngừng chốt số.")

    st.divider()
    st.subheader("📊 Lịch sử đánh gần đây")
    st.dataframe(df_ketoan.tail(10), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📥 Cập nhật KQXS")
    d_in = st.date_input("Ngày:", value=now)
    txt = st.text_area("Dán 27 giải:")
    if st.button("Đồng bộ & Tự động tính toán"):
        nums = re.findall(r'\d+', txt)
        if len(nums) >= 27:
            # Lưu Database
            get_client().open_by_url(SHEET_URL).worksheet("Database").append_row([d_in.strftime("%d-%m-%Y"), "," + ",".join(nums[:27]) + ",", "27"])
            
            # TỰ ĐỘNG ĐỐI SOÁT KẾ TOÁN (Logic chuyển dữ liệu sau 18h)
            ws_kt = get_client().open_by_url(SHEET_URL).worksheet("KeToan")
            records = ws_kt.get_all_values()
            ngay_str = d_in.strftime("%d-%m-%Y")
            l2 = [n[-2:] for n in nums]
            
            for i, row in enumerate(records):
                if row[0] == ngay_str and row[6] == "⏳ Đang đánh":
                    so_danh = row[1]
                    diem = int(row[2])
                    hits = l2.count(so_danh)
                    thu_ve = hits * diem * 80000
                    lai = thu_ve - (diem * 23000)
                    status = f"✅ Ăn {hits} nháy" if hits > 0 else "❌ Trượt"
                    # Cập nhật trực tiếp lên dòng đó trên Sheets
                    ws_kt.update_cell(i+1, 5, thu_ve)
                    ws_kt.update_cell(i+1, 6, lai)
                    ws_kt.update_cell(i+1, 7, status)
            
            st.cache_data.clear(); st.success("Đã đồng bộ và quyết toán xong!"); st.rerun()

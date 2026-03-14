import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import re
import time
from datetime import datetime

# ==========================================
# CẤU HÌNH HỆ THỐNG & GIAO DIỆN
# ==========================================
st.set_page_config(page_title="Hệ Thống Phân Tích XSMB (Cloud Quant)", layout="wide")

# ĐƯỜNG DẪN FILE GOOGLE SHEETS CỦA BẠN
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zd0OcKa3GtEJqoBp6nH7Sr3mZ646oIcKPJ6KPiMJSSE/edit?gid=616470749#gid=616470749"

# ==========================================
# KẾT NỐI GOOGLE SHEETS (DÙNG SECRETS)
# ==========================================
@st.cache_resource
def get_gspread_client():
    try:
        # Lấy thông tin từ mục Secrets trên Streamlit Cloud
        key_dict = json.loads(st.secrets["gcp_service_account"]["json_key"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Lỗi kết nối Cloud: {e}")
        st.stop()

client = get_gspread_client()
sheet = client.open_by_url(SHEET_URL)

@st.cache_data(ttl=60) 
def load_all_data():
    # Tải dữ liệu từ tab Database
    ws_db = sheet.worksheet("Database")
    df_raw = pd.DataFrame(ws_db.get_all_records())
    
    if not df_raw.empty:
        df_raw['Ngày'] = df_raw['Ngày'].astype(str)
        df_raw['Date_Obj'] = pd.to_datetime(df_raw['Ngày'], format='%d-%m-%Y', errors='coerce')
        df_raw = df_raw.dropna(subset=['Date_Obj']).sort_values('Date_Obj').reset_index(drop=True)
    
    # Tải dữ liệu từ tab KeToan
    ws_kt = sheet.worksheet("KeToan")
    df_kt = pd.DataFrame(ws_kt.get_all_records())
    if not df_kt.empty:
        df_kt['Số_Lô'] = df_kt['Số_Lô'].astype(str).str.zfill(2)
        
    return df_raw, df_kt

df, df_ketoan = load_all_data()

# ==========================================
# XỬ LÝ DỮ LIỆU LÕI
# ==========================================
def process_core(df_in):
    day_lists = []
    day_sets = []
    day_strings = []
    gan_tracker = {str(i).zfill(2): 0 for i in range(100)}
    gap_counts = {str(i).zfill(2): {g: 0 for g in range(16)} for i in range(100)}
    total_hits = {str(i).zfill(2): 0 for i in range(100)}

    for idx, row in df_in.iterrows():
        raw_list = [n[-2:] for n in str(row['Danh_Sach_Giai_Full']).split(',') if len(n) >= 2]
        day_lists.append(raw_list)
        day_sets.append(set(raw_list))
        day_strings.append("".join([n for n in str(row['Danh_Sach_Giai_Full']).split(',') if len(n) >= 2]))
        
        # Cập nhật nhịp Gan
        current_day_counts = {str(i).zfill(2): raw_list.count(str(i).zfill(2)) for i in range(100)}
        for i in range(100):
            n_str = str(i).zfill(2)
            if current_day_counts[n_str] > 0:
                if idx > 0:
                    gap_counts[n_str][min(gan_tracker[n_str], 15)] += 1
                    total_hits[n_str] += 1
                gan_tracker[n_str] = 0
            else:
                gan_tracker[n_str] += 1
                
    return day_lists, day_sets, day_strings, gan_tracker, gap_counts, total_hits

day_lists, day_sets, day_strings, gan_tracker, gap_counts, total_hits = process_core(df)

# ==========================================
# GIAO DIỆN STREAMLIT
# ==========================================
st.sidebar.title("📊 XSMB QUANT CLOUD")
mode = st.sidebar.radio("Chế độ xem:", ["📱 Mobile (Gọn)", "💻 PC (Đầy đủ)"])

tab1, tab2, tab3 = st.tabs(["🎯 Dự đoán & Kế toán", "🔍 Soi Cầu", "📝 Nhập liệu"])

# --- TAB 1: DỰ ĐOÁN & KẾ TOÁN ---
with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("🔥 Gợi ý hôm nay")
        # Thuật toán dự đoán dựa trên cầu 3 ngày
        s0 = day_strings[-1]
        preds = set()
        if len(s0) >= 100:
            for p1 in range(len(s0)):
                for p2 in range(len(s0)):
                    valid = True
                    for d in range(1, 4):
                        if day_strings[-1-d][p1] + day_strings[-1-d][p2] not in day_sets[-d]:
                            valid = False; break
                    if valid: preds.add(s0[p1] + s0[p2])
        
        if preds:
            st.write(f"Cặp số tiềm năng: {', '.join(list(preds))}")
        else:
            st.write("Đang quét tín hiệu...")

    with col2:
        st.subheader("💰 Sổ Kế Toán")
        with st.form("form_kt"):
            so = st.text_input("Số lô:", max_chars=2)
            diem = st.number_input("Điểm:", min_value=1, value=10)
            if st.form_submit_button("Lưu lên Sheets"):
                ws_kt = sheet.worksheet("KeToan")
                ngay_nay = datetime.now().strftime("%d-%m-%Y")
                ws_kt.append_row([ngay_nay, so, diem, diem*1000, 0, 0, "⏳ Chờ"])
                st.cache_data.clear()
                st.success("Đã đồng bộ lên Cloud!")
                st.rerun()

# --- TAB 3: NHẬP LIỆU (QUAN TRỌNG NHẤT) ---
with tab3:
    st.subheader("📥 Cập nhật kết quả mới")
    ngay_nhap = st.date_input("Ngày quay:", value=datetime.now())
    txt = st.text_area("Dán 27 giải từ web vào đây:")
    if st.button("Xác nhận Đẩy lên Cloud"):
        nums = re.findall(r'\d+', txt)
        if len(nums) >= 27:
            res = "," + ",".join(nums[:27]) + ","
            ws_db = sheet.worksheet("Database")
            ngay_str = ngay_nhap.strftime("%d-%m-%Y")
            ws_db.append_row([ngay_str, res, "27"])
            st.cache_data.clear()
            st.success(f"Đã lưu kết quả ngày {ngay_str}!")
        else:
            st.error(f"Chỉ tìm thấy {len(nums)} số. Cần đủ 27 giải.")

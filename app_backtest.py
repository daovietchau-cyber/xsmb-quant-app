import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import re
import time
from datetime import datetime

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG & KẾT NỐI CLOUD
# ==========================================
st.set_page_config(page_title="XSMB Quant Cloud", layout="wide")

# Đường dẫn file Google Sheets của bạn
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zd0OcKa3GtEJqoBp6nH7Sr3mZ646oIcKPJ6KPiMJSSE/edit?gid=616470749#gid=616470749"

@st.cache_resource
def get_gspread_client():
    try:
        # Đọc Key từ Secrets với chế độ strict=False
        key_dict = json.loads(st.secrets["gcp_service_account"]["json_key"], strict=False)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Lỗi cấu hình Cloud (Secrets): {e}")
        st.stop()

# Khởi tạo kết nối
try:
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL)
except Exception as e:
    st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
    st.stop()

@st.cache_data(ttl=30) 
def load_all_data():
    try:
        # --- XỬ LÝ DATABASE ---
        ws_db = sheet.worksheet("Database")
        data_db = ws_db.get_all_values()
        if len(data_db) > 1:
            df_raw = pd.DataFrame(data_db[1:], columns=data_db[0])
            df_raw['Ngày'] = df_raw['Ngày'].astype(str)
            df_raw['Date_Obj'] = pd.to_datetime(df_raw['Ngày'], format='%d-%m-%Y', errors='coerce')
            df_raw = df_raw.dropna(subset=['Date_Obj']).sort_values('Date_Obj').reset_index(drop=True)
        else:
            df_raw = pd.DataFrame(columns=['Ngày', 'Danh_Sach_Giai_Full', 'So_Giai'])
        
        # --- XỬ LÝ KẾ TOÁN (SỬ DỤNG PHƯƠNG PHÁP AN TOÀN) ---
        ws_kt = sheet.worksheet("KeToan")
        data_kt = ws_kt.get_all_values()
        if len(data_kt) > 0:
            header = data_kt[0]
            rows = data_kt[1:]
            df_kt = pd.DataFrame(rows, columns=header)
            # Lọc bỏ cột thừa nếu có
            cols_needed = ['Ngày_Đánh', 'Số_Lô', 'Điểm', 'Vốn', 'Thu_Về', 'Lãi_Lỗ', 'Trạng_Thái']
            df_kt = df_kt[[c for c in cols_needed if c in df_kt.columns]]
        else:
            df_kt = pd.DataFrame(columns=['Ngày_Đánh', 'Số_Lô', 'Điểm', 'Vốn', 'Thu_Về', 'Lãi_Lỗ', 'Trạng_Thái'])
        
        if not df_kt.empty:
            df_kt['Số_Lô'] = df_kt['Số_Lô'].astype(str).str.zfill(2)
            # Chuyển đổi kiểu số an toàn
            for col in ['Điểm', 'Vốn', 'Thu_Về', 'Lãi_Lỗ']:
                if col in df_kt.columns:
                    df_kt[col] = pd.to_numeric(df_kt[col].astype(str).replace('', '0'), errors='coerce').fillna(0)
            
        return df_raw, df_kt
    except Exception as e:
        st.error(f"❌ Lỗi đọc dữ liệu Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame()

df, df_ketoan = load_all_data()

# ==========================================
# 2. XỬ LÝ LOGIC TÍNH TOÁN
# ==========================================
def process_logic(df_in):
    day_lists, day_sets, day_strings = [], [], []
    gan_tracker = {str(i).zfill(2): 0 for i in range(100)}
    
    if df_in.empty: return [], [], [], gan_tracker

    for idx, row in df_in.iterrows():
        clean_nums = [n for n in str(row['Danh_Sach_Giai_Full']).split(',') if len(n) >= 2]
        raw = [n[-2:] for n in clean_nums]
        day_lists.append(raw)
        day_sets.append(set(raw))
        day_strings.append("".join(clean_nums))
        
        for i in range(100):
            n_str = str(i).zfill(2)
            if n_str in raw: gan_tracker[n_str] = 0
            else: gan_tracker[n_str] += 1
                
    return day_lists, day_sets, day_strings, gan_tracker

day_lists, day_sets, day_strings, gan_tracker = process_logic(df)

# ==========================================
# 3. GIAO DIỆN NGƯỜI DÙNG
# ==========================================
st.sidebar.title("📊 CHỈ HUY XSMB")
st.sidebar.info(f"Dữ liệu: {len(df)} ngày")

tab1, tab2, tab3 = st.tabs(["🎯 DỰ ĐOÁN & KẾ TOÁN", "🔍 SOI CẦU", "📝 NHẬP LIỆU"])

with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("💡 Gợi ý hôm nay")
        if len(day_strings) >= 5:
            s0 = day_strings[-1]
            preds = set()
            for p1 in range(len(s0)):
                for p2 in range(len(s0)):
                    valid = True
                    for d in range(1, 4):
                        if (len(day_strings) > d+1) and (day_strings[-1-d][p1] + day_strings[-1-d][p2] not in day_sets[-d]):
                            valid = False; break
                    if valid: preds.add(s0[p1] + s0[p2])
            
            if preds: st.success(f"Cặp số tiềm năng: {', '.join(list(preds))}")
            else: st.write("Đang quét cầu...")
        else: st.write("Cần nạp thêm dữ liệu để soi cầu.")
        
    with col2:
        st.subheader("💰 Ghi sổ đầu tư")
        with st.form("form_kt"):
            so = st.text_input("Số lô:", max_chars=2)
            diem = st.number_input("Số điểm:", min_value=1, value=10)
            if st.form_submit_button("Lưu lên Cloud"):
                if len(so) == 2:
                    ws_kt = sheet.worksheet("KeToan")
                    ngay_nay = datetime.now().strftime("%d-%m-%Y")
                    ws_kt.append_row([ngay_nay, so, diem, diem*1000, 0, 0, "⏳ Chờ KQ"])
                    st.cache_data.clear()
                    st.success("✅ Đã ghi sổ!")
                    st.rerun()

    st.divider()
    st.subheader("📊 Bảng lãi lỗ thực tế")
    if not df_ketoan.empty:
        st.dataframe(df_ketoan, hide_index=True)

with tab2:
    st.subheader("🔍 Máy quét vị trí cầu")
    if st.button("Bắt đầu quét nhanh"):
        st.write("Tính năng đang hoạt động dựa trên dữ liệu Cloud...")

with tab3:
    st.subheader("📥 Cập nhật kết quả hằng ngày")
    d_input = st.date_input("Ngày kết quả:", value=datetime.now())
    txt_input = st.text_area("Dán 27 giải:")
    
    if st.button("Đồng bộ lên Cloud"):
        nums = re.findall(r'\d+', txt_input)
        if len(nums) >= 27:
            res_str = "," + ",".join(nums[:27]) + ","
            ws_db = sheet.worksheet("Database")
            ngay_str = d_input.strftime("%d-%m-%Y")
            ws_db.append_row([ngay_str, res_str, "27"])
            st.cache_data.clear()
            st.success(f"✅ Đã lưu ngày {ngay_str}!")
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"Thiếu giải (có {len(nums)}/27)")

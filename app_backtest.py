import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import re
import time
from datetime import datetime

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG & KẾ TỐI CLOUD
# ==========================================
st.set_page_config(page_title="XSMB Quant Cloud", layout="wide")

# Đường dẫn file Google Sheets của bạn
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zd0OcKa3GtEJqoBp6nH7Sr3mZ646oIcKPJ6KPiMJSSE/edit?gid=616470749#gid=616470749"

@st.cache_resource
def get_gspread_client():
    try:
        # Đọc Key từ Secrets với chế độ strict=False để tránh lỗi ký tự đặc biệt
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
    st.info("Hãy kiểm tra xem bạn đã Share quyền 'Editor' cho email của Bot chưa.")
    st.stop()

@st.cache_data(ttl=60) 
def load_all_data():
    # Tải Database
    ws_db = sheet.worksheet("Database")
    df_raw = pd.DataFrame(ws_db.get_all_records())
    if not df_raw.empty:
        df_raw['Ngày'] = df_raw['Ngày'].astype(str)
        df_raw['Date_Obj'] = pd.to_datetime(df_raw['Ngày'], format='%d-%m-%Y', errors='coerce')
        df_raw = df_raw.dropna(subset=['Date_Obj']).sort_values('Date_Obj').reset_index(drop=True)
    
    # Tải Kế toán
    ws_kt = sheet.worksheet("KeToan")
    df_kt = pd.DataFrame(ws_kt.get_all_records())
    if not df_kt.empty:
        df_kt['Số_Lô'] = df_kt['Số_Lô'].astype(str).str.zfill(2)
        
    return df_raw, df_kt

df, df_ketoan = load_all_data()

# ==========================================
# 2. XỬ LÝ LOGIC TÍNH TOÁN
# ==========================================
@st.cache_data(ttl=60)
def process_logic(df_in):
    day_lists, day_sets, day_strings = [], [], []
    gan_tracker = {str(i).zfill(2): 0 for i in range(100)}
    
    for idx, row in df_in.iterrows():
        # Lấy 2 số cuối của các giải
        raw = [n[-2:] for n in str(row['Danh_Sach_Giai_Full']).split(',') if len(n) >= 2]
        day_lists.append(raw)
        day_sets.append(set(raw))
        day_strings.append("".join([n for n in str(row['Danh_Sach_Giai_Full']).split(',') if len(n) >= 2]))
        
        # Cập nhật nhịp gan
        for i in range(100):
            n_str = str(i).zfill(2)
            if n_str in raw: gan_tracker[n_str] = 0
            else: gan_tracker[n_str] += 1
                
    return day_lists, day_sets, day_strings, gan_tracker

day_lists, day_sets, day_strings, gan_tracker = process_logic(df)

# ==========================================
# 3. GIAO DIỆN NGƯỜI DÙNG (TỐI ƯU MOBILE)
# ==========================================
st.sidebar.title("📊 CHỈ HUY XSMB")
mode = st.sidebar.radio("Thiết bị:", ["📱 Điện thoại", "💻 Máy tính"])

tab1, tab2, tab3 = st.tabs(["🎯 DỰ ĐOÁN & KẾ TOÁN", "🔍 SOI CẦU", "📝 NHẬP LIỆU"])

# --- TAB 1: DỰ ĐOÁN ---
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
                    for d in range(1, 4): # Cầu thông 3 ngày
                        if day_strings[-1-d][p1] + day_strings[-1-d][p2] not in day_sets[-d]:
                            valid = False; break
                    if valid: preds.add(s0[p1] + s0[p2])
            
            if preds: st.success(f"Cặp số tiềm năng: {', '.join(list(preds))}")
            else: st.write("Đang chờ tín hiệu cầu mới...")
        
    with col2:
        st.subheader("💰 Ghi sổ đầu tư")
        with st.form("form_kt"):
            so = st.text_input("Số lô (2 số):", max_chars=2)
            diem = st.number_input("Số điểm:", min_value=1, value=10)
            if st.form_submit_button("Lưu lên Cloud"):
                if len(so) == 2 and so.isdigit():
                    ws_kt = sheet.worksheet("KeToan")
                    ngay_nay = datetime.now().strftime("%d-%m-%Y")
                    ws_kt.append_row([ngay_nay, so, diem, diem*1000, 0, 0, "⏳ Chờ KQ"])
                    st.cache_data.clear()
                    st.success("✅ Đã ghi sổ!")
                    st.rerun()
                else: st.error("Nhập sai định dạng số lô.")

# --- TAB 2: SOI CẦU ---
with tab2:
    st.subheader("🔍 Máy quét vị trí cầu")
    ngay_cau = st.slider("Độ dài cầu (ngày):", 1, 7, 3)
    if st.button("Bắt đầu quét"):
        # Logic soi cầu đơn giản
        st.write("Đang quét dữ liệu...")
        # ... (Tự động kế thừa từ logic Tab 1)

# --- TAB 3: NHẬP LIỆU (QUAN TRỌNG NHẤT) ---
with tab3:
    st.subheader("📥 Cập nhật kết quả hằng ngày")
    d_input = st.date_input("Ngày kết quả:", value=datetime.now())
    txt_input = st.text_area("Dán 27 giải (cách nhau bởi dấu phẩy hoặc khoảng trắng):")
    
    if st.button("Đồng bộ lên Cloud"):
        nums = re.findall(r'\d+', txt_input)
        if len(nums) >= 27:
            res_str = "," + ",".join(nums[:27]) + ","
            ws_db = sheet.worksheet("Database")
            ngay_str = d_input.strftime("%d-%m-%Y")
            
            # Kiểm tra xem ngày này đã có chưa để tránh trùng
            cell = ws_db.find(ngay_str)
            if cell: ws_db.delete_rows(cell.row)
            
            ws_db.append_row([ngay_str, res_str, "27"])
            st.cache_data.clear()
            st.success(f"✅ Đã lưu kết quả ngày {ngay_str}!")
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"Chỉ tìm thấy {len(nums)} số. Cần đủ 27 giải.")

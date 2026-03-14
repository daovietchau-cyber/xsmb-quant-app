import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import re
from datetime import datetime, time

# ==========================================
# 1. CẤU HÌNH & PHONG CÁCH (CSS)
# ==========================================
st.set_page_config(page_title="Hệ Thống Chỉ Huy XSMB", layout="wide")

st.markdown("""
    <style>
    .reportview-container .main .block-container { font-size: 22px !important; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    /* Màu sắc đặc trưng cho Chỉ huy */
    .orange-text { color: #FF8C00; font-weight: bold; }
    .blue-text { color: #1E90FF; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1zd0OcKa3GtEJqoBp6nH7Sr3mZ646oIcKPJ6KPiMJSSE/edit?gid=616470749#gid=616470749"

@st.cache_resource
def get_client():
    key_dict = json.loads(st.secrets["gcp_service_account"]["json_key"], strict=False)
    return gspread.authorize(Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]))

@st.cache_data(ttl=30)
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
# 2. BỘ NÃO QUANT & PHÂN LOẠI
# ==========================================
@st.cache_data(ttl=30)
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
        results.append({"Số": num, "Gan": curr_g, "DNA": best_g, "Loại": "🦅 ĐẠI BÀNG" if curr_g == best_g else "🐢 RÙA"})
    return results

suggestions = get_suggestions(df)

# ==========================================
# 3. GIAO DIỆN ĐIỀU HÀNH CHIẾN THUẬT
# ==========================================
now = datetime.now()
is_before_cutoff = now.time() < time(18, 0)

# Khởi tạo trạng thái chọn riêng biệt
if 'selected_nums' not in st.session_state:
    st.session_state.selected_nums = [s['Số'] for s in suggestions]

tab1, tab2 = st.tabs(["🚀 LỆNH TẤN CÔNG", "📥 NHẬP KẾ QUẢ"])

with tab1:
    st.header("🦅 Bảng Điều Phối Lệnh")
    
    # --- CỤM 4 NÚT ĐIỀU KHIỂN BIỆT LẬP ---
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("🦅 Chọn Hết Đ.Bàng"):
        db_nums = [s['Số'] for s in suggestions if "ĐẠI BÀNG" in s['Loại']]
        st.session_state.selected_nums = list(set(st.session_state.selected_nums + db_nums))
        st.rerun()
    if c2.button("🚫 Bỏ Hết Đ.Bàng"):
        st.session_state.selected_nums = [n for n in st.session_state.selected_nums if n not in [s['Số'] for s in suggestions if "ĐẠI BÀNG" in s['Loại']]]
        st.rerun()
    if c3.button("🐢 Chọn Hết Rùa"):
        r_nums = [s['Số'] for s in suggestions if "RÙA" in s['Loại']]
        st.session_state.selected_nums = list(set(st.session_state.selected_nums + r_nums))
        st.rerun()
    if c4.button("🚫 Bỏ Hết Rùa"):
        st.session_state.selected_nums = [n for n in st.session_state.selected_nums if n not in [s['Số'] for s in suggestions if "RÙA" in s['Loại']]]
        st.rerun()

    # Chuẩn bị dữ liệu hiển thị
    display_data = []
    for s in suggestions:
        display_data.append({
            "Chọn": s['Số'] in st.session_state.selected_nums,
            "Số": s['Số'],
            "Loại Chiến Thuật": s['Loại'],
            "Điểm Đề Xuất": 20 if "ĐẠI BÀNG" in s['Loại'] else 10,
            "Trạng thái": f"Gan {s['Gan']} (Đỉnh {s['DNA']})"
        })
    
    if display_data:
        # Bảng chỉnh sửa trực tiếp
        df_display = pd.DataFrame(display_data)
        edited_df = st.data_editor(df_display, use_container_width=True, hide_index=True, key="main_editor")
        
        # Cập nhật lại session_state từ bảng editor
        st.session_state.selected_nums = edited_df[edited_df['Chọn'] == True]['Số'].tolist()
        
        # Tạo lệnh dán Web
        picks = edited_df[edited_df['Chọn'] == True]
        cmd_text = ", ".join([f"{r['Số']}x{r['Điểm Đề Xuất']}" for _, r in picks.iterrows()])
        
        st.markdown("### 📋 Lệnh Copy-Paste cho Web")
        st.code(cmd_text, language="text")

        if st.button("🔥 XÁC NHẬN CHỐT LỆNH LÊN CLOUD", type="primary"):
            if is_before_cutoff:
                ws_kt = get_client().open_by_url(SHEET_URL).worksheet("KeToan")
                for _, r in picks.iterrows():
                    ws_kt.append_row([now.strftime("%d-%m-%Y"), r['Số'], r['Điểm Đề Xuất'], r['Điểm Đề Xuất']*23000, 0, 0, "⏳ Đang đánh"])
                st.success("Đã ghi lịch sử chốt số!")
            else: st.error("Đã qua 18h00 - Lệnh không được ghi nhận.")

with tab2:
    st.subheader("📥 Cập nhật KQXS & Đối soát")
    txt = st.text_area("Dán 27 giải hôm nay:")
    if st.button("Đồng bộ & Tính tiền lãi"):
        nums = re.findall(r'\d+', txt)
        if len(nums) >= 27:
            # Lưu DB
            get_client().open_by_url(SHEET_URL).worksheet("Database").append_row([now.strftime("%d-%m-%Y"), "," + ",".join(nums[:27]) + ",", "27"])
            # Đối soát
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
            st.cache_data.clear(); st.success("Hoàn tất đối soát!"); st.rerun()

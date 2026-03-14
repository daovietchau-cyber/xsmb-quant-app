import streamlit as st
import pandas as pd
import os
import re
import time
from datetime import datetime

# ==========================================
# CẤU HÌNH HỆ THỐNG
# ==========================================
pd.set_option("styler.render.max_elements", 2000000)
st.set_page_config(page_title="Hệ Thống Phân Tích Xổ Số (Quant Edition)", layout="wide")

# ==========================================
# 1. ĐỌC DỮ LIỆU & FILE KẾ TOÁN
# ==========================================
def load_database():
    csv_path = "D:\\xsmb\\database_10nam.csv"
    if not os.path.exists(csv_path): return pd.DataFrame()
    df = pd.read_csv(csv_path, dtype={'Ngày': str})
    df['Date_Obj'] = pd.to_datetime(df['Ngày'], format='%d-%m-%Y', errors='coerce')
    df = df.dropna(subset=['Date_Obj']).sort_values('Date_Obj', ascending=True).reset_index(drop=True)
    return df

df = load_database()

if df.empty:
    st.error("❌ Không tìm thấy dữ liệu. Hãy chạy lệnh tải dữ liệu.")
    st.stop()

ketoan_path = "D:\\xsmb\\so_ke_toan.csv"
if os.path.exists(ketoan_path):
    df_ketoan = pd.read_csv(ketoan_path, dtype={'Ngày_Đánh': str, 'Số_Lô': str})
else:
    df_ketoan = pd.DataFrame(columns=['Ngày_Đánh', 'Số_Lô', 'Điểm', 'Vốn', 'Thu_Về', 'Lãi_Lỗ', 'Trạng_Thái'])

# ==========================================
# 2. ĐỒNG HỒ KIỂM SOÁT
# ==========================================
now = datetime.now()
today_date = now.date()
last_db_date = df['Date_Obj'].max().date()

st.sidebar.markdown("### 📊 TÌNH TRẠNG DỮ LIỆU")
st.sidebar.success(f"**Tổng số ngày:** {len(df)} ngày")
st.sidebar.info(f"**Ngày mới nhất:** {last_db_date.strftime('%d/%m/%Y')}")

if now.hour >= 18 and now.minute >= 30: expected_date = today_date
else: expected_date = today_date - pd.Timedelta(days=1)

# ==========================================
# 3. TIỀN XỬ LÝ DỮ LIỆU (PRE-PROCESSING)
# ==========================================
records = df.to_dict('records')
N_records = len(records)
gan_history = []
gan_tracker = {str(i).zfill(2): 0 for i in range(100)}

day_strings = [] 
day_sets = []    
day_lists = []   
last_seen_date = {str(i).zfill(2): "Chưa có" for i in range(100)}
max_gan = {str(i).zfill(2): 0 for i in range(100)}

matrix_data = []
gap_counts = {str(i).zfill(2): {gap: 0 for gap in range(16)} for i in range(100)}
total_hits = {str(i).zfill(2): 0 for i in range(100)}
last_draw_counts = {}
de_hom_nay = ""

for idx, row in enumerate(records):
    date_str = row['Ngày']
    raw_nums = str(row.get('Danh_Sach_Giai_Full', '')).strip(',').split(',')
    clean_nums = [n for n in raw_nums if len(n) >= 2]
    
    full_str = "".join(clean_nums)
    last_2_list = [n[-2:] for n in clean_nums]
    last_2_set = set(last_2_list)
    
    day_strings.append(full_str)
    day_lists.append(last_2_list)
    day_sets.append(last_2_set)
    
    if idx == N_records - 1:
        de_hom_nay = last_2_list[0] if last_2_list else ""
        for n in last_2_list: last_draw_counts[n] = last_draw_counts.get(n, 0) + 1
            
    day_counts = {str(i).zfill(2): 0 for i in range(100)}
    for n in last_2_list: day_counts[n] += 1
        
    row_dict = {'Ngày': date_str}
    for i in range(100):
        num = str(i).zfill(2)
        c = day_counts[num]
        if c > 0:
            text = f"{c} nháy"
            if idx > 0 and last_seen_date[num] != "Chưa có":
                gap = gan_tracker[num]
                gap_bin = min(gap, 15)
                gap_counts[num][gap_bin] += 1
                total_hits[num] += 1
            if gan_tracker[num] == 0 and idx > 0: text += " (Về lại)"
            if gan_tracker[num] > max_gan[num]: max_gan[num] = gan_tracker[num]
            gan_tracker[num] = 0
            last_seen_date[num] = date_str
        else:
            gan_tracker[num] += 1
            text = f"Gan {gan_tracker[num]}"
        row_dict[num] = text
    matrix_data.append(row_dict)
    gan_history.append(gan_tracker.copy())

matrix_df = pd.DataFrame(matrix_data).iloc[::-1].reset_index(drop=True)
gan_rows = [{"Số Lô": str(i).zfill(2), "Lần chưa về": gan_history[-1][str(i).zfill(2)], "Ngày về gần nhất": last_seen_date[str(i).zfill(2)], "Gan cực đại": max_gan[str(i).zfill(2)]} for i in range(100)]
gan_stats_df = pd.DataFrame(gan_rows).sort_values(by="Lần chưa về", ascending=False).reset_index(drop=True)

# Hàm lấy Gan mạnh nhất (DNA) của 1 con số
def get_best_gan_hientai(num_str):
    if total_hits[num_str] == 0: return -1
    best_g = 0
    max_pct = -1
    for g in range(16):
        pct = gap_counts[num_str][g] / total_hits[num_str]
        if pct > max_pct:
            max_pct = pct
            best_g = g
    return best_g

# ==========================================
# 4. GIAO DIỆN & TABS
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📌 BÁO CÁO", "🛠️ SOI CẦU TỰ ĐỘNG", "📈 MÔ PHỎNG", "🧠 CHUYÊN GIA & KẾ TOÁN", "📝 NHẬP LIỆU"
])

with tab1:
    st.markdown("### 🔥 Báo cáo Lô Gan & Ma Trận")
    col1, col2 = st.columns(2)
    with col1: st.dataframe(gan_stats_df.head(20), hide_index=True)
    with col2: st.dataframe(matrix_df.head(30).set_index('Ngày').style.map(lambda v: 'color: #FFD700; font-weight: bold;' if 'nháy' in str(v) else ('color: #FFFFFF; background-color: rgba(255, 0, 0, 0.4);' if 'Gan' in str(v) else '')), height=400)

with tab2:
    st.markdown("### 🛠️ CỖ MÁY SOI CẦU TỰ ĐỘNG")
    bridge_days = st.slider("Cầu chạy (thông) bao nhiêu ngày?", 1, 7, 3)
    if st.button("📡 QUÉT CẦU CHO NGÀY MAI"):
        with st.spinner("Đang quét 11.449 vị trí..."):
            active_bridges = []
            s0 = day_strings[-1]
            if len(s0) >= 100:
                for p1 in range(len(s0)):
                    for p2 in range(len(s0)):
                        is_valid = True
                        for d in range(1, bridge_days + 1):
                            idx_past = N_records - 1 - d
                            if idx_past < 0 or p1 >= len(day_strings[idx_past]) or p2 >= len(day_strings[idx_past]):
                                is_valid = False; break
                            if day_strings[idx_past][p1] + day_strings[idx_past][p2] not in day_sets[idx_past + 1]:
                                is_valid = False; break
                        if is_valid: active_bridges.append(s0[p1] + s0[p2])
            if active_bridges: st.success(f"Dự đoán có {len(set(active_bridges))} số ưu tú: {', '.join(set(active_bridges))}")
            else: st.warning("Không tìm thấy Cầu hợp lệ.")

with tab3:
    st.markdown("### 📈 MÔ PHỎNG ĐỊNH LƯỢNG (Tab này giữ nguyên thuật toán cũ)")
    st.info("Sử dụng để Backtest chiến lược trong quá khứ.")

# ----------------- TAB 8: CHUYÊN GIA & KẾ TOÁN -----------------
with tab4:
    st.markdown("### 🧠 TỔNG ĐÀI CHỈ HUY ĐẦU TƯ (DASHBOARD)")
    
    col_c1, col_c2 = st.columns([1.2, 1])
    
    with col_c1:
        st.markdown("#### 📅 BÁO CÁO ĐỀ XUẤT HÔM NAY")
        st.info("Hệ thống lọc tự động: Cầu thông 3 ngày ➡️ Rơi vào vùng Gan Vàng (3-8 hoặc 13-17) ➡️ Đối chiếu DNA.")
        
        # Chạy thuật toán lọc cho ngày mai
        s0 = day_strings[-1]
        predicted_nums = set()
        if len(s0) >= 100:
            for p1 in range(len(s0)):
                for p2 in range(len(s0)):
                    is_valid = True
                    for d in range(1, 4): # Soi cầu 3 ngày
                        idx_past = N_records - 1 - d
                        if idx_past < 0 or p1 >= len(day_strings[idx_past]) or p2 >= len(day_strings[idx_past]):
                            is_valid = False; break
                        if day_strings[idx_past][p1] + day_strings[idx_past][p2] not in day_sets[idx_past + 1]:
                            is_valid = False; break
                    if is_valid: predicted_nums.add(s0[p1] + s0[p2])
        
        dai_bang_list = []
        rua_list = []
        loai_list = []
        
        for num in predicted_nums:
            curr_gan = gan_history[-1][num]
            best_gan = get_best_gan_hientai(num)
            
            if (3 <= curr_gan <= 8) or (13 <= curr_gan <= 17):
                if curr_gan == best_gan: dai_bang_list.append((num, curr_gan, best_gan))
                else: rua_list.append((num, curr_gan, best_gan))
            else:
                loai_list.append((num, curr_gan))
                
        if dai_bang_list:
            st.error("🔥 **DANH MỤC 1: TẤN CÔNG ĐẠI BÀNG (Độ tin cậy RẤT CAO)**")
            for item in dai_bang_list:
                st.write(f"- **Lô {item[0]}** | Đang Gan {item[1]} ngày. Trùng khớp 100% DNA đỉnh nổ lịch sử. Đề xuất: **Vào tiền Nhịp mạnh**.")
        else: st.write("Không có mã Đại Bàng nào thỏa mãn trong hôm nay.")
            
        if rua_list:
            st.success("🐢 **DANH MỤC 2: RÙA BỌC THÉP (Thăm dò)**")
            for item in rua_list:
                st.write(f"- **Lô {item[0]}** | Đang Gan {item[1]} ngày (Đỉnh lịch sử là Gan {item[2]}). Đề xuất: **Vào tiền Phòng thủ**.")
                
        if loai_list:
            with st.expander("🚫 Xem các mã bị hệ thống TỪ CHỐI (Rủi ro cao)"):
                for item in loai_list:
                    st.write(f"- Lô {item[0]} (Đang Gan {item[1]} ngày) - Rơi vào vùng tỷ lệ nổ chết lâm sàng. Cấm vào tiền.")
    
    with col_c2:
        st.markdown("#### 💼 SỔ KẾ TOÁN THỰC CHIẾN")
        
        with st.form("ke_toan_form"):
            ngay_danh_date = st.date_input("Ngày đầu tư:", value=expected_date)
            ngay_danh_str = ngay_danh_date.strftime("%d-%m-%Y")
            so_danh = st.text_input("Lô đã đánh (Ví dụ: 68):", max_chars=2)
            diem_danh = st.number_input("Số điểm (1đ = 1.000đ):", min_value=1, value=10, step=5)
            
            if st.form_submit_button("💾 LƯU LỆNH VÀO SỔ"):
                if so_danh.isdigit() and len(so_danh) == 2:
                    von_bo_ra = diem_danh * 1000
                    new_row = pd.DataFrame([{
                        'Ngày_Đánh': ngay_danh_str, 'Số_Lô': so_danh, 'Điểm': diem_danh, 
                        'Vốn': von_bo_ra, 'Thu_Về': 0, 'Lãi_Lỗ': 0, 'Trạng_Thái': '⏳ Chờ KQ'
                    }])
                    global df_ketoan
                    df_ketoan = pd.concat([df_ketoan, new_row], ignore_index=True)
                    df_ketoan.to_csv(ketoan_path, index=False, encoding='utf-8-sig')
                    st.success("✅ Đã ghi sổ thành công!")
                    time.sleep(1); st.rerun()
                else: st.error("Vui lòng nhập đúng 2 số.")
                
        st.markdown("**Hạch toán tự động (Cập nhật khi có kết quả bảng KQXS)**")
        # Logic đối soát tự động Kế toán với DB
        if not df_ketoan.empty:
            for i, row in df_ketoan.iterrows():
                nd = row['Ngày_Đánh']
                if nd in df['Ngày'].values:
                    sl = row['Số_Lô']
                    diem = row['Điểm']
                    # Tìm giải của ngày đó
                    idx_db = df.index[df['Ngày'] == nd][0]
                    raw = str(df.at[idx_db, 'Danh_Sach_Giai_Full']).strip(',').split(',')
                    l2 = [n[-2:] for n in raw if len(n)>=2]
                    hits = l2.count(sl)
                    
                    von = row['Vốn']
                    thu_ve = hits * diem * 3660
                    lai_lo = thu_ve - von
                    
                    df_ketoan.at[i, 'Thu_Về'] = thu_ve
                    df_ketoan.at[i, 'Lãi_Lỗ'] = lai_lo
                    if hits > 0: df_ketoan.at[i, 'Trạng_Thái'] = f"✅ Thắng ({hits} nháy)"
                    else: df_ketoan.at[i, 'Trạng_Thái'] = "❌ Thua"
            
            # Lưu lại trạng thái đã update
            df_ketoan.to_csv(ketoan_path, index=False, encoding='utf-8-sig')
            
            tong_von = df_ketoan['Vốn'].sum()
            tong_thu = df_ketoan['Thu_Về'].sum()
            tong_lai = df_ketoan['Lãi_Lỗ'].sum()
            
            st.metric("TỔNG LỢI NHUẬN THỰC TẾ", f"{tong_lai:,.0f} đ", delta=int(tong_lai))
            
            def color_status(val):
                if '✅' in str(val): return 'color: #00FF00; font-weight: bold;'
                if '❌' in str(val): return 'color: #FF4B4B;'
                return 'color: #FFD700;'
            
            st.dataframe(df_ketoan.style.applymap(color_status, subset=['Trạng_Thái']).format({
                "Vốn": "{:,.0f}", "Thu_Về": "{:,.0f}", "Lãi_Lỗ": "{:,.0f}"
            }), hide_index=True)
            
            if st.button("🗑️ Xóa toàn bộ sổ"):
                os.remove(ketoan_path)
                st.rerun()

# ----------------- TAB 5: NHẬP LIỆU THỦ CÔNG -----------------
with tab5:
    st.markdown("### 📝 BẢNG CẬP NHẬT KẾT QUẢ MỚI")
    ngay_moi_date = st.date_input("📅 Chọn ngày:", value=expected_date)
    ngay_str = ngay_moi_date.strftime("%d-%m-%Y")
    with st.form("board_input_form"):
        quick_paste = st.text_area("HỐ ĐEN (Dán 27 số):", height=100)
        if st.form_submit_button("💾 CHỐT KẾT QUẢ MỚI"):
            clean_inputs = [re.sub(r'\D', '', str(x)) for x in re.split(r'[\s,]+', quick_paste) if re.sub(r'\D', '', str(x))]
            if len(clean_inputs) == 27:
                csv_path = "D:\\xsmb\\database_10nam.csv"
                db_file = pd.read_csv(csv_path, dtype={'Ngày': str})
                db_file = db_file[db_file['Ngày'] != ngay_str] 
                db_file = pd.concat([db_file, pd.DataFrame([{"Ngày": ngay_str, "Danh_Sach_Giai_Full": "," + ",".join(clean_inputs) + ",", "So_Giai": "27"}])], ignore_index=True)
                db_file['Date_Obj'] = pd.to_datetime(db_file['Ngày'], format='%d-%m-%Y')
                db_file = db_file.sort_values(by='Date_Obj', ascending=False).drop(columns=['Date_Obj'])
                db_file.to_csv(csv_path, index=False, encoding='utf-8')
                st.success("✅ Thành công!")
                time.sleep(1)
                st.rerun()
            else: st.error(f"❌ Thiếu số. Mới có {len(clean_inputs)}/27")
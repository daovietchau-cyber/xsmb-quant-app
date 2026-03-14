@st.cache_resource
def get_gspread_client():
    try:
        # Đọc trực tiếp từ Secrets
        key_dict = json.loads(st.secrets["gcp_service_account"]["json_key"], strict=False)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Lỗi cấu hình Cloud: {e}")
        st.stop()

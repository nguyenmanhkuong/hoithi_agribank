import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.api_core import exceptions

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Phân Tích Báo Cáo Tài Chính",
    layout="wide"
)

# --- PHẦN MỚI: GIAO DIỆN NHẬP API KEY ---
st.sidebar.title("Cấu hình API Key 🔑")
api_key_input = st.sidebar.text_input(
    "Nhập Google API Key của bạn",
    type="password",
    help="Lấy key tại Google AI Studio. Key này sẽ được ưu tiên sử dụng."
)

# Logic xác định API key để sử dụng
final_api_key = None
# Ưu tiên key người dùng nhập vào
if api_key_input:
    final_api_key = api_key_input
    st.sidebar.success("Đang sử dụng API Key bạn vừa nhập.", icon="✅")
# Nếu không, dùng key từ secrets
elif "GOOGLE_API_KEY" in st.secrets:
    final_api_key = st.secrets["GOOGLE_API_KEY"]
    st.sidebar.info("Đang sử dụng API Key từ Streamlit Secrets.", icon="☁️")

# Cấu hình genai và khởi tạo model nếu có key
if final_api_key:
    try:
        genai.configure(api_key=final_api_key)
        model_analyzer = genai.GenerativeModel('gemini-1.5-flash')
        model_chat = genai.GenerativeModel('gemini-pro')
    except Exception as e:
        st.error(f"Lỗi cấu hình API Key: {e}. Vui lòng kiểm tra lại key của bạn.")
        st.stop()
else:
    # Dừng ứng dụng nếu không có key nào
    st.error("Vui lòng nhập Google API Key vào thanh bên hoặc cấu hình trong Streamlit Secrets để bắt đầu.")
    st.stop()

# --- Các phần còn lại của ứng dụng được giữ nguyên ---

st.title("Ứng dụng Phân Tích Báo Cáo Tài Chính 📊")

# --- Hàm tính toán chính (Sử dụng Caching để Tối ưu hiệu suất) ---
@st.cache_data
def process_financial_data(df):
    """Thực hiện các phép tính Tăng trưởng và Tỷ trọng."""
    
    # Đảm bảo các giá trị là số để tính toán
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 1. Tính Tốc độ Tăng trưởng
    df['Tốc độ tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    # 2. Tính Tỷ trọng theo Tổng Tài sản
    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]
    
    if tong_tai_san_row.empty:
        raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TÀI SẢN'.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0]
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0]
    
    divisor_N_1 = tong_tai_san_N_1 if tong_tai_san_N_1 != 0 else 1e-9
    divisor_N = tong_tai_san_N if tong_tai_san_N != 0 else 1e-9

    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / divisor_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / divisor_N) * 100
    
    return df

# --- Hàm gọi API Gemini (ĐÃ TÁI CẤU TRÚC) ---
def get_ai_analysis(data_for_ai):
    """Gửi dữ liệu phân tích đến Gemini API và nhận nhận xét."""
    try:
        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính chuyên nghiệp. Dựa trên các chỉ số tài chính sau, hãy đưa ra một nhận xét khách quan, ngắn gọn (khoảng 3-4 đoạn) về tình hình tài chính của doanh nghiệp. Đánh giá tập trung vào tốc độ tăng trưởng, thay đổi cơ cấu tài sản và khả năng thanh toán hiện hành.
        
        Dữ liệu thô và chỉ số:
        {data_for_ai}
        """
        response = model_analyzer.generate_content(prompt)
        return response.text

    except exceptions.GoogleAPICallError as e:
        return f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}"
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"


# --- Chức năng 1: Tải File ---
uploaded_file = st.file_uploader(
    "1. Tải file Excel Báo cáo Tài chính (Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau']
        df_processed = process_financial_data(df_raw.copy())

        if df_processed is not None:
            
            st.subheader("2. Tốc độ Tăng trưởng & 3. Tỷ trọng Cơ cấu Tài sản")
            st.dataframe(df_processed.style.format({
                'Năm trước': '{:,.0f}', 'Năm sau': '{:,.0f}',
                'Tốc độ tăng trưởng (%)': '{:.2f}%',
                'Tỷ trọng Năm trước (%)': '{:.2f}%',
                'Tỷ trọng Năm sau (%)': '{:.2f}%'
            }), use_container_width=True)
            
            st.subheader("4. Các Chỉ số Tài chính Cơ bản")
            try:
                tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]
                no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                thanh_toan_hien_hanh_N = tsnh_n / no_ngan_han_N if no_ngan_han_N != 0 else 0
                thanh_toan_hien_hanh_N_1 = tsnh_n_1 / no_ngan_han_N_1 if no_ngan_han_N_1 != 0 else 0
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(label="Chỉ số Thanh toán Hiện hành (Năm trước)", value=f"{thanh_toan_hien_hanh_N_1:.2f} lần")
                with col2:
                    st.metric(label="Chỉ số Thanh toán Hiện hành (Năm sau)", value=f"{thanh_toan_hien_hanh_N:.2f} lần", delta=f"{thanh_toan_hien_hanh_N - thanh_toan_hien_hanh_N_1:.2f}")
            except (IndexError, ZeroDivisionError):
                st.warning("Thiếu chỉ tiêu hoặc có giá trị 0 ('TÀI SẢN NGẮN HẠN', 'NỢ NGẮN HẠN') để tính chỉ số.")
                thanh_toan_hien_hanh_N, thanh_toan_hien_hanh_N_1 = "N/A", "N/A"
            
            st.subheader("5. Nhận xét Tình hình Tài chính (AI)")
            
            data_for_ai = pd.DataFrame({
                'Chỉ tiêu': ['Toàn bộ Bảng phân tích', 'Tăng trưởng TSNH (%)', 'Thanh toán hiện hành (N-1)', 'Thanh toán hiện hành (N)'],
                'Giá trị': [
                    df_processed.to_markdown(index=False),
                    f"{df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Tốc độ tăng trưởng (%)'].iloc[0]:.2f}%",
                    f"{thanh_toan_hien_hanh_N_1}", f"{thanh_toan_hien_hanh_N}"
                ]
            }).to_markdown(index=False)

            if st.button("Yêu cầu AI Phân tích"):
                with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                    ai_result = get_ai_analysis(data_for_ai)
                    st.markdown("**Kết quả Phân tích từ Gemini AI:**")
                    st.info(ai_result)

    except ValueError as ve:
        st.error(f"Lỗi cấu trúc dữ liệu: {ve}")
    except Exception as e:
        st.error(f"Có lỗi xảy ra khi đọc hoặc xử lý file: {e}. Vui lòng kiểm tra định dạng file.")
else:
    st.info("Vui lòng tải lên file Excel để bắt đầu phân tích.")

# ==============================================================================
# --- KHUNG CHAT HỎI ĐÁP VỚI GEMINI ---
# ==============================================================================

st.divider() 
st.header("Hỏi đáp thêm với Trợ lý AI 💬")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Bạn muốn hỏi gì thêm về tài chính hoặc các chủ đề khác?"}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Nhập câu hỏi của bạn..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        try:
            response_stream = model_chat.generate_content(prompt, stream=True)
            for chunk in response_stream:
                full_response += chunk.text
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        except Exception as e:
            full_response = f"Xin lỗi, đã có lỗi xảy ra: {e}"
            message_placeholder.markdown(full_response)
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})


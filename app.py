import streamlit as st
import gspread
import pandas as pd
import datetime
import plotly.express as px

# Sahifa sozlamalari
st.set_page_config(page_title="Asaka Motors Supply Chain CRM", layout="wide", page_icon="🏭")

# ==================== TIZIMGA KIRISH (AUTHENTICATION WITH AUTO-RELOAD) ====================
# Brauzer yangilanganda (F5) login chiqib ketmasligi uchun URL parametrlaridan foydalanamiz
if "logged_in" not in st.session_state:
    if "user" in st.query_params and "role" in st.query_params:
        st.session_state.logged_in = True
        st.session_state.username = st.query_params["user"]
        st.session_state.role = st.query_params["role"]
    else:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""

def login_user(user, pwd):
    try:
        users_db = st.secrets["users"]
        if user in users_db:
            user_info = users_db[user]
            if user_info["password"] == pwd:
                st.session_state.logged_in = True
                st.session_state.username = user
                st.session_state.role = user_info["role"]
                
                # F5 uchun parametrlarni saqlash
                st.query_params["user"] = user
                st.query_params["role"] = user_info["role"]
                
                st.success("Tizimga muvaffaqiyatli kirdingiz!")
                st.rerun()
            else:
                st.error("Parol xato.")
        else:
            st.error("Bunday foydalanuvchi topilmadi.")
    except Exception as e:
        st.error("Xavfsizlik sozlamalarida foydalanuvchilar ro'yxati topilmadi.")

# Agar tizimga kirmagan bo'lsa, login oynasini ko'rsatish
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🏭 ASAKA MOTORS CRM</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Tizimga kirish uchun login va parolingizni kiriting.</p>", unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    with col_l2:
        with st.form("login_form"):
            input_user = st.text_input("Foydalanuvchi nomi (Username)")
            input_pwd = st.text_input("Parol", type="password")
            btn_login = st.form_submit_button("Kirish")
            if btn_login:
                login_user(input_user, input_pwd)
    st.stop()

# Yon panelda foydalanuvchi ma'lumotlari va chiqish tugmasi
st.sidebar.markdown(f"👤 **Foydalanuvchi:** `{st.session_state.username}`")
st.sidebar.markdown(f"🔑 **Rol:** `{st.session_state.role.upper()}`")
if st.sidebar.button("🔴 Tizimdan Chiqish"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.query_params.clear() # Chiqishda URL parametrlarini tozalash
    st.rerun()

# ==================== ASOSIY BAZA ULANISHLARI ====================
@st.cache_resource
def get_gspread_client():
    creds = st.secrets["gcp_service_account"]
    gc = gspread.service_account_from_dict(creds)
    return gc

try:
    gc = get_gspread_client()
    sh = gc.open("Asaka_Motors")
except Exception as e:
    st.error(f"Google Sheets bilan bog'lanishda xatolik yuz berdi. Iltimos Secrets sozlamalarini tekshiring: {e}")
    st.stop()

# Ustunlar nomlari
COLS_SHARTNOMALAR = ["Shartnoma ID", "Yetkazib beruvchi", "Sana", "Jami Summa", "Status"]
COLS_KOMPLEKTLAR = ["Konteyner / Partiya ID", "Shartnoma ID", "Model", "Optsiya", "Komplektlar Soni", "Hozirgi Joylashuv", "ETA (Kelish sanasi)", "Kritik Holat"]
COLS_ISHLAB_CHIQARISH = ["Liniya ID", "Konteyner / Partiya ID", "Model", "Optsiya", "Yig'ilayotgan Soni", "Liniyaga Chiqqan Sana", "Tayyor Bo'lgan Soni", "Tayyor Bo'lgan Sana"]
COLS_REJA = ["Reja ID", "Model", "Optsiya", "Rejalashtirilgan Soni", "Muddati", "Status"]

def load_data(sheet_name, expected_cols):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        norm_expected = [c.replace("ʻ", "'").replace("’", "'").replace("`", "'") for c in expected_cols]
        if not data:
            return pd.DataFrame(columns=norm_expected)
        df = pd.DataFrame(data)
        df.columns = df.columns.astype(str).str.replace("ʻ", "'").str.replace("’", "'").str.replace("`", "'")
        return df
    except Exception as e:
        norm_expected = [c.replace("ʻ", "'").replace("’", "'").replace("`", "'") for c in expected_cols]
        return pd.DataFrame(columns=norm_expected)

def append_row(sheet_name, row_data):
    worksheet = sh.worksheet(sheet_name)
    worksheet.append_row(row_data)

# Ma'lumotlarni yuklash
df_shartnomalar = load_data("Shartnomalar", COLS_SHARTNOMALAR)
df_komplektlar = load_data("Komplektlar", COLS_KOMPLEKTLAR)
df_ishlab_chiqarish = load_data("Ishlab_Chiqarish", COLS_ISHLAB_CHIQARISH)
df_reja = load_data("Reja", COLS_REJA)

# ==================== DYNAMIC MENYULAR (TABS) ====================
role = st.session_state.role
tabs_list = ["📈 Boshqaruv Paneli (Dashboard)"]

# ADMIN uchun barcha tablar ochiladi
if role == "admin":
    tabs_list += ["📅 Ishlab Chiqarish Rejasi", "📝 Import Shartnomalari", "🚚 Komplektlar & Logistika", "🏭 Ishlab Chiqarish Liniyasi"]
elif role == "logistics":
    tabs_list += ["🚚 Komplektlar & Logistika"]
elif role == "production":
    tabs_list += ["📅 Ishlab Chiqarish Rejasi", "🏭 Ishlab Chiqarish Liniyasi"]

created_tabs = st.tabs(tabs_list)

# ==================== TABLARNING ICHKI KODLARI ====================
for index, tab_name in enumerate(tabs_list):
    with created_tabs[index]:
        
        # 1. DASHBOARD KODI
        if "Boshqaruv Paneli" in tab_name:
            st.header("Tezkor Ko'rsatkichlar")
            total_shartnoma = len(df_shartnomalar)
            
            try:
                yolda_soni = df_komplektlar[df_komplektlar["Hozirgi Joylashuv"].isin(["Koreya porti", "Xitoy porti", "Yoʻlda", "Bojxonada"])]["Komplektlar Soni"].astype(int).sum()
            except:
                yolda_soni = 0
                
            ombor_soni = 0
            if not df_komplektlar.empty:
                arrived_containers = df_komplektlar[df_komplektlar["Hozirgi Joylashuv"].isin(["KD Omborda", "Ishlab chiqarish liniyasida"])]
                for idx, row in arrived_containers.iterrows():
                    cid = row["Konteyner / Partiya ID"]
                    orig_qty = int(row["Komplektlar Soni"])
                    sent_qty = df_ishlab_chiqarish[df_ishlab_chiqarish["Konteyner / Partiya ID"] == cid]["Yig'ilayotgan Soni"].astype(int).sum() if not df_ishlab_chiqarish.empty else 0
                    rem_qty = orig_qty - sent_qty
                    if rem_qty > 0:
                        ombor_soni += rem_qty
                
            try:
                yig_soni = df_ishlab_chiqarish["Yig'ilayotgan Soni"].astype(int).sum() if not df_ishlab_chiqarish.empty else 0
                tayyor_soni = df_ishlab_chiqarish["Tayyor Bo'lgan Soni"].astype(int).sum() if not df_ishlab_chiqarish.empty else 0
                liniya_soni = yig_soni - tayyor_soni
            except:
                liniya_soni, tayyor_soni = 0, 0

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Jami Shartnomalar", f"{total_shartnoma} ta")
            col2.metric("Yo'ldagi Komplektlar (Tranzit)", f"{yolda_soni} ta")
            col3.metric("KD Ombordagi Qoldiq", f"{ombor_soni} ta")
            col4.metric("Liniyadagi (Yig'ishda)", f"{liniya_soni} ta")
            col5.metric("Tayyor Bo'lgan Mashinalar", f"{tayyor_soni} ta")

            st.markdown("---")
            col_chart, col_alerts = st.columns([2, 1])
            
            with col_chart:
                st.subheader("Modellar bo'yicha komplektlar taqsimoti")
                if not df_komplektlar.empty:
                    try:
                        fig = px.bar(df_komplektlar, x="Model", y="Komplektlar Soni", color="Hozirgi Joylashuv", barmode="group")
                        st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.info("Grafik uchun ma'lumot yetarli emas.")
                else:
                    st.info("Hozircha komplektlar kiritilmagan.")

            with col_alerts:
                st.subheader("🚨 Grafik Tahlil (Kritik Holatlar)")
                alerts_triggered = False
                
                # REJA VA TA'MINOT SOLISHTIRISH (SCM GAP ANALYSIS)
                if not df_reja.empty:
                    active_plans = df_reja[df_reja["Status"].isin(["Kutilmoqda", "Bajarilmoqda"])]
                    for p_idx, plan in active_plans.iterrows():
                        p_model = plan["Model"]
                        p_opt = plan["Optsiya"]
                        p_qty = int(plan["Rejalashtirilgan Soni"])
                        p_date_str = str(plan["Muddati"])
                        
                        wh_qty_model = 0
                        if not df_komplektlar.empty:
                            # 196-qator xatoligini bartaraf qilish uchun 2 bosqichli toza filtr
                            m_containers = df_komplektlar[(df_komplektlar["Model"] == p_model) & (df_komplektlar["Optsiya"] == p_opt)]
                            m_containers = m_containers[m_containers["Hozirgi Joylashuv"].isin(["KD Omborda", "Ishlab chiqarish liniyasida"])]
                            
                            for m_idx, m_row in m_containers.iterrows():
                                cid = m_row["Konteyner / Partiya ID"]
                                orig = int(m_row["Komplektlar Soni"])
                                sent = df_ishlab_chiqarish[df_ishlab_chiqarish["Konteyner / Partiya ID"] == cid]["Yig'ilayotgan Soni"].astype(int).sum() if not df_ishlab_chiqarish.empty else 0
                                wh_qty_model += max(0, orig - sent)
                        
                        transit_qty_model = 0
                        transit_before_plan = 0
                        transit_delayed = []
                        
                        if not df_komplektlar.empty:
                            t_rows = df_komplektlar[(df_komplektlar["Model"] == p_model) & (df_komplektlar["Optsiya"] == p_opt) & (df_komplektlar["Hozirgi Joylashuv"].isin(["Koreya porti", "Xitoy porti", "Yoʻlda", "Bojxonada"]))]

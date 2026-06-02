import streamlit as st
import gspread
import pandas as pd
import datetime
import plotly.express as px

# Sahifa sozlamalari
st.set_page_config(page_title="Asaka Motors Supply Chain CRM", layout="wide", page_icon="🏭")

# Sarlavha
st.title("🏭 ASAKA MOTORS — Supply Chain Monitoring & CRM")
st.markdown("Mashina komplektlari (KD), logistika va ishlab chiqarishni nazorat qilish tizimi.")

# Google Sheets ulanishi
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

# Ustunlar nomlari (Standart apostrof bilan)
COLS_SHARTNOMALAR = ["Shartnoma ID", "Yetkazib beruvchi", "Sana", "Jami Summa", "Status"]
COLS_KOMPLEKTLAR = ["Konteyner / Partiya ID", "Shartnoma ID", "Model", "Optsiya", "Komplektlar Soni", "Hozirgi Joylashuv", "ETA (Kelish sanasi)", "Kritik Holat"]
COLS_ISHLAB_CHIQARISH = ["Liniya ID", "Konteyner / Partiya ID", "Model", "Optsiya", "Yig'ilayotgan Soni", "Liniyaga Chiqqan Sana", "Tayyor Bo'lgan Soni", "Tayyor Bo'lgan Sana"]

# Ma'lumotlarni yuklash funksiyasi (Apostroflarni avtomatik tekislovchi)
def load_data(sheet_name, expected_cols):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        norm_expected = [c.replace("ʻ", "'").replace("’", "'").replace("`", "'") for c in expected_cols]
        
        if not data:
            return pd.DataFrame(columns=norm_expected)
            
        df = pd.DataFrame(data)
        # Ustunlardagi har qanday o'zbekcha apostrof belgilarini standart "'" belgisiga o'tkazish
        df.columns = df.columns.astype(str).str.replace("ʻ", "'").str.replace("’", "'").str.replace("`", "'")
        return df
    except Exception as e:
        norm_expected = [c.replace("ʻ", "'").replace("’", "'").replace("`", "'") for c in expected_cols]
        return pd.DataFrame(columns=norm_expected)

# Qator qo'shish funksiyasi
def append_row(sheet_name, row_data):
    worksheet = sh.worksheet(sheet_name)
    worksheet.append_row(row_data)

# Ma'lumotlarni yangilash
df_shartnomalar = load_data("Shartnomalar", COLS_SHARTNOMALAR)
df_komplektlar = load_data("Komplektlar", COLS_KOMPLEKTLAR)
df_ishlab_chiqarish = load_data("Ishlab_Chiqarish", COLS_ISHLAB_CHIQARISH)

# Tizimdagi Tablar (Menyular)
tab_dash, tab_shartnoma, tab_komplekt, tab_ishlab = st.tabs([
    "📈 Boshqaruv Paneli (Dashboard)", 
    "📝 Import Shartnomalari", 
    "🚚 Komplektlar & Logistika", 
    "🏭 Ishlab Chiqarish Liniyasi"
])

# ==================== TAB 1: DASHBOARD ====================
with tab_dash:
    st.header("Tezkor Ko'rsatkichlar")
    
    # Umumiy hisob-kitoblar
    total_shartnoma = len(df_shartnomalar)
    
    # Komplektlar holati
    try:
        yolda_soni = df_komplektlar[df_komplektlar["Hozirgi Joylashuv"].isin(["Koreya porti", "Xitoy porti", "Yoʻlda", "Bojxonada"])]["Komplektlar Soni"].astype(int).sum()
        ombor_soni = df_komplektlar[df_komplektlar["Hozirgi Joylashuv"] == "KD Omborda"]["Komplektlar Soni"].astype(int).sum()
    except:
        yolda_soni, ombor_soni = 0, 0
        
    try:
        # Liniyadagi = Jami yig'ilayotgan soni - Jami tayyor bo'lgan soni
        yig_soni = df_ishlab_chiqarish["Yig'ilayotgan Soni"].astype(int).sum() if not df_ishlab_chiqarish.empty else 0
        tayyor_soni = df_ishlab_chiqarish["Tayyor Bo'lgan Soni"].astype(int).sum() if not df_ishlab_chiqarish.empty else 0
        liniya_soni = yig_soni - tayyor_soni
    except Exception as e:
        liniya_soni, tayyor_soni = 0, 0

    # Metrikalar bloki
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Jami Shartnomalar", f"{total_shartnoma} ta")
    col2.metric("Yo'ldagi Komplektlar (Tranzit)", f"{yolda_soni} ta", delta_color="off")
    col3.metric("KD Ombordagi Qoldiq", f"{ombor_soni} ta")
    col4.metric("Liniyadagi (Yig'ishda)", f"{liniya_soni} ta")
    col5.metric("Tayyor Bo'lgan Mashinalar", f"{tayyor_soni} ta")

    st.markdown("---")

    col_chart, col_alerts = st.columns([2, 1])
    
    with col_chart:
        st.subheader("Modellar bo'yicha komplektlar taqsimoti")
        if not df_komplektlar.empty:
            try:
                fig = px.bar(df_komplektlar, x="Model", y="Komplektlar Soni", color="Hozirgi Joylashuv", 
                             title="Modellar va Statuslar", barmode="group")
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.info("Grafik chizish uchun yetarli ma'lumot yo'q.")
        else:
            st.info("Hozircha komplektlar kiritilmagan.")

    with col_alerts:
        st.subheader("🚨 Kritik Holatlar")
        if not df_komplektlar.empty:
            kritik_df = df_komplektlar[df_komplektlar["Kritik Holat"] == "Ha"]
            if not kritik_df.empty:
                for idx, row in kritik_df.iterrows():
                    st.error(f"⚠️ **Konteyner:** {row['Konteyner / Partiya ID']} ({row['Model']} {row['Optsiya']}) \n\n"
                             f"**Joylashuvi:** {row['Hozirgi Joylashuv']} | **Soni:** {row['Komplektlar Soni']} ta. \n\n"
                             f"Tezkor ta'minot talab etiladi!")
            else:
                st.success("Hozircha hech qanday kritik holat aniqlanmadi. Ta'minot zanjiri barqaror.")
        else:
            st.success("Ma'lumotlar mavjud emas.")

# ==================== TAB 2: IMPORT SHARTNOMALARI ====================
with tab_shartnoma:
    st.header("Import Shartnomalari")
    st.dataframe(df_shartnomalar, use_container_width=True)

    with st.expander("➕ Yangi Import Shartnomasini Kiritish"):
        with st.form("shartnoma_form", clear_on_submit=True):
            sh_id = st.text_input("Shartnoma ID (Masalan: Contract-2026-05)")
            sh_model = st.text_input("Model (Masalan: Onix, Tracker)")
            sh_opt = st.text_input("Optsiya (Masalan: Premier, Redline)")
            sh_soni = st.number_input("Komplektlar Soni", min_value=1, step=1)
            sh_date = st.date_input("Plan qilingan kelish sanasi")
            sh_status = st.selectbox("Status", ["Imzolangan", "To'lov qilingan", "Yopilgan"])
            
            submit_sh = st.form_submit_button("Shartnomani Saqlash")
            if submit_sh:
                if sh_id and sh_model:
                    append_row("Shartnomalar", [sh_id, f"{sh_model} ({sh_opt})", str(sh_date), int(sh_soni), sh_status])
                    st.success("Yangi shartnoma muvaffaqiyatli kiritildi! Sahifani yangilang.")
                else:
                    st.error("Iltimos, Shartnoma ID va Modelni kiriting.")

# ==================== TAB 3: KOMPLEKTLAR & LOGISTIKA ====================
with tab_komplekt:
    st.header("Tranzitdagi va Ombordagi Komplektlar")
    st.dataframe(df_komplektlar, use_container_width=True)

    col_add, col_update = st.columns(2)

    with col_add:
        with st.expander("🚚 Yangi Konteyner / Partiya kiritish"):
            with st.form("komplekt_form", clear_on_submit=True):
                kont_id = st.text_input("Konteyner / Partiya ID (Masalan: OOCU-1234567)")
                sh_list = df_shartnomalar["Shartnoma ID"].tolist() if not df_shartnomalar.empty else ["Shartnoma yo'q"]
                kont_sh = st.selectbox("Qaysi Shartnomaga tegishli?", sh_list)
                kont_model = st.text_input("Model (Masalan: Onix)")
                kont_opt = st.text_input("Optsiya (Masalan: Premier)")
                kont_soni = st.number_input("Komplektlar Soni (Kit)", min_value=1, step=1)
                kont_loc = st.selectbox("Hozirgi Joylashuv", ["Koreya porti", "Xitoy porti", "Yoʻlda", "Bojxonada", "KD Omborda"])
                kont_eta = st.date_input("ETA (Taxminiy kelish sanasi)")
                kont_crit = st.selectbox("Kritik Holatdami?", ["Yo'q", "Ha"])
                
                submit_kont = st.form_submit_button("Partiyani kiritish")
                if submit_kont:
                    if kont_id and kont_model:
                        append_row("Komplektlar", [kont_id, kont_sh, kont_model, kont_opt, int(kont_soni), kont_loc, str(kont_eta), kont_crit])
                        st.success("Konteyner tizimga qo'shildi!")
                    else:
                        st.error("Konteyner ID va Model kiritilishi shart.")

    with col_update:
        with st.expander("🔄 Konteyner Statusini Yangilash"):
            if not df_komplektlar.empty:
                with st.form("status_update_form"):
                    selected_kont = st.selectbox("Konteynerni tanlang", df_komplektlar["Konteyner / Partiya ID"].tolist())
                    new_loc = st.selectbox("Yangi Joylashuv / Status", ["Koreya porti", "Xitoy porti", "Yoʻlda", "Bojxonada", "KD Omborda", "Ishlab chiqarish liniyasida"])
                    is_crit = st.selectbox("Kritik Holat Statusi", ["Yo'q", "Ha"])
                    
                    submit_update = st.form_submit_button("Statusni yangilash")
                    if submit_update:
                        worksheet = sh.worksheet("Komplektlar")
                        cell = worksheet.find(selected_kont)
                        if cell:
                            worksheet.update_cell(cell.row, 6, new_loc)
                            worksheet.update_cell(cell.row, 8, is_crit)
                            st.success(f"{selected_kont} statusi muvaffaqiyatli yangilandi!")
                        else:
                            st.error("Konteyner topilmadi.")
            else:
                st.info("Yangilash uchun tizimda konteynerlar yo'q.")

# ==================== TAB 4: ISHLAB CHIQARISH LINIYASI ====================
with tab_ishlab:
    st.header("Ishlab Chiqarish va Yig'ish Jarayoni")
    st.dataframe(df_ishlab_chiqarish, use_container_width=True)

    col_line_add, col_line_update = st.columns(2)

    with col_line_add:
        with st.expander("🏭 Komplektlarni Liniyaga chiqarish (Yig'ishni boshlash)"):
            with st.form("line_add_form", clear_on_submit=True):
                line_id = st.text_input("Liniya ID (Masalan: LINE-2026-001)")
                kont_list = df_komplektlar[df_komplektlar["Hozirgi Joylashuv"] == "KD Omborda"]["Konteyner / Partiya ID"].tolist() if not df_komplektlar.empty else []
                if not kont_list:
                    st.warning("Eslatma: KD Omborda yig'ishga tayyor komplektlar mavjud emas.")
                
                selected_kont_line = st.selectbox("Qaysi partiyadan olinadi?", kont_list if kont_list else ["Omborda yuk yo'q"])
                l_model = st.text_input("Model (Masalan: Onix)")
                l_opt = st.text_input("Optsiya (Masalan: Premier)")
                l_soni = st.number_input("Yig'ishga topshirilayotgan soni", min_value=1, step=1)
                l_date = st.date_input("Liniyaga chiqqan sana")
                
                submit_line = st.form_submit_button("Yig'ishni boshlash")
                if submit_line:
                    if line_id and selected_kont_line != "Omborda yuk yo'q":
                        append_row("Ishlab_Chiqarish", [line_id, selected_kont_line, l_model, l_opt, int(l_soni), str(l_date), 0, "Kutilmoqda"])
                        
                        worksheet_k = sh.worksheet("Komplektlar")
                        cell_k = worksheet_k.find(selected_kont_line)
                        if cell_k:
                            worksheet_k.update_cell(cell_k.row, 6, "Ishlab chiqarish liniyasida")
                            
                        st.success("Komplektlar liniyaga muvaffaqiyatli yo'naltirildi!")
                    else:
                        st.error("Ma'lumotlar to'liq emas.")

    with col_line_update:
        with st.expander("✅ Mashina Yig'ilishini Yakunlash (Tayyor Mahsulot)"):
            if not df_ishlab_chiqarish.empty:
                # Ustun nomini xavfsiz qidirish
                active_lines = df_ishlab_chiqarish[df_ishlab_chiqarish["Tayyor Bo'lgan Soni"].astype(int) == 0]["Liniya ID"].tolist()
                
                if active_lines:
                    with st.form("line_update_form"):
                        sel_line = st.selectbox("Yakunlanadigan Liniyani tanlang", active_lines)
                        tayyor_soni_input = st.number_input("Yig'ilgan tayyor mashinalar soni", min_value=1, step=1)
                        tayyor_sana = st.date_input("Tayyor bo'lgan sana")
                        
                        submit_line_up = st.form_submit_button("Yig'ishni yakunlash")
                        if submit_line_up:
                            worksheet_l = sh.worksheet("Ishlab_Chiqarish")
                            cell_l = worksheet_l.find(sel_line)
                            if cell_l:
                                worksheet_l.update_cell(cell_l.row, 7, int(tayyor_soni_input))
                                worksheet_l.update_cell(cell_l.row, 8, str(tayyor_sana))
                                st.success(f"{sel_line} bo'yicha yig'ish yakunlandi!")
                            else:
                                st.error("Liniya topilmadi.")
                else:
                    st.info("Hozirda yig'ish jarayonidagi faol liniyalar mavjud emas.")
            else:
                st.info("Yig'ish tarixi mavjud emas.")

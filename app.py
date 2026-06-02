import streamlit as st
import gspread
import pandas as pd
import datetime
import plotly.express as px

# Sahifa sozlamalari
st.set_page_config(page_title="Asaka Motors Supply Chain CRM", layout="wide", page_icon="🏭")

# ==================== TIZIMGA KIRISH (AUTHENTICATION WITH AUTO-RELOAD) ====================
# Rol bo'sh bo'lib qolishining oldini olish uchun xavfsiz tekshiruv
if "logged_in" not in st.session_state or "role" not in st.session_state or not st.session_state.role:
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
# Rol belgilarini kichik harfga o'tkazib solishtiramiz (xatoliklarni oldini olish uchun)
role = str(st.session_state.role).lower()
tabs_list = ["📈 Boshqaruv Paneli (Dashboard)"]

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
                            for t_idx, t_row in t_rows.iterrows():
                                t_soni = int(t_row["Komplektlar Soni"])
                                transit_qty_model += t_soni
                                
                                try:
                                    plan_dt = datetime.datetime.strptime(p_date_str, "%Y-%m-%d").date()
                                    eta_dt = datetime.datetime.strptime(str(t_row["ETA (Kelish sanasi)"]), "%Y-%m-%d").date()
                                    if eta_dt > plan_dt:
                                        transit_delayed.append((t_row["Konteyner / Partiya ID"], t_row["ETA (Kelish sanasi)"], t_soni))
                                    else:
                                        transit_before_plan += t_soni
                                except:
                                    transit_before_plan += t_soni
                        
                        total_available_in_time = wh_qty_model + transit_before_plan
                        total_overall = wh_qty_model + transit_qty_model
                        
                        if total_overall < p_qty:
                            deficit = p_qty - total_overall
                            st.error(f"🔴 **MUTLAQ DEFIZIT: {p_model} ({p_opt})** \n\n"
                                     f"Reja bo'yicha **{p_qty} ta** yig'ilishi kerak (Muddati: {p_date_str}). \n\n"
                                     f"Omborda va tranzitda jami jismoniy qoldiq: **{total_overall} ta**. \n\n"
                                     f"⚠️ **Yetishmovchilik:** {deficit} ta komplekt! Qo'shimcha zakaz bering.")
                            alerts_triggered = True
                            
                        elif total_available_in_time < p_qty:
                            st.warning(f"🟡 **KECHIKISH XAVFI: {p_model} ({p_opt})** \n\n"
                                       f"Reja muddati: {p_date_str} (Hajmi: {p_qty} ta). \n\n"
                                       f"O'z vaqtida yetib keladigan komplektlar jami: **{total_available_in_time} ta**. \n\n"
                                       f"Kechikayotgan yuklar: " + ", ".join([f"`{cid}` (ETA: {eta})" for cid, eta, qty in transit_delayed]))
                            alerts_triggered = True

                if not df_komplektlar.empty:
                    kritik_df = df_komplektlar[(df_komplektlar["Kritik Holat"] == "Ha") & ~(df_komplektlar["Hozirgi Joylashuv"] == "Ishlab chiqarish liniyasida")]
                    if not kritik_df.empty:
                        for idx, row in kritik_df.iterrows():
                            st.error(f"⚠️ **Kritik Konteyner:** {row['Konteyner / Partiya ID']} ({row['Model']})\n\n**Joylashuvi:** {row['Hozirgi Joylashuv']} | **Soni:** {row['Komplektlar Soni']} ta.")
                            alerts_triggered = True
                
                if not alerts_triggered:
                    st.success("Barcha ishlab chiqarish rejalari ta'minot bilan to'liq qoplangan. Ta'minot zanjiri barqaror.")

        # 1.5 ISHLAB CHIQARISH REJASI KODI (REJA TAB)
        elif "Ishlab Chiqarish Rejasi" in tab_name:
            st.header("Ishlab Chiqarish Rejasi (Production Plan)")
            st.dataframe(df_reja, use_container_width=True)

            col_plan_add, col_plan_up = st.columns(2)
            with col_plan_add:
                with st.expander("➕ Yangi Ishlab Chiqarish Rejasini Kiritish"):
                    with st.form("reja_add_form", clear_on_submit=True):
                        p_id = st.text_input("Reja ID (Masalan: PLAN-COB-06)")
                        p_model = st.text_input("Model (Masalan: Cobalt)")
                        p_opt = st.text_input("Optsiya (Masalan: GX-Style)")
                        p_qty = st.number_input("Rejalashtirilgan Soni (Hajmi)", min_value=1, step=1)
                        p_date = st.date_input("Muddati")
                        p_status = st.selectbox("Status", ["Kutilmoqda", "Bajarilmoqda", "Yakunlandi"])
                        
                        submit_p = st.form_submit_button("Rejani Saqlash")
                        if submit_p:
                            if p_id and p_model:
                                append_row("Reja", [p_id, p_model, p_opt, int(p_qty), str(p_date), p_status])
                                st.success("Reja muvaffaqiyatli kiritildi! Sahifani yangilang.")
                            else:
                                st.error("Liniya ID va Model majburiy.")
            
            with col_plan_up:
                with st.expander("🔄 Reja Statusini O'zgartirish"):
                    if not df_reja.empty:
                        active_p_list = df_reja[df_reja["Status"] != "Yakunlandi"]["Reja ID"].tolist()
                        if active_p_list:
                            with st.form("reja_up_form"):
                                sel_p = st.selectbox("Rejani tanlang", active_p_list)
                                new_p_status = st.selectbox("Yangi Status", ["Kutilmoqda", "Bajarilmoqda", "Yakunlandi"])
                                submit_p_up = st.form_submit_button("Statusni yangilash")
                                if submit_p_up:
                                    worksheet_r = sh.worksheet("Reja")
                                    cell_r = worksheet_r.find(sel_p)
                                    if cell_r:
                                        worksheet_r.update_cell(cell_r.row, 6, new_p_status)
                                        st.success("Reja muvaffaqiyatli yangilandi! Sahifani yangilang.")
                        else:
                            st.info("Hozirda faol rejalar maqomida yuk yo'q.")
                    else:
                        st.info("Kiritilgan rejalar tarixi yo'q.")

        # 2. SHARTNOMALAR KODI
        elif "Import Shartnomalari" in tab_name:
            st.header("Import Shartnomalari")
            st.dataframe(df_shartnomalar, use_container_width=True)

            with st.expander("➕ Yangi Import Shartnomasini Kiritish"):
                with st.form("shartnoma_form", clear_on_submit=True):
                    sh_id = st.text_input("Shartnoma ID")
                    sh_model = st.text_input("Model")
                    sh_opt = st.text_input("Optsiya")
                    sh_soni = st.number_input("Komplektlar Soni", min_value=1, step=1)
                    sh_date = st.date_input("Plan qilingan kelish sanasi")
                    sh_status = st.selectbox("Status", ["Imzolangan", "To'lov qilingan", "Yopilgan"])
                    submit_sh = st.form_submit_button("Shartnomani Saqlash")
                    if submit_sh:
                        if sh_id and sh_model:
                            append_row("Shartnomalar", [sh_id, f"{sh_model} ({sh_opt})", str(sh_date), int(sh_soni), sh_status])
                            st.success("Muvaffaqiyatli saqlandi! Sahifani yangilang.")
                        else:
                            st.error("Ma'lumotlarni to'ldiring.")

        # 3. LOGISTIKA KODI
        elif "Komplektlar & Logistika" in tab_name:
            st.header("Tranzitdagi va Ombordagi Komplektlar")
            st.dataframe(df_komplektlar, use_container_width=True)

            col_add, col_update = st.columns(2)
            with col_add:
                with st.expander("🚚 Yangi Konteyner / Partiya kiritish"):
                    with st.form("komplekt_form", clear_on_submit=True):
                        kont_id = st.text_input("Konteyner / Partiya ID")
                        sh_list = df_shartnomalar["Shartnoma ID"].tolist() if not df_shartnomalar.empty else ["Shartnoma yo'q"]
                        kont_sh = st.selectbox("Qaysi Shartnomaga tegishli?", sh_list)
                        kont_model = st.text_input("Model")
                        kont_opt = st.text_input("Optsiya")
                        kont_soni = st.number_input("Komplektlar Soni", min_value=1, step=1)
                        kont_loc = st.selectbox("Hozirgi Joylashuv", ["Koreya porti", "Xitoy porti", "Yoʻlda", "Bojxonada", "KD Omborda"])
                        kont_eta = st.date_input("ETA")
                        kont_crit = st.selectbox("Kritik Holatdami?", ["Yo'q", "Ha"])
                        submit_kont = st.form_submit_button("Partiyani kiritish")
                        if submit_kont:
                            if kont_id and kont_model:
                                append_row("Komplektlar", [kont_id, kont_sh, kont_model, kont_opt, int(kont_soni), kont_loc, str(kont_eta), kont_crit])
                                st.success("Muvaffaqiyatli kiritildi! Sahifani yangilang.")
                            else:
                                st.error("Ma'lumotlar to'liq emas.")
            with col_update:
                with st.expander("🔄 Konteyner Statusini Yangilash"):
                    if not df_komplektlar.empty:
                        with st.form("status_update_form"):
                            selected_kont = st.selectbox("Konteynerni tanlang", df_komplektlar["Konteyner / Partiya ID"].tolist())
                            new_loc = st.selectbox("Yangi Status", ["Koreya porti", "Xitoy porti", "Yoʻlda", "Bojxonada", "KD Omborda", "Ishlab chiqarish liniyasida"])
                            is_crit = st.selectbox("Kritik Holat Statusi", ["Yo'q", "Ha"])
                            submit_update = st.form_submit_button("Statusni yangilash")
                            if submit_update:
                                worksheet = sh.worksheet("Komplektlar")
                                cell = worksheet.find(selected_kont)
                                if cell:
                                    worksheet.update_cell(cell.row, 6, new_loc)
                                    worksheet.update_cell(cell.row, 8, is_crit)
                                    st.success("Muvaffaqiyatli yangilandi! Sahifani yangilang.")
                    else:
                        st.info("Konteynerlar yo'q.")

        # 4. ISHLAB CHIQARISH KODI
        elif "Ishlab Chiqarish" in tab_name:
            st.header("Ishlab Chiqarish va Yig'ish Jarayoni")
            st.dataframe(df_ishlab_chiqarish, use_container_width=True)

            col_line_add, col_line_update = st.columns(2)
            
            kont_list = []
            if not df_komplektlar.empty:
                for idx, row in df_komplektlar[df_komplektlar["Hozirgi Joylashuv"].isin(["KD Omborda", "Ishlab chiqarish liniyasida"])].iterrows():
                    cid = row["Konteyner / Partiya ID"]
                    tot = int(row["Komplektlar Soni"])
                    sent = df_ishlab_chiqarish[df_ishlab_chiqarish["Konteyner / Partiya ID"] == cid]["Yig'ilayotgan Soni"].astype(int).sum() if not df_ishlab_chiqarish.empty else 0
                    if tot - sent > 0:
                        kont_list.append(cid)

            with col_line_add:
                with st.expander("🏭 Liniyaga chiqarish (Yig'ishni boshlash)"):
                    if kont_list:
                        with st.form("line_add_form", clear_on_submit=True):
                            line_id = st.text_input("Liniya ID")
                            selected_kont_line = st.selectbox("Qaysi partiyadan olinadi?", kont_list)
                            row_k = df_komplektlar[df_komplektlar["Konteyner / Partiya ID"] == selected_kont_line].iloc[0]
                            orig_qty = int(row_k["Komplektlar Soni"])
                            already_sent = df_ishlab_chiqarish[df_ishlab_chiqarish["Konteyner / Partiya ID"] == selected_kont_line]["Yig'ilayotgan Soni"].astype(int).sum() if not df_ishlab_chiqarish.empty else 0
                            max_allowed = orig_qty - already_sent
                            
                            st.info(f"Konteynerda jami {orig_qty} ta bor. Ombordagi qoldiq: {max_allowed} ta.")
                            l_model = st.text_input("Model", value=row_k["Model"])
                            l_opt = st.text_input("Optsiya", value=row_k["Optsiya"])
                            l_soni = st.number_input("Soni", min_value=1, max_value=max_allowed, step=1)
                            l_date = st.date_input("Sana")
                            submit_line = st.form_submit_button("Liniyaga chiqarish")
                            if submit_line:
                                if line_id:
                                    append_row("Ishlab_Chiqarish", [line_id, selected_kont_line, l_model, l_opt, int(l_soni), str(l_date), 0, "Kutilmoqda"])
                                    worksheet_k = sh.worksheet("Komplektlar")
                                    cell_k = worksheet_k.find(selected_kont_line)
                                    if cell_k:
                                        if (already_sent + int(l_soni)) >= orig_qty:
                                            worksheet_k.update_cell(cell_k.row, 6, "Ishlab chiqarish liniyasida")
                                        else:
                                            worksheet_k.update_cell(cell_k.row, 6, "KD Omborda")
                                    st.success("Muvaffaqiyatli saqlandi! Sahifani yangilang.")
                                else:
                                    st.error("Liniya ID kiritilishi shart.")
                    else:
                        st.warning("KD Omborda yig'ishga tayyor komplektlar yo'q.")

            with col_line_update:
                with st.expander("✅ Mashina Yig'ilishini Yakunlash"):
                    if not df_ishlab_chiqarish.empty:
                        active_lines = df_ishlab_chiqarish[df_ishlab_chiqarish["Tayyor Bo'lgan Soni"].astype(int) == 0]["Liniya ID"].tolist()
                        if active_lines:
                            with st.form("line_update_form"):
                                sel_line = st.selectbox("Liniyani tanlang", active_lines)
                                row_l = df_ishlab_chiqarish[df_ishlab_chiqarish["Liniya ID"] == sel_line].iloc[0]
                                line_limit = int(row_l["Yig'ilayotgan Soni"])
                                tayyor_soni_input = st.number_input("Yig'ilgan tayyor soni", min_value=1, max_value=line_limit, step=1)
                                tayyor_sana = st.date_input("Tayyor bo'lgan sana")
                                submit_line_up = st.form_submit_button("Yig'ishni yakunlash")
                                if submit_line_up:
                                    worksheet_l = sh.worksheet("Ishlab_Chiqarish")
                                    cell_l = worksheet_l.find(sel_line)
                                    if cell_l:
                                        worksheet_l.update_cell(cell_l.row, 7, int(tayyor_soni_input))
                                        worksheet_l.update_cell(cell_l.row, 8, str(tayyor_sana))
                                        st.success("Muvaffaqiyatli yakunlandi! Sahifani yangilang.")
                        else:
                            st.info("Yig'ish jarayonidagi faol liniyalar yo'q.")
                    else:
                        st.info("Yig'ish tarixi mavjud emas.")

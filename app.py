import streamlit as st
import pandas as pd
import bcrypt
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
import extra_streamlit_components as stx

# ==============================================================================
# 1. DESIGN SYSTÉMU & CSS INJEKCE
# ==============================================================================
class ThemeManager:
    @staticmethod
    def apply_custom_theme():
        st.set_page_config(
            page_title="🔥 FireSport Pro | Týmový Manažer",
            page_icon="⚡",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght=400;500;600;700;800&display=swap');
            html, body, [data-testid="stSidebar"] { font-family: 'Plus Jakarta Sans', sans-serif; }
            div[data-testid="stMetric"] {
                background: linear-gradient(135deg, rgba(255,75,75,0.05) 0%, rgba(255,165,0,0.05) 100%);
                border: 1px solid rgba(255,75,75,0.15);
                padding: 1rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);
            }
            .stButton>button {
                font-weight: 700 !important; border-radius: 8px !important;
                transition: all 0.3s ease !important; text-transform: uppercase; letter-spacing: 0.5px;
            }
            div[data-testid="stExpander"] {
                border-radius: 12px !important; border: 1px solid rgba(0,0,0,0.08) !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
            }
            .badge-success {
                background-color: #d4edda; color: #155724; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; font-weight: 600;
            }
            .calendar-card {
                background: #f8f9fa; border-left: 5px solid #ff4b4b; padding: 10px 15px; border-radius: 4px; margin-bottom: 8px;
            }
        </style>
        """, unsafe_allow_html=True)


# ==============================================================================
# 2. DATOVÁ VRSTVA (OPRAVENÁ PRO TOLERANCI VELKÝCH/MALÝCH PÍSMEN)
# ==============================================================================
class FireSportDB:
    def __init__(self):
        try:
            self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except Exception as e:
            st.error(f"🔴 Kritická chyba inicializace databáze (Zkontroluj st.secrets): {e}")
            st.stop()

    def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        try:
            clean_login = login.strip().lower()
            if not clean_login:
                return None
                
            # OPRAVA: Používáme .ilike. místo .eq. aby vyhledávání ignorovalo velká/malá písmena
            res = self.client.table("uzivatele")\
                .select("*, sbory(nazev_sdh)")\
                .or_(f"email.ilike.{clean_login},prezdivka.ilike.{clean_login}")\
                .execute()
            return res.data[0] if res.data else None
        except Exception as e:
            st.error(f"❌ Chyba při načítání profilu uživatele: {e}")
            return None

    def update_user_profile(self, user_id: int, u_data: Dict[str, Any]) -> bool:
        try:
            self.client.table("uzivatele").update(u_data).eq("id", user_id).execute()
            return True
        except Exception as e:
            st.error(f"❌ Aktualizace profilu selhala: {e}")
            return False

    def get_all_sbory(self) -> List[Dict[str, Any]]:
        try:
            return self.client.table("sbory").select("*").order("nazev_sdh").execute().data or []
        except Exception as e:
            st.warning(f"Nepodařilo se načíst seznam sborů: {e}")
            return []

    def insert_sbor(self, nazev: str) -> Optional[int]:
        try:
            res = self.client.table("sbory").insert({"nazev_sdh": nazev.strip()}).execute()
            if res.data:
                return res.data[0]["id"]
            return None
        except Exception as e:
            st.error(f"❌ Nepodařilo se vytvořit nový klub v DB: {e}")
            return None

    def register_user(self, u_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            res = self.client.table("uzivatele").insert(u_data).execute()
            if res.data:
                return res.data[0]
            return None
        except Exception as e:
            st.error(f"❌ Zápis uživatele do databáze selhal: {e}")
            return None

    def get_pokusy(self, sdh_id: int) -> List[Dict[str, Any]]:
        try:
            return self.client.table("sportovni_pokusy").select("*").eq("sbor_id", sdh_id).order("created_at", desc=True).execute().data or []
        except Exception as e:
            st.error(f"⚠️ Nepodařilo se načíst tréninkové pokusy: {e}")
            return []

    def insert_pokus(self, p_data: Dict[str, Any]) -> Any:
        try:
            return self.client.table("sportovni_pokusy").insert(p_data).execute()
        except Exception as e:
            st.error(f"🔴 Nepodařilo se uložit nový pokus: {e}")
            return None

    def get_soupiska(self, sdh_id: int) -> List[Dict[str, Any]]:
        try:
            return self.client.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", sdh_id).execute().data or []
        except Exception as e:
            st.error(f"⚠️ Problém s načítáním členů soupisky: {e}")
            return []

    def get_sestava(self) -> List[Dict[str, Any]]:
        try:
            return self.client.table("sestava_tymu").select("*").execute().data or []
        except Exception as e:
            st.error(f"⚠️ Nepodařilo se načíst pozice taktické sestavy: {e}")
            return []

    def upsert_sestava(self, s_data: Dict[str, Any]) -> Any:
        try:
            return self.client.table("sestava_tymu").upsert(s_data, on_conflict="uzivatel_id").execute()
        except Exception as e:
            st.error(f"🔴 Nepodařilo se uložit změnu pozice: {e}")
            return None

    def get_material(self, sdh_id: int) -> List[Dict[str, Any]]:
        return self.client.table("sportovni_material").select("*").eq("sbor_id", sdh_id).execute().data or []

    def insert_material(self, m_data: Dict[str, Any]) -> Any:
        return self.client.table("sportovni_material").insert(m_data).execute()

    def get_kalendar(self, sdh_id: int) -> List[Dict[str, Any]]:
        try:
            dnes = datetime.now().date().isoformat()
            return self.client.table("kalendar_akci").select("*").eq("sbor_id", sdh_id).gte("datum", dnes).order("datum").order("cas").execute().data or []
        except Exception as e:
            st.error(f"⚠️ Nepodařilo se načíst plánované akce: {e}")
            return []

    def insert_kalendar_akce(self, a_data: Dict[str, Any]) -> Any:
        try:
            return self.client.table("kalendar_akci").insert(a_data).execute()
        except Exception as e:
            st.error(f"🔴 Chyba při zápisu akce do kalendáře: {e}")
            return None


# ==============================================================================
# 3. APLIKAČNÍ LOGIKA & COOKIE SYSTÉM
# ==============================================================================
class FireSportApp:
    def __init__(self):
        self.db = FireSportDB()
        self.cookie_manager = stx.CookieManager()
        self._init_session_state()

    def _init_session_state(self):
        defaults = {
            "logged_in": False, "user_id": None, "user_jmeno": "",
            "user_prezdivka": "", "user_email": "",
            "sdh_id": None, "sdh_nazev": "", "stranka": "🏆 Výsledky & Tréninky"
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

    def handle_auto_login(self):
        if st.session_state["logged_in"]:
            return

        saved_login = self.cookie_manager.get(cookie="firesport_user_login")
        
        if saved_login:
            user = self.db.get_user_by_login(saved_login)
            if user:
                sbor_nazev = "Bez sboru"
                if user.get("sbory"):
                    if isinstance(user["sbory"], list) and len(user["sbory"]) > 0:
                        sbor_nazev = user["sbory"][0].get("nazev_sdh", "Bez sboru")
                    elif isinstance(user["sbory"], dict):
                        sbor_nazev = user["sbory"].get("nazev_sdh", "Bez sboru")
                
                st.session_state.update({
                    "logged_in": True, "user_id": user["id"],
                    "user_jmeno": f"{user['jmeno']} {user['prijmeni']}",
                    "user_prezdivka": user.get("prezdivka", "") or "",
                    "user_email": user["email"],
                    "sdh_id": user["sdh_id"], "sdh_nazev": sbor_nazev
                })
                st.rerun()

    def render(self):
        ThemeManager.apply_custom_theme()
        self.handle_auto_login()
        
        if not st.session_state.logged_in:
            self.render_auth_zone()
        else:
            self.render_app_zone()

    def render_auth_zone(self):
        st.subheader("🔥 Vítejte v systému FireSport Pro")
        st.caption("Profesionální analytický nástroj pro správu a optimalizaci útoků v požárním sportu.")
        
        tab_login, tab_reg = st.tabs(["🔒 Přihlášení do šatny", "📝 Registrace nového týmu/člena"])
        
        with tab_login:
            with st.form("auth_login_form"):
                login = st.text_input("E-mail nebo Přezdívka", placeholder="pavel.proud / pavel@sdh.cz").strip()
                heslo = st.text_input("Heslo", type="password", placeholder="••••••••")
                remember_me = st.checkbox("Zůstat přihlášený (na 30 dní)", value=True)
                submit_login = st.form_submit_button("Vstoupit do aplikace", type="primary", use_container_width=True)
                
            if submit_login:
                if login and heslo:
                    user = self.db.get_user_by_login(login)
                    if user:
                        if bcrypt.checkpw(heslo.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                            sbor_nazev = "Bez sboru"
                            if user.get("sbory"):
                                if isinstance(user["sbory"], list) and len(user["sbory"]) > 0:
                                    sbor_nazev = user["sbory"][0].get("nazev_sdh", "Bez sboru")
                                elif isinstance(user["sbory"], dict):
                                    sbor_nazev = user["sbory"].get("nazev_sdh", "Bez sboru")
                            
                            st.session_state.update({
                                "logged_in": True, "user_id": user["id"],
                                "user_jmeno": f"{user['jmeno']} {user['prijmeni']}",
                                "user_prezdivka": user.get("prezdivka", "") or "",
                                "user_email": user["email"],
                                "sdh_id": user["sdh_id"], "sdh_nazev": sbor_nazev
                            })
                            
                            if remember_me:
                                self.cookie_manager.set("firesport_user_login", login, max_age=2592000)
                            
                            st.success("🔓 Přihlášení úspěšné! Vstupuji...")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("❌ Nesprávné heslo. Zkuste to znovu.")
                    else:
                        st.error("❌ Účet s tímto loginem neexistuje. Zkontrolujte e-mail nebo přezdívku.")
                else:
                    st.warning("⚠️ Vyplňte přihlašovací pole.")

        with tab_reg:
            with st.form("auth_reg_form"):
                typ_reg = st.radio("Způsob registrace:", ["Přidat se k existujícímu týmu", "Vytvořit zcela nový sportovní klub/tým"])
                sbory = self.db.get_all_sbory()
                sbor_dict = {s["nazev_sdh"]: s["id"] for s in sbory}
                
                if typ_reg == "Přidat se k existujícímu týmu" and sbor_dict:
                    vybrany_sbor_nazev = st.selectbox("Vyberte tým ze seznamu:", list(sbor_dict.keys()))
                    sdh_id = sbor_dict[vybrany_sbor_nazev]
                    novy_sbor = None
                else:
                    novy_sbor = st.text_input("Název nového týmu (např. SDH Lhotka - muži)").strip()
                    sdh_id = None

                cc1, cc2 = st.columns(2)
                jmeno = cc1.text_input("Jméno").strip()
                prijmeni = cc2.text_input("Příjmení").strip()
                prezdivka_reg = st.text_input("Přezdívka (volitelné)").strip().lower()
                email = st.text_input("E-mail (hlavní přihlašovací login)").strip().lower()
                heslo_raw = st.text_input("Heslo do systému", type="password")
                submit_reg = st.form_submit_button("Dokončit registraci a vytvořit účet", use_container_width=True)

            if submit_reg:
                if email and heslo_raw and jmeno and prijmeni:
                    if typ_reg == "Vytvořit zcela nový sportovní klub/tým":
                        if not novy_sbor:
                            st.error("❌ Pro vytvoření nového týmu musíte vyplnit jeho název!")
                            st.stop()
                        sdh_id = self.db.insert_sbor(novy_sbor)
                        sbor_final_nazev = novy_sbor
                        if not sdh_id:
                            st.stop()
                    else:
                        sbor_final_nazev = vybrany_sbor_nazev
                    
                    hashed = bcrypt.hashpw(heslo_raw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    
                    reg_payload = {
                        "sdh_id": sdh_id, "jmeno": jmeno, "prijmeni": prijmeni, 
                        "email": email, "prezdivka": prezdivka_reg if prezdivka_reg else None,
                        "heslo_hash": hashed, "role": "správce"
                    }
                    
                    created_user = self.db.register_user(reg_payload)
                    
                    if created_user:
                        st.session_state.update({
                            "logged_in": True, "user_id": created_user["id"],
                            "user_jmeno": f"{created_user['jmeno']} {created_user['prijmeni']}",
                            "user_prezdivka": created_user.get("prezdivka", "") or "",
                            "user_email": created_user["email"],
                            "sdh_id": created_user["sdh_id"], "sdh_nazev": sbor_final_nazev
                        })
                        
                        self.cookie_manager.set("firesport_user_login", email, max_age=2592000)
                        st.success("🎉 Účet úspěšně vytvořen! Vstupuji do systému...")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.warning("⚠️ Musíte vyplnit všechna povinná pole.")

    def render_app_zone(self):
        with st.sidebar:
            st.markdown(f"### 🎽 {st.session_state.user_jmeno}")
            if st.session_state.user_prezdivka:
                st.caption(f"Přezdívka: @{st.session_state.user_prezdivka}")
            st.markdown(f"🏆 Klub: **{st.session_state.sdh_nazev}**")
            st.markdown("<span class='badge-success'>🟢 Full Access (Správce)</span>", unsafe_allow_html=True)
            st.write("")
            
            menu = [
                "🏆 Výsledky & Tréninky", 
                "🏃 Soupiska & Posty", 
                "⚡ Sportovní nářadí & Mašina",
                "⚙️ Nastavení profilu"
            ]
            volba = st.sidebar.radio("Navigace sekcí:", menu, key="stranka")
            
            st.divider()
            
            if st.button("Odhlásit se z kabiny", use_container_width=True, type="secondary"):
                self.cookie_manager.delete("firesport_user_login")
                for k in ["logged_in", "user_id", "user_jmeno", "user_prezdivka", "user_email", "sdh_id", "sdh_nazev"]:
                    st.session_state[k] = None
                st.session_state.logged_in = False
                st.rerun()

        if volba == "🏆 Výsledky & Tréninky":
            self.view_vysledky()
        elif volba == "🏃 Soupiska & Posty":
            self.view_soupiska()
        elif volba == "⚡ Sportovní nářadí & Mašina":
            self.view_naradi()
        elif volba == "⚙️ Nastavení profilu":
            self.view_profil_settings()

    # ==============================================================================
    # POHLED: VÝSLEDKY, TRÉNINKY & MINI KALENDÁŘ
    # ==============================================================================
    def view_vysledky(self):
        st.header("🏆 Týmový deník & Telemetrie útoků")
        
        # --- SEKCE MINI KALENDÁŘE ---
        col_cal, col_add = st.columns([2, 1])
        
        with col_cal:
            st.subheader("📅 Nadcházející akce týmu")
            akce = self.db.get_kalendar(st.session_state.sdh_id)
            if akce:
                for a in akce:
                    try:
                        datum_raw = datetime.strptime(a["datum"], "%Y-%m-%d").strftime("%d. %m. %Y")
                    except:
                        datum_raw = a["datum"]
                        
                    cas_raw = a["cas"][:5] if a.get("cas") else "Čas neurčen"
                    ikona = "🏃‍♂️" if a["typ_akce"] == "Trénink" else "🔥"
                    
                    st.markdown(f"""
                    <div class="calendar-card" style="border-left-color: {'#ff8c00' if a['typ_akce'] == 'Trénink' else '#ff4b4b'};">
                        <strong>{ikona} {a['typ_akce']}: {a['nazev']}</strong><br/>
                        ⏱️ {datum_raw} v {cas_raw} | 📍 Místo: {a.get('misto', 'Nespecifikováno')}<br/>
                        <small style="color: #666;">📝 {a.get('poznamka', '') or 'Bez poznámky.'}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Na nejbližší dny nejsou naplánované žádné tréninky ani závody.")
                
        with col_add:
            st.subheader("🛠️ Plánovač")
            with st.expander("➕ Přidat událost", expanded=False):
                with st.form("novy_kalendar_form", clear_on_submit=True):
                    a_typ = st.selectbox("Typ akce", ["Trénink", "Soutěž"])
                    a_nazev = st.text_input("Název akce", placeholder="např. Příprava základna / Extraliga")
                    a_datum = st.date_input("Datum", datetime.now().date())
                    a_cas = st.time_input("Čas zahájení")
                    a_misto = st.text_input("Lokalita / Místo")
                    a_poznamka = st.text_area("Bližší info (např. s sebou tretry)", height=70)
                    
                    if st.form_submit_button("Uložit do kalendáře", use_container_width=True):
                        if a_nazev:
                            self.db.insert_kalendar_akce({
                                "sbor_id": st.session_state.sdh_id,
                                "typ_akce": a_typ,
                                "nazev": a_nazev,
                                "datum": a_datum.isoformat(),
                                "cas": a_cas.strftime("%H:%M:%S"),
                                "misto": a_misto,
                                "poznamka": a_poznamka
                            })
                            st.success("Akce byla uložena!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Vyplňte prosím název akce.")

        st.divider()

        # --- TELEMETRIE ÚTOKŮ ---
        st.subheader("⏱️ Telemetrie měřených pokusů")
        with st.expander("⏱️ ZAPSAT NOVÝ DOSAŽENÝ ČAS / POKUS", expanded=False):
            with st.form("pokus_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                f_typ = c1.selectbox("Typ měřené aktivity", ["Trénink - Útok", "Závod - Extraliga", "Závod - Okresní liga", "Pohárová soutěž"])
                f_soutez = c2.text_input("Lokalita / Název soutěže", value="Domácí základna")
                
                cc1, cc2, cc3 = st.columns(3)
                f_voda = cc1.number_input("Čas vody / Koš (s)", min_value=0.0, max_value=60.0, value=9.50, step=0.01, format="%.2f")
                f_levy = cc2.number_input("Levý proud (s)", min_value=0.0, max_value=60.0, value=14.20, step=0.01, format="%.2f")
                f_pravy = cc3.number_input("Pravý proud (s)", min_value=0.0, max_value=60.0, value=14.50, step=0.01, format="%.2f")
                
                f_np = st.checkbox("⚠️ Neplatný pokus (NP / Nedokončeno)")
                f_not = st.text_input("Zápis a analýza chyb (např. prostřik vpravo)")
                
                if st.form_submit_button("⚡ Odeslat data do cloudu", type="primary"):
                    vysledny = max(f_levy, f_pravy) if not f_np else 0.0
                    self.db.insert_pokus({
                        "sbor_id": st.session_state.sdh_id, "typ_udalosti": f_typ, "nazev_souteze": f_soutez,
                        "cas_voda": f_voda, "cas_levy_proud": f_levy, "cas_pravy_proud": f_pravy,
                        "vysledny_cas": vysledny, "diskvalifikace": f_np, "poznamka": f_not
                    })
                    st.success("🎯 Data úspěšně odeslána.")
                    time.sleep(0.5)
                    st.rerun()

        if st.session_state.sdh_id:
            pokusy = self.db.get_pokusy(st.session_state.sdh_id)
            if pokusy:
                df = pd.DataFrame(pokusy)
                
                for col in ["diskvalifikace", "vysledny_cas", "created_at", "cas_levy_proud", "cas_pravy_proud", "typ_udalosti", "nazev_souteze", "cas_voda", "poznamka"]:
                    if col not in df.columns: 
                        df[col] = False if col == "diskvalifikace" else 0.0 if "cas" in col or col == "vysledny_cas" else ""

                platne = df[df["diskvalifikace"] == False]
                
                m1, m2, m3 = st.columns(3)
                if not platne.empty:
                    m1.metric("🏆 Rekord sezóny (Tým)", f"{float(platne['vysledny_cas'].min()):.2f} s")
                    m2.metric("⏱️ Průměrný čas útoku", f"{float(platne['vysledny_cas'].mean()):.2f} s")
                else:
                    m1.metric("🏆 Rekord sezóny (Tým)", "N/A")
                    m2.metric("⏱️ Průměrný čas útoku", "N/A")
                m3.metric("🏃 Celkem pokusů", len(df))
                
                st.write("### 📊 Detailní přehled pokusů")
                
                df["datum"] = pd.to_datetime(df["created_at"], errors="coerce").dt.date
                df["prostrik"] = (df["cas_levy_proud"].astype(float) - df["cas_pravy_proud"].astype(float)).abs()
                df["status"] = df["diskvalifikace"].map({True: "❌ Neplatný (NP)", False: "✅ Platný pokus"})
                
                ui_df = df[["datum", "typ_udalosti", "nazev_souteze", "cas_voda", "cas_levy_proud", "cas_pravy_proud", "prostrik", "vysledny_cas", "status", "poznamka"]]
                
                st.dataframe(
                    ui_df,
                    column_config={
                        "datum": st.column_config.DateColumn("Datum"),
                        "typ_udalosti": st.column_config.TextColumn("Kategorie"),
                        "nazev_souteze": st.column_config.TextColumn("Místo konání"),
                        "cas_voda": st.column_config.NumberColumn("Koš/Voda", format="%.2f s"),
                        "cas_levy_proud": st.column_config.NumberColumn("Levý proud", format="%.2f s"),
                        "cas_pravy_proud": st.column_config.NumberColumn("Pravý proud", format="%.2f s"),
                        "prostrik": st.column_config.NumberColumn("Prostřik", format="%.2f s"),
                        "vysledny_cas": st.column_config.NumberColumn("VÝSLEDNÝ ČAS", format="%.2f s"),
                        "status": st.column_config.TextColumn("Stav pokusu"),
                        "poznamka": st.column_config.TextColumn("Komentář analýzy")
                    },
                    hide_index=True, use_container_width=True
                )

    # ==============================================================================
    # POHLED: SOUPISKA & POSTY
    # ==============================================================================
    def view_soupiska(self):
        st.header("🏃 Sestava týmu & Taktická tabule")
        
        zavodnici = self.db.get_soupiska(st.session_state.sdh_id)
        sestava = self.db.get_sestava()
        
        zavodnici_dict = {f"{z['jmeno']} {z['prijmeni']}": z["id"] for z in zavodnici}
        sestava_dict = {s["uzivatel_id"]: s for s in sestava if "uzivatel_id" in s}
        
        if zavodnici_dict:
            with st.expander("🛠️ TAKTIKA: MANAGEMENT POZIC", expanded=False):
                with st.form("taktika_form"):
                    atlet = st.selectbox("Závodník pro přiřazení postu:", list(zavodnici_dict.keys()))
                    post = st.selectbox("Primární závodní pozice:", ["Koš", "Savice", "Stroj", "Béčka", "Rozdělovač", "Levý proud", "Pravý proud"])
                    zaloha = st.text_input("Alternativní / Záložní posty", value="Univerzál")
                    
                    if st.form_submit_button("🔒 Zafixovat sestavu"):
                        u_id = zavodnici_dict[atlet]
                        strana = "Levá" if post == "Levý proud" else "Pravá" if post == "Pravý proud" else "Střed"
                        self.db.upsert_sestava({
                            "uzivatel_id": u_id, "hlavni_post": post, "strana": strana, "zalozni_post": zaloha
                        })
                        st.success("Taktické rozřazení uloženo.")
                        st.rerun()
                        
        st.write("### 🎽 Aktivní soupiska")
        if zavodnici:
            sestava_data = []
            for z in zavodnici:
                s_info = sestava_dict.get(z["id"], {})
                sestava_data.append({
                    "Závodník": f"{z['jmeno']} {z['prijmeni']}",
                    "Hlavní post": s_info.get("hlavni_post", "⚠️ Nepřiřazen (Mimo soupisku)"),
                    "Záložní varianta": s_info.get("zalozni_post", "—")
                })
            st.dataframe(pd.DataFrame(sestava_data), use_container_width=True, hide_index=True)

    # ==============================================================================
    # POHLED: SPORTOVNÍ NÁŘADÍ
    # ==============================================================================
    def view_naradi(self):
        st.header("⚡ Sklad sportovního materiálu & Speciály")
        
        with st.expander("➕ INVENTARIZACE: PŘIDAT MATERIÁL", expanded=False):
            with st.form("material_form"):
                n_nazev = st.text_input("Přesné označení nářadí", placeholder="Hadice C52 - Sport Slim")
                c1, c2 = st.columns(2)
                n_typ = c1.selectbox("Kategorie materiálu", ["Mašina PS 12", "Hadice B", "Hadice C", "Savice", "Proudnice", "Koš", "Rozdělovač"])
                n_stav = c2.selectbox("Kondice / Nasazení", ["🔥 TOP stav (Závodní)", "🔄 Tréninková zátěž", "🛠️ V opravě / Revize"])
                n_param = st.text_input("Technické specifikace", placeholder="délka 15.02m, gramáž 2100g")
                
                if st.form_submit_button("💾 Zařadit do evidence"):
                    if n_nazev:
                        self.db.insert_material({
                            "sbor_id": st.session_state.sdh_id, 
                            "nazev": n_nazev, 
                            "kategorie": n_typ, 
                            "stav": n_stav, 
                            "parametry": n_param
                        })
                        st.success("Nářadí bylo katalogizováno.")
                        st.rerun()

        material = self.db.get_material(st.session_state.sdh_id)
        if material:
            df_mat = pd.DataFrame(material)
            for col in ["kategorie", "nazev", "parametry", "stav"]:
                if col not in df_mat.columns: df_mat[col] = "—"
            
            st.dataframe(
                df_mat[["kategorie", "nazev", "parametry", "stav"]],
                column_config={
                    "kategorie": st.column_config.TextColumn("Kategorie nářadí"),
                    "nazev": st.column_config.TextColumn("Název a značka"),
                    "parametry": st.column_config.TextColumn("Specifikace a rozměry"),
                    "stav": st.column_config.TextColumn("Technický stav")
                },
                use_container_width=True, hide_index=True
            )

    # ==============================================================================
    # POHLED: NASTAVENÍ PROFILU
    # ==============================================================================
    def view_profil_settings(self):
        st.header("⚙️ Nastavení vašeho sportovního profilu")
        st.caption("Zde můžete spravovat své osobní údaje a nastavit si jedinečnou přezdívku pro rychlé přihlášení.")
        
        with st.form("profile_update_form"):
            st.write("### Osobní identifikátory")
            new_prezdivka = st.text_input("Vaše přezdívka (bez mezer)", value=st.session_state.user_prezdivka, placeholder="např. strojnik_tomas").strip().lower()
            
            st.divider()
            st.write("### Kontaktní a evidenční údaje")
            c1, c2 = st.columns(2)
            curr_jmeno = c1.text_input("Jméno", value=st.session_state.user_jmeno.split()[0] if st.session_state.user_jmeno else "")
            curr_prijmeni = c2.text_input("Příjmení", value=st.session_state.user_jmeno.split()[1] if len(st.session_state.user_jmeno.split()) > 1 else "")
            
            st.text_input("E-mailová adresa (nelze měnit)", value=st.session_state.user_email, disabled=True)
            
            save_profile = st.form_submit_button("💾 Uložit změny v profilu", type="primary")
            
        if save_profile:
            payload = {
                "jmeno": curr_jmeno,
                "prijmeni": curr_prijmeni,
                "prezdivka": new_prezdivka if new_prezdivka else None
            }
            
            success = self.db.update_user_profile(st.session_state.user_id, payload)
            if success:
                st.session_state["user_jmeno"] = f"{curr_jmeno} {curr_prijmeni}"
                st.session_state["user_prezdivka"] = new_prezdivka
                
                if self.cookie_manager.get(cookie="firesport_user_login"):
                    login_to_save = new_prezdivka if new_prezdivka else st.session_state.user_email
                    self.cookie_manager.set("firesport_user_login", login_to_save, max_age=2592000)
                    
                st.success("✅ Profil byl úspěšně aktualizován!")
                time.sleep(0.5)
                st.rerun()


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    app = FireSportApp()
    app.render()

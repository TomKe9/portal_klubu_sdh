import streamlit as st
import pandas as pd
import bcrypt
from datetime import datetime
from typing import Dict, Any, List, Optional
from supabase import create_client, Client

# ==============================================================================
# 1. DESIGN SYSTÉMU & CSS INJEKCE (UI/UX na úrovni dospělého produktu)
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
        
        # Injekce vlastního CSS pro moderní tmavý/světlý sportovní režim, zaoblení karet a stíny
        st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
            
            /* Globální reset písma */
            html, body, [data-testid="stSidebar"] {
                font-family: 'Plus Jakarta Sans', sans-serif;
            }
            
            /* Stylování kontejnerů a karet */
            div[data-testid="stMetric"] {
                background: linear-gradient(135deg, rgba(255,75,75,0.05) 0%, rgba(255,165,0,0.05) 100%);
                border: 1px solid rgba(255,75,75,0.15);
                padding: 1rem;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.02);
            }
            
            /* Tlačítka s plynulým přechodem */
            .stButton>button {
                font-weight: 700 !important;
                border-radius: 8px !important;
                transition: all 0.3s ease !important;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            /* Formuáře a expandery */
            div[data-testid="stExpander"] {
                border-radius: 12px !important;
                border: 1px solid rgba(0,0,0,0.08) !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
                background-color: transparent !important;
            }
            
            /* Vlastní styly pro stavy a labely */
            .badge-success {
                background-color: #d4edda;
                color: #155724;
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 0.85rem;
                font-weight: 600;
            }
        </style>
        """, unsafe_allow_html=True)


# ==============================================================================
# 2. DATOVÁ VRSTVA (Data Access Object - Izolace DB od UI)
# ==============================================================================
class FireSportDB:
    def __init__(self):
        try:
            self.client: Client = create_client(
                st.secrets["SUPABASE_URL"], 
                st.secrets["SUPABASE_KEY"]
            )
        except Exception as e:
            st.error(f"🔴 Kritická chyba inicializace databáze: {e}")
            st.stop()

    def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        res = self.client.table("uzivatele").select("*, sbory(nazev_sdh)").or_(f"email.eq.{login},prezdivka.eq.{login}").execute()
        return res.data[0] if res.data else None

    def get_all_sbory(self) -> List[Dict[str, Any]]:
        return self.client.table("sbory").select("*").execute().data or []

    def insert_sbor(self, nazev: str) -> Optional[int]:
        res = self.client.table("sbory").insert({"nazev_sdh": nazev}).execute()
        return res.data[0]["id"] if res.data else None

    def register_user(self, u_data: Dict[str, Any]) -> Any:
        return self.client.table("uzivatele").insert(u_data).execute()

    def get_pokusy(self, sdh_id: int) -> List[Dict[str, Any]]:
        return self.client.table("sportovni_pokusy").select("*").eq("sbor_id", sdh_id).order("created_at", desc=True).execute().data or []

    def insert_pokus(self, p_data: Dict[str, Any]) -> Any:
        return self.client.table("sportovni_pokusy").insert(p_data).execute()

    def get_soupiska(self, sdh_id: int) -> List[Dict[str, Any]]:
        return self.client.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", sdh_id).execute().data or []

    def get_sestava(self) -> List[Dict[str, Any]]:
        return self.client.table("sestava_tymu").select("*").execute().data or []

    def upsert_sestava(self, s_data: Dict[str, Any]) -> Any:
        return self.client.table("sestava_tymu").upsert(s_data, on_conflict="uzivatel_id").execute()

    def get_material(self, sdh_id: int) -> List[Dict[str, Any]]:
        return self.client.table("sportovni_material").select("*").eq("sdh_id", sdh_id).execute().data or []

    def insert_material(self, m_data: Dict[str, Any]) -> Any:
        return self.client.table("sportovni_material").insert(m_data).execute()


# ==============================================================================
# 3. APLIKAČNÍ LOGIKA & UI ŘÍZENÍ (Pohledy / Views)
# ==============================================================================
class FireSportApp:
    def __init__(self):
        self.db = FireSportDB()
        self._init_session_state()

    def _init_session_state(self):
        defaults = {
            "logged_in": False, "user_id": None, "user_jmeno": "",
            "sdh_id": None, "sdh_nazev": "", "stranka": "🏆 Výsledky & Tréninky"
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

    def render(self):
        ThemeManager.apply_custom_theme()
        
        if not st.session_state.logged_in:
            self.render_auth_zone()
        else:
            self.render_app_zone()

    # --- AUTENTIZAČNÍ ZÓNA ---
    def render_auth_zone(self):
        st.subheader("🔥 Vítejte v systému FireSport Pro")
        st.caption("Profesionální analytický nástroj pro správu a optimalizaci útoků v požárním sportu.")
        
        tab_login, tab_reg = st.tabs(["🔒 Přihlášení do šatny", "📝 Registrace nového týmu/člena"])
        
        with tab_login:
            with st.form("auth_login_form", clear_on_submit=False):
                login = st.text_input("E-mail nebo uživatelské jméno", placeholder="pavel.proud@sdh.cz").strip()
                heslo = st.text_input("Heslo", type="password", placeholder="••••••••")
                if st.form_submit_button("Vstoupit do aplikace", type="primary", use_container_width=True):
                    if user := self.db.get_user_by_login(login):
                        if bcrypt.checkpw(heslo.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                            sbor_nazev = user["sbory"][0]["nazev_sdh"] if isinstance(user["sbory"], list) else user["sbory"].get("nazev_sdh", "Bez sboru")
                            st.session_state.update({
                                "logged_in": True, "user_id": user["id"],
                                "user_jmeno": f"{user['jmeno']} {user['prijmeni']}",
                                "sdh_id": user["sdh_id"], "sdh_nazev": sbor_nazev
                            })
                            st.rerun()
                    st.error("🔒 Neplatné přihlašovací údaje. Zkuste to znovu.")

        with tab_reg:
            with st.form("auth_reg_form"):
                typ_reg = st.radio("Způsob registrace:", ["Přidat se k existujícímu týmu", "Vytvořit zcela nový sportovní klub/tým"])
                sbory = self.db.get_all_sbory()
                sbor_dict = {s["nazev_sdh"]: s["id"] for s in sbory}
                
                sdh_id = None
                if typ_reg == "Přidat se k existujícímu týmu" and sbor_dict:
                    sdh_id = sbor_dict[st.selectbox("Vyberte tým:", list(sbor_dict.keys()))]
                else:
                    novy_sbor = st.text_input("Název nového týmu (např. SDH Lhotka - muži)").strip()

                cc1, cc2 = st.columns(2)
                jmeno = cc1.text_input("Jméno")
                prijmeni = cc2.text_input("Příjmení")
                email = st.text_input("E-mail (bude sloužit jako login)")
                heslo_raw = st.text_input("Heslo", type="password")

                if st.form_submit_button("Dokončit registraci a vytvořit účet", use_container_width=True):
                    if email and heslo_raw and jmeno and prijmeni:
                        try:
                            if typ_reg == "Vytvořit zcela nový sportovní klub/tým" and novy_sbor:
                                sdh_id = self.db.insert_sbor(novy_sbor)
                            
                            hashed = bcrypt.hashpw(heslo_raw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                            self.db.register_user({
                                "sdh_id": sdh_id, "jmeno": jmeno, "prijmeni": prijmeni, 
                                "email": email, "heslo_hash": hashed, "role": "správce"
                            })
                            st.success("🎉 Registrace dokončena! Nyní se můžete přihlásit.")
                        except Exception as e:
                            st.error(f"Chyba při zápisu registrace: {e}")

    # --- HLAVNÍ APLIKAČNÍ ZÓNA ---
    def render_app_zone(self):
        # Sidebar a profil
        with st.sidebar:
            st.markdown(f"### 🎽 {st.session_state.user_jmeno}")
            st.markdown(f"🏆 Klub: **{st.session_state.sdh_nazev}**")
            st.markdown("<span class='badge-success'>🟢 Full Access (Správce)</span>", unsafe_allow_html=True)
            st.write("")
            
            menu = ["🏆 Výsledky & Tréninky", "🏃 Soupiska & Posty", "⚡ Sportovní nářadí & Mašina"]
            volba = st.sidebar.radio("Navigace sekcí:", menu, key="stranka")
            
            st.divider()
            if st.button("Odhlásit se z kabiny", use_container_width=True, type="secondary"):
                for k in ["logged_in", "user_id", "user_jmeno", "sdh_id", "sdh_nazev"]:
                    st.session_state[k] = None
                st.session_state.logged_in = False
                st.rerun()

        # Směrování stránek
        if volba == "🏆 Výsledky & Tréninky":
            self.view_vysledky()
        elif volba == "🏃 Soupiska & Posty":
            self.view_soupiska()
        elif volba == "⚡ Sportovní nářadí & Mašina":
            self.view_naradi()

    # ==============================================================================
    # POHLED 1: VÝSLEDKY & TRÉNINKY (Pokročilá analytika, tabulky s datovými typy)
    # ==============================================================================
    def view_vysledky(self):
        st.header("🏆 Tréninkový deník & Telemetrie útoků")
        
        with st.expander("⏱️ MĚŘENÍ: ZAPSAT NOVÝ POKUS / POKROČILÁ DATA", expanded=False):
            with st.form("pokus_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                f_typ = c1.selectbox("Typ měřené aktivity", ["Trénink - Útok", "Závod - Extraliga", "Závod - Okresní liga", "Pohárová soutěž"])
                f_soutez = c2.text_input("Lokalita / Název soutěže", value="Domácí základna")
                
                cc1, cc2, cc3 = st.columns(3)
                f_voda = cc1.number_input("Čas vody / Koš (s)", min_value=0.0, max_value=60.0, value=9.50, step=0.01, format="%.2f")
                f_levy = cc2.number_input("Levý proud (s)", min_value=0.0, max_value=60.0, value=14.20, step=0.01, format="%.2f")
                f_pravy = cc3.number_input("Pravý proud (s)", min_value=0.0, max_value=60.0, value=14.50, step=0.01, format="%.2f")
                
                f_np = st.checkbox("⚠️ Neplatný pokus (NP / Nedokončeno / Diskvalifikace)")
                f_not = st.text_input("Zápis a analýza chyb (např. prostřik 0.3s vpravo, nedošlap na čáru)")
                
                if st.form_submit_button("⚡ Odeslat data do cloudu", type="primary"):
                    vysledny = max(f_levy, f_pravy) if not f_np else 0.0
                    self.db.insert_pokus({
                        "sbor_id": st.session_state.sdh_id, "typ_udalosti": f_typ, "nazev_souteze": f_soutez,
                        "cas_voda": f_voda, "cas_levy_proud": f_levy, "cas_pravy_proud": f_pravy,
                        "vysledny_cas": vysledny, "diskvalifikace": f_np, "poznamka": f_not
                    })
                    st.success("🎯 Data úspěšně uložena a zvalidována.")
                    st.rerun()

        pokusy = self.db.get_pokusy(st.session_state.sdh_id)
        if pokusy:
            df = pd.DataFrame(pokusy)
            platne = df[df["diskvalifikace"] == False]
            
            # Výkonnostní metriky (KPIs)
            m1, m2, m3 = st.columns(3)
            if not platne.empty:
                m1.metric("🏆 Rekord sezóny (Tým)", f"{platne['vysledny_cas'].min():.2f} s")
                m2.metric("⏱️ Průměrný čas útoku", f"{platne['vysledny_cas'].mean():.2f} s")
            else:
                m1.metric("🏆 Rekord sezóny (Tým)", "N/A")
                m2.metric("⏱️ Průměrný čas útoku", "N/A")
            m3.metric("🏃 Celkem pokusů", len(df))
            
            st.write("### 📊 Detailní telemetrie pokusů")
            
            # Příprava čistého DataFrame pro pokročilý st.dataframe prvek
            df["datum"] = pd.to_datetime(df["created_at"]).dt.date
            df["prostrik"] = (df["cas_levy_proud"] - df["cas_pravy_proud"]).abs()
            df["status"] = df["diskvalifikace"].map({True: "❌ Neplatný (NP)", False: "✅ Platný pokus"})
            
            ui_df = df[["datum", "typ_udalosti", "nazev_souteze", "cas_voda", "cas_levy_proud", "cas_pravy_proud", "prostrik", "vysledny_cas", "status", "poznamka"]]
            
            # Profesionální zobrazení tabulky s typováním sloupců a barvami
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
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("💡 Databáze pokusů je čistá. Zadejte první pokus výše.")

    # ==============================================================================
    # POHLED 2: SOUPISKA & POSTY (Taktická tabule a mapování relací)
    # ==============================================================================
    def view_soupiska(self):
        st.header("🏃 Sestava týmu & Taktická tabule")
        
        zavodnici = self.db.get_soupiska(st.session_state.sdh_id)
        sestava = self.db.get_sestava()
        
        zavodnici_dict = {f"{z['jmeno']} {z['prijmeni']}": z["id"] for z in zavodnici}
        sestava_dict = {s["uzivatel_id"]: s for s in sestava}
        
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
        else:
            st.warning("V databázi sboru se nenachází žádní registrovaní běžci.")

    # ==============================================================================
    # POHLED 3: SPORTOVNÍ NÁŘADÍ (Řízení inventáře a technického stavu)
    # ==============================================================================
    def view_naradi(self):
        st.header("⚡ Sklad sportovního materiálu & Speciály")
        
        with st.expander("➕ INVENTARIZACE: PŘIDAT MATERIÁL", expanded=False):
            with st.form("material_form"):
                n_nazev = st.text_input("Přesné označení nářadí", placeholder="Hadice C52 - Sport Slim (Ultra lehká)")
                c1, c2 = st.columns(2)
                n_typ = c1.selectbox("Kategorie materiálu", ["Mašina PS 12", "Hadice B", "Hadice C", "Savice", "Proudnice", "Koš", "Rozdělovač"])
                n_stav = c2.selectbox("Kondice / Nasazení", ["🔥 TOP stav (Závodní)", "🔄 Tréninková zátěž", "🛠️ V opravě / Revize"])
                n_param = st.text_input("Technické specifikace (např. délka 15.02m, gramáž 2100g, úprava motoru 2150 ccm)")
                
                if st.form_submit_button("💾 Zařadit do evidence"):
                    if n_nazev:
                        self.db.insert_material({
                            "sdh_id": st.session_state.sdh_id, "nazev": n_nazev, 
                            "kategorie": n_typ, "stav": n_stav, "parametry": n_param
                        })
                        st.success("Nářadí bylo katalogizováno.")
                        st.rerun()

        material = self.db.get_material(st.session_state.sdh_id)
        if material:
            df_mat = pd.DataFrame(material)[["kategorie", "nazev", "parametry", "stav"]]
            st.dataframe(
                df_mat,
                column_config={
                    "kategorie": st.column_config.TextColumn("Kategorie nářadí"),
                    "nazev": st.column_config.TextColumn("Název a značka"),
                    "parametry": st.column_config.TextColumn("Specifikace a rozměry"),
                    "stav": st.column_config.TextColumn("Technický stav")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Sklad nářadí je prázdný. Zaevidujte první mašinu nebo hadice.")


# ==============================================================================
# ENTRY POINT (Spouštěč aplikace)
# ==============================================================================
if __name__ == "__main__":
    app = FireSportApp()
    app.render()

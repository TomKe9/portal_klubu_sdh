import streamlit as st
import bcrypt
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
import extra_streamlit_components as stx
from streamlit_calendar import calendar

# Nastavení konfigurace stránky
st.set_page_config(page_title="🔥 FireSport Pro | Sborový Kalendář", page_icon="⚡", layout="wide")

# Mapování dnů v týdnu pro hezké zobrazení
DNY_V_TYDNU = {
    0: "Pondělí",
    1: "Úterý",
    2: "Středa",
    3: "Čtvrtek",
    4: "Pátek",
    5: "Sobota",
    6: "Neděle"
}

# ==============================================================================
# DATOVÁ VRSTVA
# ==============================================================================
class FireSportDB:
    def __init__(self):
        try:
            self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except Exception as e:
            st.error(f"🔴 Chyba inicializace Supabase (Zkontroluj st.secrets): {e}")
            st.stop()

    def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        try:
            clean_login = login.strip().lower()
            if not clean_login:
                return None
            res = self.client.table("uzivatele").select("*").or_(f"email.ilike.{clean_login},prezdivka.ilike.{clean_login}").execute()
            return res.data[0] if res.data else None
        except Exception as e:
            st.error(f"❌ Chyba při hledání uživatele v DB: {e}")
            return None

    def register_user(self, u_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            res = self.client.table("uzivatele").insert(u_data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            st.error(f"❌ Zápis uživatele do databáze selhal: {e}")
            return None

    def insert_akce(self, a_data: Dict[str, Any]) -> Any:
        try:
            return self.client.table("akce").insert(a_data).execute()
        except Exception as e:
            st.error(f"❌ Nepodařilo se uložit akci: {e}")
            return None

    def get_akce_pro_sdh(self, sdh_nazev: str) -> List[Dict[str, Any]]:
        try:
            # FILTROVÁNÍ: Načteme pouze akce patřící konkrétnímu SDH
            res = self.client.table("akce").select("*").eq("sdh", sdh_nazev).execute()
            return res.data or []
        except Exception as e:
            st.error(f"❌ Nepodařilo se načíst akce z DB: {e}")
            return []

    def delete_akce(self, akce_id: int) -> bool:
        try:
            self.client.table("akce").delete().eq("id", akce_id).execute()
            return True
        except Exception as e:
            st.error(f"❌ Nepodařilo se smazat akci z databáze: {e}")
            return False

# ==============================================================================
# POMOCNÉ FUNKCE PRO KALENDÁŘ A ŘAZENÍ
# ==============================================================================
def vygeneruj_kalendarove_udalosti(akce_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    udalosti = []
    dnes = date.today()
    
    for akce in akce_list:
        barva = "#ff4b4b" if akce["typ_akce"] == "Závod" else "#00c0f2"
        ikona = "🔥" if akce["typ_akce"] == "Závod" else "🏃‍♂️"
        
        if akce["is_opakována"]:
            target_den = akce["opakování_den_v_tydnu"]
            for i in range(-7, 28): 
                den_kontroly = dnes + timedelta(days=i)
                if den_kontroly.weekday() == target_den:
                    udalosti.append({
                        "title": f"{ikona} {akce['nazev']}",
                        "start": f"{den_kontroly.isoformat()}T{akce['cas'][:5]}",
                        "backgroundColor": barva,
                        "borderColor": barva,
                        "allDay": False
                    })
        else:
            if akce["datum_jednorazove"]:
                udalosti.append({
                    "title": f"{ikona} {akce['nazev']}",
                    "start": f"{akce['datum_jednorazove']}T{akce['cas'][:5]}",
                    "backgroundColor": barva,
                    "borderColor": barva,
                    "allDay": False
                })
    return udalosti

# ==============================================================================
# APLIKAČNÍ LOGIKA & AUTOMATICKÉ PŘIHLÁŠENÍ
# ==============================================================================
db = FireSportDB()
cookie_manager = stx.CookieManager()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_name" not in st.session_state:
    st.session_state["user_name"] = ""
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "user_sdh" not in st.session_state:
    st.session_state["user_sdh"] = ""

# Kontrola cookies pro automatické přihlášení
if not st.session_state["logged_in"]:
    saved_login = cookie_manager.get(cookie="firesport_login_remember")
    if saved_login:
        user = db.get_user_by_login(saved_login)
        if user:
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user["id"]
            st.session_state["user_name"] = f"{user['jmeno']} {user['prijmeni']}"
            st.session_state["user_sdh"] = user.get("sdh", "Nespecifikováno")
            st.rerun()

# --- OBRAZOVKA PO PŘIHLÁŠENÍ ---
if st.session_state["logged_in"]:
    
    with st.sidebar:
        st.markdown(f"### 🎽 {st.session_state['user_name']}")
        st.markdown(f"🏠 **{st.session_state['user_sdh']}**")
        st.write("---")
        menu = ["📅 Týmový Kalendář", "⚙️ Moje nastavení"]
        volba = st.radio("Sekce aplikace:", menu)
        st.write("---")
        if st.button("Odhlásit se a smazat paměť", use_container_width=True):
            cookie_manager.delete("firesport_login_remember")
            st.session_state["logged_in"] = False
            st.session_state["user_name"] = ""
            st.session_state["user_id"] = None
            st.session_state["user_sdh"] = ""
            st.rerun()

    if volba == "📅 Týmový Kalendář":
        st.title(f"📅 Kalendář akcí pro {st.session_state['user_sdh']}")
        
        col_form, col_cal = st.columns([1, 2])
        
        with col_form:
            st.subheader("➕ Nová událost sboru")
            with st.form("nova_akce_form", clear_on_submit=True):
                typ_akce = st.selectbox("Typ události", ["Trénink", "Závod"])
                nazev_akce = st.text_input("Název akce", placeholder="Např. Příprava na základně / Extraliga")
                
                vychozi_cas = datetime.combine(date.today(), datetime.min.time()).replace(hour=18, minute=0).time()
                cas_akce = st.time_input("Čas začátku", value=vychozi_cas)
                misto_akce = st.text_input("Místo", placeholder="Hasičské hřiště / Obec")
                
                is_opakovana = st.checkbox("Opakovat tuto akci pravidelně každý týden")
                
                if is_opakovana:
                    vybrany_den_nazev = st.selectbox("Vyber den v týdnu pro opakování:", list(DNY_V_TYDNU.values()), index=3)
                    opakovat_den_id = [k for k, v in DNY_V_TYDNU.items() if v == vybrany_den_nazev][0]
                    datum_jednorazove = None
                else:
                    datum_jednorazove = st.date_input("Datum akce", value=date.today())
                    opakovat_den_id = None
                
                submit_akce = st.form_submit_button("Uložit do kalendáře", type="primary", use_container_width=True)
                
            if submit_akce:
                if not nazev_akce:
                    st.error("❌ Vyplňte prosím název akce.")
                else:
                    formatovany_cas = cas_akce.strftime("%H:%M")
                    payload_akce = {
                        "vytvoril_uzivatel_id": st.session_state["user_id"],
                        "sdh": st.session_state["user_sdh"],  # Automaticky uzamčeno pod SDH uživatele
                        "typ_akce": typ_akce,
                        "nazev": nazev_akce,
                        "cas": formatovany_cas,
                        "misto": misto_akce if misto_akce else "Nespecifikováno",
                        "is_opakována": is_opakovana,
                        "datum_jednorazove": datum_jednorazove.isoformat() if datum_jednorazove else None,
                        "opakování_den_v_tydnu": opakovat_den_id
                    }
                    
                    if db.insert_akce(payload_akce):
                        st.success("🎉 Událost byla úspěšně uložena!")
                        time.sleep(0.5)
                        st.rerun()

        with col_cal:
            st.subheader("🗓️ Vizuální přehled sboru")
            # Načítáme pouze akce daného SDH
            raw_akce = db.get_akce_pro_sdh(st.session_state["user_sdh"])
            udalosti_pro_kalendar = vygeneruj_kalendarove_udalosti(raw_akce)
            
            kalendar_options = {
                "initialView": "dayGridMonth",
                "firstDay": 1, 
                "locale": "cs",
                "headerToolbar": {
                    "left": "prev,next today",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek"
                },
                "height": 450
            }
            
            calendar(events=udalosti_pro_kalendar, options=kalendar_options)

        # Seznam akcí pod kalendářem
        st.write("---")
        st.subheader("📋 Kompletní seznam akcí a správa")
        
        if not raw_akce:
            st.info(f"Zatím nejsou naplánované žádné akce pro {st.session_state['user_sdh']}.")
        else:
            col_list_op, col_list_jedn = st.columns(2)
            
            with col_list_op:
                st.markdown("#### 🔄 Pravidelné týdenní tréninky")
                opakovane = [a for a in raw_akce if a["is_opakována"]]
                opakovane.sort(key=lambda x: x["opakování_den_v_tydnu"])
                
                if opakovane:
                    for op in opakovane:
                        cc1, cc2 = st.columns([5, 1])
                        den_text = DNY_V_TYDNU.get(op["opakování_den_v_tydnu"], "Neznámý den")
                        cc1.info(f"🏃‍♂️ **{op['nazev']}** — Každý **{den_text}** v **{op['cas'][:5]}** (Místo: {op['misto']})")
                        if cc2.button("🗑️ Smazat", key=f"del_{op['id']}", use_container_width=True):
                            if db.delete_akce(op["id"]):
                                st.rerun()
                else:
                    st.caption("Žádné opakované tréninky.")
            
            with col_list_jedn:
                st.markdown("#### 📅 Jednorázové události & Závody")
                jednorazove = [a for a in raw_akce if not a["is_opakována"]]
                jednorazove.sort(key=lambda x: x["datum_jednorazove"] if x["datum_jednorazove"] else "")
                
                if jednorazove:
                    for je in jednorazove:
                        cc1, cc2 = st.columns([5, 1])
                        try:
                            datum_cz = datetime.strptime(je["datum_jednorazove"], "%Y-%m-%d").strftime("%d.%m.%Y")
                        except:
                            datum_cz = je["datum_jednorazove"]
                        ikona = "🔥" if je["typ_akce"] == "Závod" else "🏃‍♂️"
                        
                        cc1.warning(f"{ikona} **{je['nazev']}** — Dne **{datum_cz}** v **{je['cas'][:5]}** (Místo: {je['misto']})")
                        if cc2.button("🗑️ Smazat", key=f"del_{je['id']}", use_container_width=True):
                            if db.delete_akce(je["id"]):
                                st.rerun()
                else:
                    st.caption("Žádné jednorázové akce.")

    elif volba == "⚙️ Moje nastavení":
        st.title("⚙️ Moje nastavení")
        st.write(f"Tvůj profil je registrován pod: **{st.session_state['user_sdh']}**")

# --- AUTENTIZAČNÍ OBRAZOVKA (PŘIHLÁŠENÍ / REGISTRACE) ---
else:
    st.title("🔥 FireSport Pro — Ověření spojení")
    tab_login, tab_reg = st.tabs(["🔒 Přihlášení", "📝 Registrace nového účtu"])
    
    with tab_login:
        with st.form("login_form"):
            login_input = st.text_input("E-mail nebo Přezdívka").strip()
            heslo_input = st.text_input("Heslo", type="password")
            remember_me = st.checkbox("Zůstat přihlášený (na 30 dní)", value=True)
            submit_login = st.form_submit_button("Přihlásit se", type="primary")
            
        if submit_login:
            if not login_input or not heslo_input:
                st.warning("⚠️ Vyplňte obě pole.")
            else:
                user = db.get_user_by_login(login_input)
                if user:
                    if bcrypt.checkpw(heslo_input.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                        st.session_state["logged_in"] = True
                        st.session_state["user_id"] = user["id"]
                        st.session_state["user_name"] = f"{user['jmeno']} {user['prijmeni']}"
                        st.session_state["user_sdh"] = user.get("sdh", "Nespecifikováno")
                        
                        if remember_me:
                            cookie_manager.set("firesport_login_remember", login_input, max_age=2592000)
                        
                        st.success("Ověření úspěšné, načítám...")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Nesprávné heslo.")
                else:
                    st.error("❌ Účet s tímto e-mailem nebo přezdívkou neexistuje.")

    with tab_reg:
        st.subheader("Vytvořit nový testovací účet")
        with st.form("reg_form"):
            reg_jmeno = st.text_input("Jméno").strip()
            reg_prijmeni = st.text_input("Příjmení").strip()
            reg_sdh = st.text_input("Název SDH (sboru)", placeholder="Např. SDH Lhota").strip()
            reg_prezdivka = st.text_input("Přezdívka (volitelné)").strip().lower()
            reg_email = st.text_input("E-mail (bude sloužit jako login)").strip().lower()
            reg_heslo = st.text_input("Heslo", type="password")
            submit_reg = st.form_submit_button("Zaregistrovat se")
            
        if submit_reg:
            if not reg_jmeno or not reg_prijmeni or not reg_email or not reg_heslo or not reg_sdh:
                st.warning("⚠️ Vyplňte všechna povinná pole (Jméno, Příjmení, Název SDH, E-mail, Heslo).")
            else:
                hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                payload = {
                    "jmeno": reg_jmeno,
                    "prijmeni": reg_prijmeni,
                    "sdh": reg_sdh, # Uložíme název SDH k uživateli
                    "email": reg_email,
                    "prezdivka": reg_prezdivka if reg_prezdivka else None,
                    "heslo_hash": hashed
                }
                if db.register_user(payload):
                    st.success(f"🎉 Registrace pro {reg_sdh} úspěšná! Nyní se přepni na záložku Přihlášení.")

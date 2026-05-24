import streamlit as st
import bcrypt
import time
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
import extra_streamlit_components as stx

# Nastavení konfigurace stránky
st.set_page_config(page_title="🔥 FireSport Pro | Kalendář", page_icon="⚡", layout="wide")

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

    def get_vsechny_akce(self) -> List[Dict[str, Any]]:
        try:
            # Řadíme od nejnověji vytvořených
            res = self.client.table("akce").select("*").order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            st.error(f"❌ Nepodařilo se načíst akce z DB: {e}")
            return []

    # NOVÁ METODA: Smazání akce podle jejího ID
    def delete_akce(self, akce_id: int) -> bool:
        try:
            self.client.table("akce").delete().eq("id", akce_id).execute()
            return True
        except Exception as e:
            st.error(f"❌ Nepodařilo se smazat akci z databáze: {e}")
            return False

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

# Kontrola cookies pro automatické přihlášení
if not st.session_state["logged_in"]:
    saved_login = cookie_manager.get(cookie="firesport_login_remember")
    if saved_login:
        user = db.get_user_by_login(saved_login)
        if user:
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user["id"]
            st.session_state["user_name"] = f"{user['jmeno']} {user['prijmeni']}"
            st.rerun()

# --- OBRAZOVKA PO PŘIHLÁŠENÍ ---
if st.session_state["logged_in"]:
    
    # Boční panel (Sidebar)
    with st.sidebar:
        st.markdown(f"### 🎽 {st.session_state['user_name']}")
        st.write("---")
        menu = ["📅 Kalendář & Plánování", "⚙️ Moje nastavení"]
        volba = st.radio("Sekce aplikace:", menu)
        st.write("---")
        if st.button("Odhlásit se a smazat paměť", use_container_width=True):
            cookie_manager.delete("firesport_login_remember")
            st.session_state["logged_in"] = False
            st.session_state["user_name"] = ""
            st.session_state["user_id"] = None
            st.rerun()

    # --- MAIN OBSAH: SEKCE KALENDÁŘ ---
    if volba == "📅 Kalendář & Plánování":
        st.title("📅 Kalendář akcí & Tréninkový plán")
        
        col_form, col_list = st.columns([1, 2])
        
        with col_form:
            st.subheader("➕ Přidat novou událost")
            
            with st.form("nova_akce_form", clear_on_submit=True):
                typ_akce = st.selectbox("Typ události", ["Trénink", "Závod"])
                nazev_akce = st.text_input("Název akce", placeholder="Např. Příprava na základně / Extraliga")
                cas_akce = st.time_input("Čas začátku", value=datetime.now().time())
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
                    payload_akce = {
                        "vytvoril_uzivatel_id": st.session_state["user_id"],
                        "typ_akce": typ_akce,
                        "nazev": nazev_akce,
                        "cas": cas_akce.strftime("%H:%M:%S"),
                        "misto": misto_akce if misto_akce else "Nespecifikováno",
                        "is_opakována": is_opakovana,
                        "datum_jednorazove": datum_jednorazove.isoformat() if datum_jednorazove else None,
                        "opakování_den_v_tydnu": opakovat_den_id
                    }
                    
                    if db.insert_akce(payload_akce):
                        st.success("🎉 Událost byla úspěšně uložena!")
                        time.sleep(0.5)
                        st.rerun()

        with col_list:
            st.subheader("📋 Přehled naplánovaných akcí")
            akce_list = db.get_vsechny_akce()
            
            if not akce_list:
                st.info("Zatím nejsou naplánované žádné akce ani pravidelné tréninky.")
            else:
                # Rozdělení na opakované a jednorázové
                st.markdown("#### 🔄 Pravidelné týdenní tréninky / akce")
                opakovane = [a for a in akce_list if a["is_opakována"]]
                
                if opakovane:
                    for op in opakovane:
                        # Vytvoříme řádek pro akci a tlačítko na smazání vedle sebe
                        cc1, cc2 = st.columns([5, 1])
                        den_text = DNY_V_TYDNU.get(op["opakování_den_v_tydnu"], "Neznámý den")
                        cas_text = op["cas"][:5]
                        
                        cc1.info(f"🏃‍♂️ **{op['nazev']}** — Každý **{den_text}** v **{cas_text}** (Místo: {op['misto']})")
                        # Unikátní klíč (key) pro každé tlačítko pomocí ID z databáze
                        if cc2.button("🗑️ Smazat", key=f"del_{op['id']}", use_container_width=True):
                            if db.delete_akce(op["id"]):
                                st.toast(f"Akce '{op['nazev']}' smazána!")
                                time.sleep(0.5)
                                st.rerun()
                else:
                    st.caption("Žádné opakované tréninky.")
                
                st.markdown("---")
                st.markdown("#### 📅 Jednorázové události & Závody")
                jednorazove = [a for a in akce_list if not a["is_opakována"]]
                
                if jednorazove:
                    for je in jednorazove:
                        cc1, cc2 = st.columns([5, 1])
                        try:
                            datum_cz = datetime.strptime(je["datum_jednorazove"], "%Y-%m-%d").strftime("%d.%m.%Y")
                        except:
                            datum_cz = je["datum_jednorazove"]
                        cas_text = je["cas"][:5]
                        ikona = "🔥" if je["typ_akce"] == "Závod" else "🏃‍♂️"
                        
                        cc1.warning(f"{ikona} **{je['nazev']}** — Dne **{datum_cz}** v **{cas_text}** (Místo: {je['misto']})")
                        if cc2.button("🗑️ Smazat", key=f"del_{je['id']}", use_container_width=True):
                            if db.delete_akce(je["id"]):
                                st.toast(f"Akce '{je['nazev']}' smazána!")
                                time.sleep(0.5)
                                st.rerun()
                else:
                    st.caption("Žádné jednorázové akce.")

    elif volba == "⚙️ Moje nastavení":
        st.title("⚙️ Moje nastavení")
        st.write("Tady budeme moct v budoucnu upravovat profil.")

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
            reg_prezdivka = st.text_input("Přezdívka (volitelné)").strip().lower()
            reg_email = st.text_input("E-mail (bude sloužit jako login)").strip().lower()
            reg_heslo = st.text_input("Heslo", type="password")
            submit_reg = st.form_submit_button("Zaregistrovat se")
            
        if submit_reg:
            if not reg_jmeno or not reg_prijmeni or not reg_email or not reg_heslo:
                st.warning("⚠️ Vyplňte všechna povinná pole (Jméno, Příjmení, E-mail, Heslo).")
            else:
                hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                payload = {
                    "jmeno": reg_jmeno,
                    "prijmeni": reg_prijmeni,
                    "email": reg_email,
                    "prezdivka": reg_prezdivka if reg_prezdivka else None,
                    "heslo_hash": hashed
                }
                if db.register_user(payload):
                    st.success("🎉 Registrace proběhla úspěšně! Nyní se přepni na záložku Přihlášení.")

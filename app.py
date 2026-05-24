import streamlit as st
import bcrypt
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
import extra_streamlit_components as stx
from streamlit_calendar import calendar

# Konfigurace stránky
st.set_page_config(page_title="FireSport Pro | Informační systém", layout="wide")

DNY_V_TYDNU = {0: "Pondělí", 1: "Úterý", 2: "Středa", 3: "Čtvrtek", 4: "Pátek", 5: "Sobota", 6: "Neděle"}

# ==============================================================================
# DATOVÁ VRSTVA
# ==============================================================================
class FireSportDB:
    def __init__(self):
        self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

    def get_user_by_login(self, login: str):
        res = self.client.table("uzivatele").select("*").or_(f"email.ilike.{login.strip().lower()},prezdivka.ilike.{login.strip().lower()}").execute()
        return res.data[0] if res.data else Noneimport streamlit as st
import bcrypt
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
import extra_streamlit_components as stx
from streamlit_calendar import calendar

# Konfigurace stránky
st.set_page_config(page_title="FireSport Pro | Informační systém", layout="wide")

# ==============================================================================
# DATOVÁ VRSTVA
# ==============================================================================
class FireSportDB:
    def __init__(self):
        self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

    def get_user_by_login(self, login: str):
        res = self.client.table("uzivatele").select("*").or_(f"email.ilike.{login.strip().lower()},prezdivka.ilike.{login.strip().lower()}").execute()
        return res.data[0] if res.data else None

    def get_akce_pro_sdh(self, sdh: str):
        return self.client.table("akce").select("*").eq("sdh", sdh).execute().data or []

    def get_dochazka_pro_akci(self, akce_id: int):
        res = self.client.table("dochazka").select("status, uzivatel_id").eq("akce_id", akce_id).execute()
        users = self.client.table("uzivatele").select("id, jmeno, prijmeni").execute()
        user_map = {u["id"]: f"{u['jmeno']} {u['prijmeni']}" for u in users.data}
        for item in res.data:
            item["jmeno_uzivatele"] = user_map.get(item["uzivatel_id"], "Neznámý")
        return res.data

    def uloz_dochazku(self, akce_id, uzivatel_id, status):
        return self.client.table("dochazka").upsert({"akce_id": akce_id, "uzivatel_id": uzivatel_id, "status": status}, on_conflict="akce_id,uzivatel_id").execute()

    def insert_akce(self, data): return self.client.table("akce").insert(data).execute()
    def delete_akce(self, id): return self.client.table("akce").delete().eq("id", id).execute()
    def update_user_sdh(self, id, sdh): return self.client.table("uzivatele").update({"sdh": sdh}).eq("id", id).execute()

# ==============================================================================
# HLAVNÍ APLIKACE
# ==============================================================================
db = FireSportDB()
cookie_manager = stx.CookieManager()

if "logged_in" not in st.session_state: st.session_state.update({"logged_in": False})

# Automatické přihlášení
if not st.session_state["logged_in"]:
    saved = cookie_manager.get(cookie="firesport_login_remember")
    if saved:
        user = db.get_user_by_login(saved)
        if user:
            st.session_state.update({"logged_in": True, "user_id": user["id"], "user_name": f"{user['jmeno']} {user['prijmeni']}", "user_sdh": user.get("sdh", "")})
            st.rerun()

if st.session_state.get("logged_in"):
    with st.sidebar:
        st.write(f"### {st.session_state['user_name']}")
        volba = st.radio("Navigace:", ["Kalendář akcí", "Moje nastavení"])
        if st.button("Odhlásit se"):
            cookie_manager.delete("firesport_login_remember")
            st.session_state.clear()
            st.rerun()

    if volba == "Kalendář akcí":
        st.title(f"Kalendář: {st.session_state['user_sdh']}")
        c_form, c_list = st.columns([1, 2])
        
        with c_form:
            with st.form("nova"):
                typ = st.selectbox("Typ", ["Trénink", "Závod"])
                nazev = st.text_input("Název")
                datum = st.date_input("Datum")
                cas = st.time_input("Čas začátku", value=datetime.strptime("18:00", "%H:%M").time())
                if st.form_submit_button("Přidat událost"):
                    db.insert_akce({
                        "sdh": st.session_state["user_sdh"], 
                        "typ_akce": typ, 
                        "nazev": nazev, 
                        "datum_jednorazove": datum.isoformat(),
                        "cas": cas.strftime("%H:%M")
                    })
                    st.rerun()
        
        with c_list:
            akce = db.get_akce_pro_sdh(st.session_state["user_sdh"])
            for a in akce:
                with st.container(border=True):
                    # Zobrazení času, pokud existuje
                    cas_info = f"v {a.get('cas', '')}" if a.get('cas') else ""
                    st.markdown(f"#### {a['typ_akce']}: {a['nazev']} | {a.get('datum_jednorazove', '')} {cas_info}")
                    
                    d = db.get_dochazka_pro_akci(a["id"])
                    prihl = [x["jmeno_uzivatele"] for x in d if x["status"] == "Přijdu"]
                    
                    c1, c2, c3 = st.columns([1, 1, 2])
                    if c1.button("Přijdu", key=f"a{a['id']}"): db.uloz_dochazku(a['id'], st.session_state['user_id'], "Přijdu"); st.rerun()
                    if c2.button("Nepřijdu", key=f"n{a['id']}"): db.uloz_dochazku(a['id'], st.session_state['user_id'], "Nepřijdu"); st.rerun()
                    st.write(f"**Potvrzeno ({len(prihl)}):** {', '.join(prihl) if prihl else 'Nikdo'}")
                    if st.button("Smazat akci", key=f"del{a['id']}"): db.delete_akce(a['id']); st.rerun()

    elif volba == "Moje nastavení":
        novy = st.text_input("Změnit název SDH", value=st.session_state["user_sdh"])
        if st.button("Uložit"):
            db.update_user_sdh(st.session_state["user_id"], novy)
            st.session_state["user_sdh"] = novy
            st.rerun()

else:
    st.title("FireSport Pro - Přihlášení")
    with st.form("login"):
        u = st.text_input("E-mail/Přezdívka")
        p = st.text_input("Heslo", type="password")
        if st.form_submit_button("Přihlásit"):
            user = db.get_user_by_login(u)
            if user and bcrypt.checkpw(p.encode(), user["heslo_hash"].encode()):
                st.session_state.update({"logged_in": True, "user_id": user["id"], "user_name": f"{user['jmeno']} {user['prijmeni']}", "user_sdh": user.get("sdh", "")})
                cookie_manager.set("firesport_login_remember", u, max_age=2592000)
                st.rerun()

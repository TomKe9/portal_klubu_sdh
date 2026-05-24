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
        try:
            self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except Exception as e:
            st.error(f"Chyba připojení k Supabase: {e}")
            st.stop()

    def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        try:
            res = self.client.table("uzivatele").select("*").or_(f"email.ilike.{login.strip().lower()},prezdivka.ilike.{login.strip().lower()}").execute()
            return res.data[0] if res.data else None
        except: return None

    def register_user(self, u_data: Dict[str, Any]) -> Any:
        return self.client.table("uzivatele").insert(u_data).execute()

    def update_user_sdh(self, user_id: int, nový_sdh: str) -> bool:
        try:
            self.client.table("uzivatele").update({"sdh": nový_sdh}).eq("id", user_id).execute()
            return True
        except: return False

    def insert_akce(self, a_data: Dict[str, Any]) -> Any:
        return self.client.table("akce").insert(a_data).execute()

    def get_akce_pro_sdh(self, sdh_nazev: str) -> List[Dict[str, Any]]:
        return self.client.table("akce").select("*").eq("sdh", sdh_nazev).execute().data or []

    def delete_akce(self, akce_id: int) -> bool:
        try:
            self.client.table("akce").delete().eq("id", akce_id).execute()
            return True
        except: return False

    def uloz_dochazku(self, akce_id: int, uzivatel_id: int, status: str) -> bool:
        try:
            self.client.table("dochazka").upsert({"akce_id": akce_id, "uzivatel_id": uzivatel_id, "status": status}, on_conflict="akce_id,uzivatel_id").execute()
            return True
        except: return False

    # OPRAVENÁ METODA: Načte docházku a jména uživatelů samostatně
    def get_dochazka_pro_akci(self, akce_id: int) -> List[Dict[str, Any]]:
        try:
            res = self.client.table("dochazka").select("status, uzivatel_id").eq("akce_id", akce_id).execute()
            data = res.data or []
            # Samostatné načtení uživatelů pro mapování
            users = self.client.table("uzivatele").select("id, jmeno, prijmeni").execute()
            user_map = {u["id"]: {"jmeno": u["jmeno"], "prijmeni": u["prijmeni"]} for u in users.data}
            
            for item in data:
                u_info = user_map.get(item["uzivatel_id"], {"jmeno": "Neznámý", "prijmeni": "Uživatel"})
                item["uzivatele"] = u_info # Mapujeme na strukturu, kterou kód očekává
            return data
        except: return []

# ==============================================================================
# LOGIKA KALENDÁŘE
# ==============================================================================
def vygeneruj_kalendarove_udalosti(akce_list):
    udalosti = []
    dnes = date.today()
    for akce in akce_list:
        barva = "#ff4b4b" if akce["typ_akce"] == "Závod" else "#00c0f2"
        # Jednoduché zobrazení pro kalendář
        udalosti.append({
            "title": f"{akce['typ_akce']}: {akce['nazev']}",
            "start": f"{akce.get('datum_jednorazove', dnes.isoformat())}T{akce['cas'][:5]}",
            "backgroundColor": barva
        })
    return udalosti

# ==============================================================================
# HLAVNÍ APLIKACE
# ==============================================================================
db = FireSportDB()
cookie_manager = stx.CookieManager()

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "user_name": "", "user_id": None, "user_sdh": ""})

if not st.session_state["logged_in"]:
    saved = cookie_manager.get(cookie="firesport_login_remember")
    if saved:
        user = db.get_user_by_login(saved)
        if user:
            st.session_state.update({"logged_in": True, "user_id": user["id"], "user_name": f"{user['jmeno']} {user['prijmeni']}", "user_sdh": user.get("sdh", "")})
            st.rerun()

if st.session_state["logged_in"]:
    with st.sidebar:
        st.write(f"### {st.session_state['user_name']}")
        volba = st.radio("Navigace:", ["Kalendář akcí", "Moje nastavení"])
        if st.button("Odhlásit se"):
            cookie_manager.delete("firesport_login_remember")
            st.session_state.clear()
            st.rerun()

    if volba == "Kalendář akcí":
        st.title(f"Kalendář: {st.session_state['user_sdh']}")
        
        # Form a Kalendář
        col_form, col_cal = st.columns([1, 2])
        with col_form:
            with st.form("nova_akce"):
                typ = st.selectbox("Typ", ["Trénink", "Závod"])
                nazev = st.text_input("Název")
                cas = st.time_input("Čas", value=datetime.strptime("18:00", "%H:%M").time())
                datum = st.date_input("Datum")
                if st.form_submit_button("Uložit"):
                    db.insert_akce({"sdh": st.session_state["user_sdh"], "typ_akce": typ, "nazev": nazev, "cas": cas.strftime("%H:%M"), "datum_jednorazove": datum.isoformat()})
                    st.rerun()
        
        with col_cal:
            akce = db.get_akce_pro_sdh(st.session_state["user_sdh"])
            calendar(events=vygeneruj_kalendarove_udalosti(akce))

        # Výpis docházky
        st.subheader("Seznam akcí")
        for a in akce:
            with st.expander(f"{a['typ_akce']}: {a['nazev']} ({a['datum_jednorazove']})"):
                dochazka = db.get_dochazka_pro_akci(a["id"])
                
                # Tlačítka
                c1, c2, c3 = st.columns(3)
                if c1.button("Přijdu", key=f"ano_{a['id']}"): db.uloz_dochazku(a['id'], st.session_state['user_id'], "Přijdu"); st.rerun()
                if c2.button("Nepřijdu", key=f"ne_{a['id']}"): db.uloz_dochazku(a['id'], st.session_state['user_id'], "Nepřijdu"); st.rerun()
                if c3.button("Smazat", key=f"del_{a['id']}"): db.delete_akce(a['id']); st.rerun()
                
                # Výpis lidí
                prihl = [f"{d['uzivatele']['jmeno']} {d['uzivatele']['prijmeni']}" for d in dochazka if d["status"]=="Přijdu"]
                st.write(f"Potvrzeno ({len(prihl)}): {', '.join(prihl)}")

    elif volba == "Moje nastavení":
        st.title("Nastavení")
        novy_sdh = st.text_input("Změnit SDH", value=st.session_state["user_sdh"])
        if st.button("Uložit sbor"):
            db.update_user_sdh(st.session_state["user_id"], novy_sdh)
            st.session_state["user_sdh"] = novy_sdh
            st.rerun()

else:
    st.title("Přihlášení")
    with st.form("login"):
        u = st.text_input("Login")
        p = st.text_input("Heslo", type="password")
        if st.form_submit_button("Přihlásit"):
            user = db.get_user_by_login(u)
            if user and bcrypt.checkpw(p.encode(), user["heslo_hash"].encode()):
                st.session_state.update({"logged_in": True, "user_id": user["id"], "user_name": f"{user['jmeno']} {user['prijmeni']}", "user_sdh": user.get("sdh", "")})
                st.rerun()

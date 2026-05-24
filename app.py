import streamlit as st
import bcrypt
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
import extra_streamlit_components as stx
from streamlit_calendar import calendar

# Konfigurace stránky aplikace
st.set_page_config(page_title="FireSport Pro | Informační systém", layout="wide")

# Mapování dnů v týdnu pro textové zobrazení
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
# DATOVÁ VRSTVA (DATABASE ACCESS LAYER)
# ==============================================================================
class FireSportDB:
    def __init__(self):
        try:
            self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except Exception as e:
            st.error(f"Chyba inicializace databázového připojení Supabase: {e}")
            st.stop()

    def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        try:
            clean_login = login.strip().lower()
            if not clean_login:
                return None
            res = self.client.table("uzivatele").select("*").or_(f"email.ilike.{clean_login},prezdivka.ilike.{clean_login}").execute()
            return res.data[0] if res.data else None
        except Exception as e:
            st.error(f"Chyba při vyhledávání uživatele v databázi: {e}")
            return None

    def register_user(self, u_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            res = self.client.table("uzivatele").insert(u_data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            st.error(f"Zápis uživatele do databáze selhal: {e}")
            return None

    def update_user_sdh(self, user_id: int, nový_sdh: str) -> bool:
        try:
            self.client.table("uzivatele").update({"sdh": nový_sdh}).eq("id", user_id).execute()
            return True
        except Exception as e:
            st.error(f"Nepodařilo se aktualizovat sbor v databázi: {e}")
            return False

    def insert_akce(self, a_data: Dict[str, Any]) -> Any:
        try:
            return self.client.table("akce").insert(a_data).execute()
        except Exception as e:
            st.error(f"Nepodařilo se uložit akci do databáze: {e}")
            return None

    def get_akce_pro_sdh(self, sdh_nazev: str) -> List[Dict[str, Any]]:
        try:
            res = self.client.table("akce").select("*").eq("sdh", sdh_nazev).execute()
            return res.data or []
        except Exception as e:
            st.error(f"Nepodařilo se načíst akce z databáze: {e}")
            return []

    def delete_akce(self, akce_id: int) -> bool:
        try:
            self.client.table("akce").delete().eq("id", akce_id).execute()
            return True
        except Exception as e:
            st.error(f"Nepodařilo se smazat akci z databáze: {e}")
            return False

    def uloz_dochazku(self, akce_id: int, uzivatel_id: int, status: str) -> bool:
        try:
            self.client.table("dochazka").upsert(
                {"akce_id": akce_id, "uzivatel_id": uzivatel_id, "status": status},
                on_conflict="akce_id,uzivatel_id"
            ).execute()
            return True
        except Exception as e:
            st.error(f"Nepodařilo se uložit docházku: {e}")
            return False

    def get_dochazka_pro_akci(self, akce_id: int) -> List[Dict[str, Any]]:
        try:
            res = self.client.table("dochazka").select("status, uzivatele(jmeno, prijmeni, id)").eq("akce_id", akce_id).execute()
            return res.data or []
        except Exception as e:
            st.error(f"Nepodařilo se načíst docházku k akci: {e}")
            return []

# ==============================================================================
# POMOCNÉ FUNKCE PRO KALENDÁŘ A ŘAZENÍ
# ==============================================================================
def vygeneruj_kalendarove_udalosti(akce_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    udalosti = []
    dnes = date.today()
    
    for akce in akce_list:
        barva = "#ff4b4b" if akce["typ_akce"] == "Závod" else "#00c0f2"
        
        if akce["is_opakována"]:
            target_den = akce["opakování_den_v_tydnu"]
            for i in range(-7, 28): 
                den_kontroly = dnes + timedelta(days=i)
                if den_kontroly.weekday() == target_den:
                    udalosti.append({
                        "title": f"{akce['typ_akce']}: {akce['nazev']}",
                        "start": f"{den_kontroly.isoformat()}T{akce['cas'][:5]}",
                        "backgroundColor": barva,
                        "borderColor": barva,
                        "allDay": False
                    })
        else:
            if akce["datum_jednorazove"]:
                udalosti.append({
                    "title": f"{akce['typ_akce']}: {akce['nazev']}",
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

# --- OBRAZOVKA PO ÚSPĚŠNÉM PŘIHLÁŠENÍ ---
if st.session_state["logged_in"]:
    
    with st.sidebar:
        st.markdown(f"### Uživatel: {st.session_state['user_name']}")
        st.markdown(f"Sbor: **{st.session_state['user_sdh']}**")
        st.write("---")
        menu = ["Kalendář akcí", "Moje nastavení"]
        volba = st.radio("Navigace:", menu)
        st.write("---")
        if st.button("Odhlásit se", use_container_width=True):
            cookie_manager.delete("firesport_login_remember")
            st.session_state["logged_in"] = False
            st.session_state["user_name"] = ""
            st.session_state["user_id"] = None
            st.session_state["user_sdh"] = ""
            st.rerun()

    # --- SEKCE 1: KALENDÁŘ ---
    if volba == "Kalendář akcí":
        st.title(f"Kalendář plánovaných akcí: {st.session_state['user_sdh']}")
        
        col_form, col_cal = st.columns([1, 2])
        
        with col_form:
            st.subheader("Přidat novou událost")
            with st.form("nova_akce_form", clear_on_submit=True):
                typ_akce = st.selectbox("Typ události", ["Trénink", "Závod"])
                nazev_akce = st.text_input("Název akce", placeholder="Např. Příprava na základně / Extraliga")
                
                vychozi_cas = datetime.combine(date.today(), datetime.min.time()).replace(hour=18, minute=0).time()
                cas_akce = st.time_input("Čas začátku", value=vychozi_cas)
                misto_akce = st.text_input("Místo konání", placeholder="Hasičské hřiště / Areál")
                
                is_opakovana = st.checkbox("Opakovat tuto akci pravidelně každý týden")
                
                if is_opakovana:
                    vybrany_den_nazev = st.selectbox("Den v týdnu pro opakování:", list(DNY_V_TYDNU.values()), index=3)
                    opakovat_den_id = [k for k, v in DNY_V_TYDNU.items() if v == vybrany_den_nazev][0]
                    datum_jednorazove = None
                else:
                    datum_jednorazove = st.date_input("Datum akce", value=date.today())
                    opakovat_den_id = None
                
                submit_akce = st.form_submit_button("Uložit událost", type="primary", use_container_width=True)
                
            if submit_akce:
                if not nazev_akce:
                    st.error("Chyba: Vyplňte prosím název akce.")
                else:
                    formatovany_cas = cas_akce.strftime("%H:%M")
                    payload_akce = {
                        "vytvoril_uzivatel_id": st.session_state["user_id"],
                        "sdh": st.session_state["user_sdh"],
                        "typ_akce": typ_akce,
                        "nazev": nazev_akce,
                        "cas": formatovany_cas,
                        "misto": misto_akce if misto_akce else "Nespecifikováno",
                        "is_opakována": is_opakovana,
                        "datum_jednorazove": datum_jednorazove.isoformat() if datum_jednorazove else None,
                        "opakování_den_v_tydnu": opakovat_den_id
                    }
                    
                    if db.insert_akce(payload_akce):
                        st.success("Událost byla úspěšně uložena do kalendáře.")
                        time.sleep(0.5)
                        st.rerun()

        with col_cal:
            st.subheader("Grafický přehled")
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

        st.write("---")
        st.subheader("Seznam naplánovaných akcí a správa")
        
        if not raw_akce:
            st.info(f"Aktuálně nejsou naplánovány žádné akce pro sbor {st.session_state['user_sdh']}.")
        else:
            col_list_op, col_list_jedn = st.columns(2)
            
            def vykresli_polozku_akce(akce, detail_id_prefix):
                if akce["is_opakována"]:
                    den_text = DNY_V_TYDNU.get(akce["opakování_den_v_tydnu"], "Neznámý den")
                    cas_info = f"Každý den: {den_text} v {akce['cas'][:5]}"
                else:
                    try:
                        datum_cz = datetime.strptime(akce["datum_jednorazove"], "%Y-%m-%d").strftime("%d.%m.%Y")
                    except:
                        datum_cz = akce["datum_jednorazove"]
                    cas_info = f"Datum: {datum_cz} v {akce['cas'][:5]}"

                st.markdown(f"##### {akce['typ_akce']}: {akce['nazev']}")
                st.caption(f"{cas_info} | Místo: {akce['misto']}")
                
                seznam_dochazky = db.get_dochazka_pro_akci(akce["id"])
                prihlaseni = [f"{d['uzivatele']['jmeno']} {d['uzivatele']['prijmeni']}" for d in seznam_dochazky if d["status"] == "Přijdu"]
                odhlaseni = [f"{d['uzivatele']['jmeno']} {d['uzivatele']['prijmeni']}" for d in seznam_dochazky if d["status"] == "Nepřijdu"]
                
                moje_volba = "Nevyjádřeno"
                for d in seznam_dochazky:
                    if d["uzivatele"] and d["uzivatele"]["id"] == st.session_state["user_id"]:
                        moje_volba = d["status"]
                        break

                c1, c2, c3 = st.columns([2, 2, 2])
                with c1:
                    if st.button("Přijdu", key=f"ano_{detail_id_prefix}_{akce['id']}", type="secondary" if moje_volba != "Přijdu" else "primary", use_container_width=True):
                        if db.uloz_dochazku(akce["id"], st.session_state["user_id"], "Přijdu"):
                            st.rerun()
                with c2:
                    if st.button("Nepřijdu", key=f"ne_{detail_id_prefix}_{akce['id']}", type="secondary" if moje_volba != "Nepřijdu" else "primary", use_container_width=True):
                        if db.uloz_dochazku(akce["id"], st.session_state["user_id"], "Nepřijdu"):
                            st.rerun()
                with c3:
                    if st.button("Smazat akci", key=f"del_{detail_id_prefix}_{akce['id']}", use_container_width=True):
                        if db.delete_akce(akce["id"]):
                            st.rerun()

                with st.expander(f"Přehled účasti (Přijdu: {len(prihlaseni)} | Nepřijdu: {len(odhlaseni)})"):
                    col_p, col_o = st.columns(2)
                    with col_p:
                        st.markdown("**Potvrzená účast:**")
                        if prihlaseni:
                            for p in prihlaseni:
                                st.write(f"✓ {p}")
                        else:
                            st.caption("Nikdo se nepřihlásil.")
                    with col_o:
                        st.markdown("**Omluveni:**")
                        if odhlaseni:
                            for o in odhlaseni:
                                st.write(f"✗ {o}")
                        else:
                            st.caption("Nikdo se neomluvil.")
                st.write("---")

            with col_list_op:
                st.markdown("#### Pravidelné týdenní události")
                opakovane = [a for a in raw_akce if a["is_opakována"]]
                opakovane.sort(key=lambda x: x["opakování_den_v_tydnu"])
                
                if opakovane:
                    for op in opakovane:
                        vykresli_polozku_akce(op, "op")
                else:
                    st.caption("Žádné pravidelné události.")
            
            with col_list_jedn:
                st.markdown("#### Jednorázové události a závody")
                jednorazove = [a for a in raw_akce if not a["is_opakována"]]
                jednorazove.sort(key=lambda x: x["datum_jednorazove"] if x["datum_jednorazove"] else "")
                
                if jednorazove:
                    for je in jednorazove:
                        vykresli_polozku_akce(je, "jedn")
                else:
                    st.caption("Žádné jednorázové události.")

    # --- SEKCE 2: MOJE NASTAVENÍ ---
    elif volba == "Moje nastavení":
        st.title("Moje nastavení")
        st.write("Správa informací o uživatelském účtu a příslušnosti ke sboru.")
        
        st.markdown("---")
        st.subheader("Správa sboru (SDH)")
        st.info(f"Aktuálně přiřazený sbor: **{st.session_state['user_sdh']}**")
        
        with st.form("update_sdh_form"):
            novy_nazev_sdh = st.text_input("Nový nebo upravený název SDH:", value=st.session_state['user_sdh']).strip()
            st.caption("Upozornění: Ostatní členové sboru musí zadat identický název (včetně velkých/malých písmen) pro sdílení společného kalendáře.")
            submit_change = st.form_submit_button("Aktualizovat sbor", type="primary")
            
        if submit_change:
            if not novy_nazev_sdh:
                st.error("Chyba: Název sboru nesmí být prázdný.")
            else:
                if db.update_user_sdh(st.session_state["user_id"], novy_nazev_sdh):
                    st.session_state["user_sdh"] = novy_nazev_sdh
                    st.success(f"Změna uložena. Profil byl úspěšně přesunut pod sbor: {novy_nazev_sdh}")
                    time.sleep(1)
                    st.rerun()

# --- AUTENTIZAČNÍ OBRAZOVKA (PŘIHLÁŠENÍ / REGISTRACE) ---
else:
    st.title("FireSport Pro — Přístup do systému")
    tab_login, tab_reg = st.tabs(["Přihlášení k účtu", "Registrace nového účtu"])
    
    with tab_login:
        with st.form("login_form"):
            login_input = st.text_input("E-mail nebo uživatelské jméno").strip()
            heslo_input = st.text_input("Heslo", type="password")
            remember_me = st.checkbox("Zůstat přihlášen (30 dní)", value=True)
            submit_login = st.form_submit_button("Přihlásit se", type="primary")
            
        if submit_login:
            if not login_input or not heslo_input:
                st.warning("Vyplňte prosím všechna přihlašovací pole.")
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
                        
                        st.success("Ověření identity úspěšné. Načítám data...")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Chyba: Nesprávné heslo.")
                else:
                    st.error("Chyba: Účet s tímto e-mailem nebo přezdívkou neexistuje.")

    with tab_reg:
        st.subheader("Registrace nového uživatele")
        with st.form("reg_form"):
            reg_jmeno = st.text_input("Jméno").strip()
            reg_prijmeni = st.text_input("Příjmení").strip()
            reg_sdh = st.text_input("Název SDH (sboru)", placeholder="Např. SDH Lhota").strip()
            reg_prezdivka = st.text_input("Uživatelské jméno / Přezdívka (volitelné)").strip().lower()
            reg_email = st.text_input("E-mailová adresa (slouží jako přihlašovací login)").strip().lower()
            reg_heslo = st.text_input("Přístupové heslo", type="password")
            submit_reg = st.form_submit_button("Dokončit registraci")
            
        if submit_reg:
            if not reg_jmeno or not reg_prijmeni or not reg_email or not reg_heslo or not reg_sdh:
                st.warning("Vyplňte prosím všechna povinná pole (Jméno, Příjmení, Název SDH, E-mail, Heslo).")
            else:
                hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                payload = {
                    "jmeno": reg_jmeno,
                    "prijmeni": reg_prijmeni,
                    "sdh": reg_sdh,
                    "email": reg_email,
                    "prezdivka": reg_prezdivka if reg_prezdivka else None,
                    "heslo_hash": hashed
                }
                if db.register_user(payload):
                    st.success("Registrace sboru byla úspěšně dokončena. Pokračujte přihlášením.")

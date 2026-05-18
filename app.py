import streamlit as st
from supabase import create_client, Client
import bcrypt
import datetime
import base64
from PIL import Image
import io
import json
import os
import pandas as pd
import urllib.parse
from streamlit_calendar import calendar

# ==========================================
# 1. KONFIGURACE & INICIALIZACE SYSTÉMU
# ==========================================
st.set_page_config(
    page_title="Hasičský Portál JSDH / SDH", 
    page_icon="🚒", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Moderní CSS styly pro globální vzhled aplikaci (Karty, Stíny, Fonty)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stSidebar"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Moderní responzivní karty */
    .dashboard-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05), 0 1px 3px rgba(0, 0, 0, 0.02);
        border: 1px solid #f0f0f0;
        margin-bottom: 20px;
    }
    
    .poplach-card {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        border-left: 6px solid #e53935;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 25px;
    }
    
    /* Indikátory / Badges */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-success { background-color: #e8f5e9; color: #2e7d32; }
    .badge-danger { background-color: #ffebee; color: #c62828; }
    .badge-warning { background-color: #fff3e0; color: #ef6c00; }
    .badge-info { background-color: #e3f2fd; color: #1565c0; }
    
    /* Finanční widgety */
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: #1a1a1a;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_jmeno = ""
    st.session_state.user_role = "člen"
    st.session_state.sdh_id = None
    st.session_state.sdh_nazev = ""
    st.session_state.user_avatar = "🧑‍🚒"
    st.session_state.stranka = "🚨 POPLACH & Výjezd"

def nacti_trvale_prihlaseni():
    if "user_id" in st.query_params and not st.session_state.logged_in:
        u_id = st.query_params["user_id"]
        try:
            res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").eq("id", u_id).execute()
            if res.data:
                user = res.data[0]
                st.session_state.logged_in = True
                st.session_state.user_id = user["id"]
                st.session_state.user_jmeno = f"{user['jmeno']} {user['prijmeni']}"
                st.session_state.user_role = user["role"]
                st.session_state.sdh_id = user["sdh_id"]
                st.session_state.sdh_nazev = user["sbory"]["nazev_sdh"]
                st.session_state.user_avatar = ziskej_avatar_uzivatele(user["id"])
                st.session_state.stranka = "🚨 POPLACH & Výjezd"
        except Exception:
            pass

# ==========================================
# 2. POMOCNÉ FUNKCE & GRAFIKA
# ==========================================
SOUBOR_AVATARU = "profilovky_data.json"

def nacti_vsechny_avatary():
    if os.path.exists(SOUBOR_AVATARU):
        try:
            with open(SOUBOR_AVATARU, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {}
    return {}

def uloz_avatar_uzivatele(user_id, avatar_data):
    data = nacti_vsechny_avatary()
    data[str(user_id)] = avatar_data
    with open(SOUBOR_AVATARU, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def ziskej_avatar_uzivatele(user_id):
    data = nacti_vsechny_avatary()
    return data.get(str(user_id), "🧑‍🚒")

def zobraz_profilovku(avatar_data):
    if not avatar_data: return "🧑‍🚒"
    if str(avatar_data).startswith("data:image"):
        return f"""<img src="{avatar_data}" style="border-radius: 50%; width: 45px; height: 45px; object-fit: cover; vertical-align: middle; margin-right: 12px; border: 2px solid #e0e0e0;">"""
    return f"""<span style="font-size: 32px; vertical-align: middle; margin-right: 12px;">{avatar_data}</span>"""

def generuj_qr_kod_url(castka, zprava):
    iban_sboru = "CZ1234567890123456789012" 
    zprava_url = urllib.parse.quote(zprava[:20])
    return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={iban_sboru[2:]}&bankCode={iban_sboru[2:6]}&amount={castka}&currency=CZK&message={zprava_url}"

nacti_trvale_prihlaseni()

# Hlavička aplikace v čistém moderním flat stylu
st.markdown("""
<div style="padding: 10px 0px 20px 0px;">
    <h1 style="margin: 0; font-weight: 700; color: #1e1e1e;">🚒 Hasičský Portál</h1>
    <p style="margin: 5px 0 0 0; color: #666; font-size: 1.05rem;">Chytré řízení sboru a výjezdové jednotky</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 3. HLAVNÍ ROZHRANÍ & BOČNÍ PANEL
# ==========================================
if st.session_state.logged_in:
    je_spravce = False
    vlastnik_res = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=False).limit(1).execute()
    if vlastnik_res.data and vlastnik_res.data[0]["id"] == st.session_state.user_id:
        je_spravce = True

    # Uživatelská karta v bočním panelu
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    av_html = zobraz_profilovku(st.session_state.user_avatar)
    st.sidebar.markdown(f"""
    <div style="display: flex; align-items: center; background-color: #f8f9fa; padding: 12px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #eee;">
        {av_html}
        <div>
            <div style="font-weight: 600; color: #222; font-size: 1.05rem;">{st.session_state.user_jmeno}</div>
            <div style="font-size: 0.8rem; color: #e53935; font-weight: 500;">{str(st.session_state.user_role).upper()}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.sidebar.button(f"🏢 {st.session_state.sdh_nazev}", use_container_width=True, type="secondary"):
        st.session_state.stranka = "🧑‍🚒 Seznam členů sboru"
        st.rerun()
        
    if st.sidebar.button("⚙️ Moje nastavení", use_container_width=True):
        st.session_state.stranka = "Moje nastavení"
        st.rerun()
        
    st.sidebar.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
    
    kategorie_menu = {
        "🚨 AKTIVNÍ SLUŽBA & VÝJEZDY": [
            "🚨 POPLACH & Výjezd",
            "📅 Plán akcí & Docházka",
            "📑 Kniha výjezdů & Export",
            "🗺️ Mapa vodních zdrojů"
        ],
        "📦 VNITŘNÍ CHOD & MAJETEK": [
            "📢 Nástěnka sboru",
            "📦 Sklad & Výstroj OOP",
            "🎖️ Kvalifikace & Odbornost",
            "📊 Statistiky docházky",
            "🛠️ Technika & Revize",
            "🪙 Pokladna & Příspěvky",
            "🧑‍🚒 Seznam členů sboru"
        ]
    }
    
    if je_spravce:
        kategorie_menu["🛠️ ADMINISTRACE SBORU"] = ["⚙️ Správa sboru (Správce)"]

    plochy_seznam_menu = []
    for kat, polozky in kategorie_menu.items():
        plochy_seznam_menu.extend(polozky)
        
    if st.session_state.stranka == "Moje nastavení" and "Moje nastavení" not in plochy_seznam_menu:
        plochy_seznam_menu.append("Moje nastavení")

    index_menu = plochy_seznam_menu.index(st.session_state.stranka) if st.session_state.stranka in plochy_seznam_menu else 0
    volba = st.sidebar.selectbox("Navigace systému", plochy_seznam_menu, index=index_menu)
    
    if st.session_state.stranka != volba:
        st.session_state.stranka = volba
        st.rerun()
        
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    if st.sidebar.button("Odhlásit se z portálu", use_container_width=True, type="primary"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.sdh_id = None
        st.session_state.stranka = "🚨 POPLACH & Výjezd"
        if "user_id" in st.query_params: del st.query_params["user_id"]
        st.rerun()

# ==========================================
# 4. SEKCE PRO NEPŘIHLÁŠENÉ UŽIVATELE
# ==========================================
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔒 Bezpečné přihlášení", "📝 Registrace nového člena / sboru"])
    
    with tab1:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.subheader("Vstup do systému")
        login_input = st.text_input("E-mail nebo uživatelská přezdívka").strip()
        login_heslo = st.text_input("Heslo", type="password")
        zustat_prihlasen = st.checkbox("Zůstat trvale přihlášen na tomto zařízení")
        
        if st.button("Autorizovat vstup", type="primary", use_container_width=True):
            if login_input and login_heslo:
                res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").or_(f"email.eq.{login_input},prezdivka.eq.{login_input}").execute()
                if res.data:
                    user = res.data[0]
                    if bcrypt.checkpw(login_heslo.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                        st.session_state.logged_in = True
                        st.session_state.user_id = user["id"]
                        st.session_state.user_jmeno = f"{user['jmeno']} {user['prijmeni']}"
                        st.session_state.user_role = user["role"]
                        st.session_state.sdh_id = user["sdh_id"]
                        st.session_state.sdh_nazev = user["sbory"]["nazev_sdh"]
                        st.session_state.user_avatar = ziskej_avatar_uzivatele(user["id"])
                        st.session_state.stranka = "🚨 POPLACH & Výjezd"
                        if zustat_prihlasen: st.query_params["user_id"] = str(user["id"])
                        st.rerun()
                    else: st.error("Zadané heslo není správné.")
                else: st.error("Uživatel s těmito údaji neexistuje.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.subheader("Registrační formulář")
        sbory_res = supabase.table("sbory").select("*").execute()
        seznam_sboru = {s["nazev_sdh"]: s["id"] for s in sbory_res.data} if sbory_res.data else {}
        volba_sboru = st.radio("Zvolte typ registrace:", ["Přidat se k existujícímu sboru", "Zaregistrovat úplně nový sbor"])
        
        vybrany_sdh_id, novy_sbor_nazev = None, ""
        if volba_sboru == "Přidat se k existujícímu sboru":
            if seznam_sboru:
                vybrany_sbor_nazev = st.selectbox("Vyberte sbor (SDH):", list(seznam_sboru.keys()))
                vybrany_sdh_id = seznam_sboru[vybrany_sbor_nazev]
        else:
            novy_sbor_nazev = st.text_input("Název zakládaného sboru (např. SDH Lhota)").strip()
            
        reg_jmeno = st.text_input("Jméno")
        reg_prijmeni = st.text_input("Příjmení")
        reg_email = st.text_input("E-mailová adresa")
        reg_heslo = st.text_input("Přihlašovací heslo", type="password")
        pozice_na_utoku = ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"]
        vybrana_role = st.selectbox("Vaše hlavní zařazení / pozice:", pozice_na_utoku)
        
        if st.button("Odeslat registraci", type="secondary"):
            if reg_jmeno and reg_prijmeni and reg_email and reg_heslo and (vybrany_sdh_id or novy_sbor_nazev):
                try:
                    if volba_sboru == "Zaregistrovat úplně nový sbor":
                        sbor_ins = supabase.table("sbory").insert({"nazev_sdh": novy_sbor_nazev}).execute()
                        vybrany_sdh_id = sbor_ins.data[0]["id"]
                    
                    hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    supabase.table("uzivatele").insert({
                        "sdh_id": vybrany_sdh_id, "jmeno": reg_jmeno, "prijmeni": reg_prijmeni,
                        "email": reg_email, "heslo_hash": hashed, "role": vybrana_role
                    }).execute()
                    st.success("Registrace proběhla úspěšně! Nyní se můžete přihlásit v prvním tabu.")
                except Exception as e: st.error(f"Chyba při registraci: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 5. KATEGORIE: AKTIVNÍ SLUŽBA & VÝJEZDY (JSDH)
# ==========================================
elif st.session_state.logged_in:

    # --- MODUL: POPLACH & VÝJEZDOVÝ TABLET ---
    if volba == "🚨 POPLACH & Výjezd":
        st.subheader("Výjezdový monitor jednotky")
        
        if je_spravce:
            with st.expander("🚨 OPERATIVNÍ VYHLÁŠENÍ POPLACHU (Pro velitele)"):
                pop_udalost = st.text_input("Druh události (KOPIS)")
                pop_misto = st.text_input("Místo události / adresa")
                if st.button("🚨 VYHLÁSIT AKUTNÍ POPLACH", type="primary", use_container_width=True):
                    if pop_udalost:
                        supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                        supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": pop_udalost, "misto": pop_misto}).execute()
                        st.success("Poplach byl úspěšně distribuován do systému!")
                        st.rerun()

        pop_res = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
        
        if pop_res.data:
            aktivni_poplach = pop_res.data[0]
            st.markdown(f"""
            <div class="poplach-card">
                <span class="badge badge-danger" style="font-size:0.9rem; padding: 6px 12px; margin-bottom:10px;">⚠️ AKUTNÍ VÝJEZD JEDNOTKY</span>
                <h2 style="color: #c62828; margin: 5px 0; font-weight:700;">{aktivni_poplach['udalost']}</h2>
                <p style="font-size: 1.15rem; color: #333; margin: 5px 0;">📍 <b>Místo zásahu:</b> {aktivni_poplach['misto']}</p>
                <span style="color:#666; font-size:0.85rem;">Vyhlášeno v {aktivni_poplach['created_at'][11:16]} hod (Serverový čas KOPIS)</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### 🚒 Moje odezva pro velitele")
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                if st.button("🟢 Jedu na zbrojnici (IHNED)", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": "ihned"}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p2:
                cas_min = st.selectbox("Dorazím s časovou prodlevou:", ["za 5 min", "za 10 min", "za 15 min"])
                if st.button("🟡 Potvrdit s dojezdovým časem", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": cas_min}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p3:
                if st.button("🔴 Nedorazím / Mimo akceschopnost", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Nedorazím", "cas_prijezdu": None}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()

            st.markdown("<br><hr>", unsafe_allow_html=True)
            st.markdown("### 📋 Připravenost posádky v garáži")
            reakce_res = supabase.table("poplach_reakce").select("stav, cas_prijezdu, uzivatele(jmeno, prijmeni, role)").eq("poplach_id", aktivni_poplach["id"]).execute()
            
            if reakce_res.data:
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown("<div class='dashboard-card' style='border-top: 4px solid #4caf50;'>", unsafe_allow_html=True)
                    st.markdown("<h4>✅ Členové na cestě</h4>", unsafe_allow_html=True)
                    for r in reakce_res.data:
                        if r["stav"] == "Jedu na zbrojnici":
                            st.write(f"🟢 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}** ({r['uzivatele']['role']}) — `Příjezd: {r['cas_prijezdu']}`")
                    st.markdown("</div>", unsafe_allow_html=True)
                with col_g2:
                    st.markdown("<div class='dashboard-card' style='border-top: 4px solid #f44336;'>", unsafe_allow_html=True)
                    st.markdown("<h4>❌ Omluvení členové</h4>", unsafe_allow_html=True)
                    for r in reakce_res.data:
                        if r["stav"] == "Nedorazím":
                            st.write(f"🔴 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}**")
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("Zatím žádný člen jednotky nepotvrdil svou odezvu.")
                
            if je_spravce:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("❌ Lokalizovat zásah jako ukončený (Odvolat poplach)", type="secondary", use_container_width=True):
                    supabase.table("poplachy").update({"aktivni": False}).eq("id", aktivni_poplach["id"]).execute()
                    st.success("Poplachový stav byl ukončen.")
                    st.rerun()
        else:
            st.markdown("""
            <div class="dashboard-card" style="border-top: 5px solid #4caf50; background-color: #e8f5e9;">
                <h3 style="color:#2e7d32; margin:0; font-weight:600;">🎉 Vše v pořádku</h3>
                <p style="margin:5px 0 0 0; color:#388e3c;">Jednotka je aktuálně v klidu, žádný aktivní výjezd nebyl hlášen.</p>
            </div>
            """, unsafe_allow_html=True)

    # --- MODUL: PLÁN AKCÍ & DOCHÁZKA ---
    elif volba == "📅 Plán akcí & Docházka":
        st.subheader("Plán činností a kalendář sboru")
        typy_k_vyberu = ["Zásah", "Cvičení", "Soutěž", "Brigáda", "Schůze", "Jiné"]
        vybrane_typy = st.multiselect("Filtrovat typ akcí:", typy_k_vyberu, default=typy_k_vyberu)
        
        akce_res = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).order("datum").execute()
        vsechny_akce = akce_res.data if akce_res.data else []
        filtrovane_akce = [a for a in vsechny_akce if a["typ_akce"] in vybrane_typy]
        
        kalendar_udalosti = []
        barvy_akci = {"Zásah": "#d32f2f", "Cvičení": "#1976d2", "Soutěž": "#f57c00", "Brigáda": "#388e3c", "Schůze": "#7b1fa2", "Jiné": "#455a64"}
        for akce in filtrovane_akce:
            barva = barvy_akci.get(akce["typ_akce"], "#1976d2")
            kalendar_udalosti.append({
                "title": f"{akce['nazev_akce']} ({akce['cas'] if akce.get('cas') else ''})",
                "start": akce["datum"], "end": akce["datum"], "backgroundColor": barva, "borderColor": barva, "allDay": True
            })
        
        calendar(events=kalendar_udalosti, options={"headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listMonth"}, "locale": "cs", "firstDay": 1}, key="sdh_full_calendar")
        
        st.markdown("<br><hr>", unsafe_allow_html=True)
        dnes = datetime.date.today().isoformat()
        tab_budouci, tab_historie = st.tabs(["📋 Nadcházející události", "🗄️ Archiv minulých událostí"])
        
        def vykresli_akce(seznam):
            if not seznam: 
                st.info("Žádné události v této sekci.")
                return
            for akce in seznam:
                with st.expander(f"📅 {akce['datum']} - {akce['nazev_akce']} ({akce['typ_akce']})"):
                    if akce["typ_akce"] == "Zásah":
                        st.error(f"Číslo výjezdu: {akce.get('cislo_vyjezdu','')} | Použitá technika: {akce.get('pouzita_technika','')}")
                    if akce.get('poznamka'): 
                        st.info(akce['poznamka'])
                    
                    doch_res = supabase.table("dochazka").select("status").eq("akce_id", akce["id"]).eq("uzivatel_id", st.session_state.user_id).execute()
                    st.write(f"Moje nahlášená účast: **{doch_res.data[0]['status'] if doch_res.data else 'Nezadáno'}**")
                    
                    c1, c2, c3 = st.columns(3)
                    if c1.button("Jdu 👍", key=f"y_{akce['id']}", use_container_width=True):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Jdu"}, on_conflict="akce_id,uzivatel_id").execute(); st.rerun()
                    if c2.button("Nejdu 👎", key=f"n_{akce['id']}", use_container_width=True):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nejdu"}, on_conflict="akce_id,uzivatel_id").execute(); st.rerun()
                    if c3.button("Nevím 🤷", key=f"m_{akce['id']}", use_container_width=True):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nevím"}, on_conflict="akce_id,uzivatel_id").execute(); st.rerun()

        with tab_budouci: vykresli_akce([a for a in filtrovane_akce if a["datum"] >= dnes])
        with tab_historie: vykresli_akce([a for a in filtrovane_akce if a["datum"] < dnes])

    # --- MODUL: KNIHA VÝJEZDŮ & EXPORT ---
    elif volba == "📑 Kniha výjezdů & Export":
        st.subheader("Přehled ostrých zásahů jednotky")
        zasahy_res = supabase.table("akce").select("datum, cas, nazev_akce, cislo_vyjezdu, pouzita_technika, motohodiny_uziti, poznamka").eq("sdh_id", st.session_state.sdh_id).eq("typ_akce", "Zásah").order("datum", desc=True).execute()
        if zasahy_res.data:
            df_zasahy = pd.DataFrame(zasahy_res.data)
            df_zasahy.columns = ["Datum", "Čas", "Událost zásahu", "Číslo výjezdu KOPIS", "Technika", "Mth / Km", "Poznámka k zásahu"]
            st.dataframe(df_zasahy, use_container_width=True)
            st.download_button("📥 Exportovat knihu výjezdů (CSV)", data=df_zasahy.to_csv(index=False, encoding="utf-8-sig"), file_name="kniha_vyjezdu.csv", mime="text/csv", type="secondary")
        else: st.info("V databázi sboru nejsou evidovány žádné ostré zásahy.")

    # --- MODUL: MAPA VODNÍCH ZDROJŮ ---
    elif volba == "🗺️ Mapa vodních zdrojů":
        st.subheader("Statická hydrantová síť a vodní zdroje")
        if je_spravce:
            with st.expander("➕ Zadat nový vodní zdroj do mapy"):
                v_nazev = st.text_input("Popis lokace / název bodu")
                v_typ = st.selectbox("Typ zdroje", ["Nadzemní hydrant", "Podzemní hydrant", "Požární nádrž", "Přírodní zdroj"])
                v_stav = st.selectbox("Provozní funkčnost", ["Funkční", "Nefunkční", "V opravě"])
                v_lat = st.number_input("Zeměpisná šířka (Latitude)", format="%.5f")
                v_lon = st.number_input("Zeměpisná délka (Longitude)", format="%.5f")
                if st.button("Uložit bod do systému", type="primary"):
                    try:
                        supabase.table("vodni_zdroje").insert({"sdh_id": st.session_state.sdh_id, "nazev": v_nazev, "typ": v_typ, "stav": v_stav, "latitude": v_lat, "longitude": v_lon}).execute()
                        st.success("Bod byl zanesen."); st.rerun()
                    except Exception as e: st.error(f"Chyba zápisu: {e}")
                    
        try:
            zdroje_res = supabase.table("vodni_zdroje").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
            if zdroje_res.data:
                st.map(pd.DataFrame(zdroje_res.data), latitude="latitude", longitude="longitude")
                st.markdown("<br><h4>📋 Seznam bodů hasební vody</h4>", unsafe_allow_html=True)
                for z in zdroje_res.data:
                    badge_style = "badge-success" if z['stav'] == "Funkční" else "badge-danger"
                    st.markdown(f"""
                    <div class='dashboard-card' style='padding: 12px; margin-bottom: 8px;'>
                        📍 <b>{z['nazev']}</b> ({z['typ']}) — <span class='badge {badge_style}'>{z['stav']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else: st.info("Zatím nebyly zaneseny žádné body vodních zdrojů.")
        except Exception as e: st.error(f"Chyba komunikace s mapovým serverem: {e}")

# ==========================================
# 6. KATEGORIE: VNITŘNÍ CHOD SBORU & MAJETEK (SDH)
# ==========================================
    # --- MODUL: SBOREVOVÁ NÁSTĚNKA ---
    elif volba == "📢 Nástěnka sboru":
        st.subheader("Aktuální oznámení a sborová vývěska")
        if je_spravce:
            with st.expander("📌 Publikovat nové oznámení na nástěnku"):
                nadpis_zpr = st.text_input("Nadpis zprávy")
                text_zpr = st.text_area("Obsah sdělení")
                priorita = st.checkbox("Označit jako DŮLEŽITÉ / KRITICKÉ")
                if st.button("Vyvěsit zprávu", type="primary"):
                    try:
                        supabase.table("nastenka").insert({"sdh_id": st.session_state.sdh_id, "autor_jmeno": st.session_state.user_jmeno, "nadpis": nadpis_zpr, "text": text_zpr, "dulezite": priorita}).execute()
                        st.success("Zpráva byla úspěšně vyvěšena."); st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")
                    
        try:
            zpravy_res = supabase.table("nastenka").select("*").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=True).execute()
            st.markdown("<br>", unsafe_allow_html=True)
            for z in (zpravy_res.data if zpravy_res.data else []):
                border_color = "#e53935" if z["dulezite"] else "#e0e0e0"
                badge_html = "<span class='badge badge-danger' style='margin-bottom:8px;'>🚨 DŮLEŽITÉ</span>" if z["dulezite"] else ""
                st.markdown(f"""
                <div class="dashboard-card" style="border-left: 5px solid {border_color};">
                    {badge_html}
                    <h3 style="margin: 0 0 8px 0; font-weight:600;">{z['nadpis']}</h3>
                    <p style="color: #333; font-size:1rem; line-height:1.5;">{z['text']}</p>
                    <hr style="border:0; border-top:1px solid #f0f0f0; margin: 10px 0;">
                    <span style="font-size:0.8rem; color:#777;">Autor: <b>{z['autor_jmeno']}</b> | Publikováno v systému</span>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e: st.error(f"Chyba načítání nástěnky: {e}")

    # --- MODUL: SKLAD & VÝSTROJ ---
    elif volba == "📦 Sklad & Výstroj OOP":
        st.subheader("Skladové hospodářství a osobní výstroj")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute()
        slovnik_clenu_sklad = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cl_res.data} if cl_res.data else {}
        
        t_moje, t_sklad = st.tabs(["🎒 Moje přidělená výstroj", "🔧 Komplexní správa skladu"])
        with t_moje:
            moje_oop = supabase.table("sklad").select("*").eq("prideleno_uzivatel_id", st.session_state.user_id).execute()
            if moje_oop.data:
                for item in moje_oop.data:
                    st.markdown(f"""
                    <div class='dashboard-card' style='border-left: 4px solid #1565c0; padding:15px;'>
                        <span style='font-size:1.1rem; font-weight:600;'>🧥 {item['nazev']}</span> <br>
                        <span style='color:#555; font-size:0.9rem;'>Evidovaná velikost: <b>{item['velikost']}</b></span>
                    </div>
                    """, unsafe_allow_html=True)
            else: st.info("Nemáte aktuálně zapsanou žádnou osobní výstroj ve skladu.")
                
        with t_sklad:
            if je_spravce:
                with st.expander("➕ Zaevidovat novou položku do skladu"):
                    n_mat = st.text_input("Název materiálu / výstroje (např. Zásahový kabát Bushfire)")
                    n_vel = st.text_input("Velikostní specifikace (např. XL / 52)")
                    n_uziv = st.selectbox("Přidělení konkrétnímu členovi sboru:", ["Ponechat volně skladem"] + list(slovnik_clenu_sklad.keys()))
                    if st.button("Uložit položku do majetku"):
                        p_id = None if n_uziv == "Ponechat volně skladem" else slovnik_clenu_sklad[n_uziv]
                        supabase.table("sklad").insert({"sdh_id": st.session_state.sdh_id, "nazev": n_mat, "velikost": n_vel, "stav": "V pořádku", "prideleno_uzivatel_id": p_id}).execute()
                        st.success("Položka byla úspěšně naskladněna."); st.rerun()
            
            vsechen_sklad = supabase.table("sklad").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).execute()
            st.markdown("<br><h4>📋 Celkový přehled inventáře skladu</h4>", unsafe_allow_html=True)
            for i in (vsechen_sklad.data if vsechen_sklad.data else []):
                if i.get('uzivatele'):
                    status_html = f"<span class='badge badge-info'>👤 Vydáno: {i['uzivatele']['jmeno']} {i['uzivatele']['prijmeni']}</span>"
                else:
                    status_html = "<span class='badge badge-success'>📦 Skladem</span>"
                    
                st.markdown(f"""
                <div class='dashboard-card' style='padding:12px; margin-bottom:8px;'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <span><b>{i['nazev']}</b> (Velikost: {i['velikost']})</span>
                        {status_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # --- MODUL: KVALIFIKACE & ODBORNOST ---
    elif volba == "🎖️ Kvalifikace & Odbornost":
        st.subheader("Hlídač platnosti licencí a odborných způsobilostí")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute()
        slovnik_hasicu = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cl_res.data} if cl_res.data else {}
        
        if je_spravce:
            with st.expander("➕ Zapsat nebo prodloužit kvalifikaci členovi"):
                k_hasic = st.selectbox("Vyberte hasiče:", list(slovnik_hasicu.keys()))
                k_typ = st.selectbox("Typ osvědčení / kurz", ["Zdravotní prohlídka", "Nositel dýchací techniky (NDT)", "Strojník JSDH", "Velitel družstva / sboru"])
                k_datum = st.date_input("Termín platnosti DO:")
                if st.button("Aktualizovat kvalifikaci", type="primary"):
                    supabase.table("kvalifikace").upsert({"uzivatel_id": slovnik_hasicu[k_hasic], "typ_kurzu": k_typ, "platnost_do": str(k_datum)}, on_conflict="uzivatel_id,typ_kurzu").execute()
                    st.success("Údaje o kvalifikaci byly zapsány."); st.rerun()
                    
        vsechny_kval = supabase.table("kvalifikace").select("*, uzivatele(jmeno, prijmeni, sdh_id)").execute()
        filtrovane_kval = [k for k in vsechny_kval.data if k.get("uzivatele") and k["uzivatele"]["sdh_id"] == st.session_state.sdh_id] if vsechny_kval.data else []
        dnesni_den = datetime.date.today()
        
        st.markdown("<br>", unsafe_allow_html=True)
        for k in filtrovane_kval:
            p_do = datetime.datetime.strptime(k["platnost_do"], "%Y-%m-%d").date()
            if p_do < dnesni_den:
                st.markdown(f"""
                <div class='dashboard-card' style='border-left: 5px solid #d32f2f; background-color: #fff8f8;'>
                    ❌ <b>{k['uzivatele']['jmeno']} {k['uzivatele']['prijmeni']}</b> — <span class='badge badge-danger'>{k['typ_kurzu']}</span> <br>
                    <span style='color:#c62828; font-size:0.9rem;'><b>PROPADLÁ PLATNOST!</b> (Skončilo: {p_do.strftime('%d.%m.%Y')})</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='dashboard-card' style='border-left: 5px solid #388e3c;'>
                    🟢 <b>{k['uzivatele']['jmeno']} {k['uzivatele']['prijmeni']}</b> — <span class='badge badge-success'>{k['typ_kurzu']}</span> <br>
                    <span style='color:#555; font-size:0.9rem;'>Platné osvědčení do: <b>{p_do.strftime('%d.%m.%Y')}</b></span>
                </div>
                """, unsafe_allow_html=True)

    # --- MODUL: STATISTIKY DOCHÁZKY ---
    elif volba == "📊 Statistiky docházky":
        st.subheader("Statistické vyhodnocení docházkové úspěšnosti")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute()
        celkem_akci = supabase.table("akce").select("id", count="exact").eq("sdh_id", st.session_state.sdh_id).execute().count or 0
        
        if celkem_akci > 0 and cl_res.data:
            for clen in cl_res.data:
                u_doch = supabase.table("dochazka").select("status").eq("uzivatel_id", clen["id"]).eq("status", "Jdu").execute()
                pocet_jdu = len(u_doch.data) if u_doch.data else 0
                procento = round((pocet_jdu / celkem_akci) * 100, 1)
                
                st.markdown(f"**🚒 {clen['jmeno']} {clen['prijmeni']}** ({clen['role']}) — Účast: **{pocet_jdu} z {celkem_akci} akcí** (`{procento} %`)")
                st.progress(min(int(procento), 100))
                st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)

    # --- MODUL: TECHNIKA & REVIZE ---
    elif volba == "🛠️ Technika & Revize":
        st.subheader("Evidence techniky a sledování STK / Revizí")
        if je_spravce:
            with st.expander("➕ Přidat nový vůz nebo agregát do správy"):
                t_nazev = st.text_input("Identifikace a název vozidla/stroje (např. CAS 20 Scania)")
                t_revize = st.date_input("Termín příští STK / revize zařízení:")
                if st.button("Zařadit techniku do sboru"):
                    supabase.table("technika").insert({"sdh_id": st.session_state.sdh_id, "nazev": t_nazev, "typ": "Vozidlo", "stk_revize": str(t_revize), "stav": "V pořádku"}).execute()
                    st.rerun()
                    
        tech_res = supabase.table("technika").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
        st.markdown("<br>", unsafe_allow_html=True)
        for t in (tech_res.data if tech_res.data else []):
            st.markdown(f"""
            <div class='dashboard-card' style='border-top: 4px solid #1565c0;'>
                <h3 style='margin:0 0 5px 0;'>🚒 {t['nazev']}</h3>
                <span style='font-size:0.95rem; color:#444;'>Příští revizní kontrola / STK: <b>{t['stk_revize']}</b></span>
            </div>
            """, unsafe_allow_html=True)

    # --- MODUL: POKLADNA & PŘÍSPĚVKY ---
    elif volba == "🪙 Pokladna & Příspěvky":
        st.subheader("Finanční správa, pokladní deník a členské příspěvky")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute()
        slovnik_clenu_pocka = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cl_res.data} if cl_res.data else {}
        
        tab_p_prehled, tab_p_zadat, tab_p_qr = st.tabs(["📊 Finanční přehled a deník", "🪙 Zápis účetního dokladu", "📱 Úhrada členských příspěvků QR kódem"])
        
        with tab_p_prehled:
            trans_res = supabase.table("pokladna").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
            vsechny_trans = trans_res.data if trans_res.data else []
            
            prijmy = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Příjem")
            vydaje = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Výdaj")
            zustatek = prijmy - vydaje
            
            # Moderní HTML Finanční Widgety
            w_c1, w_c2, w_c3 = st.columns(3)
            with w_c1:
                st.markdown(f"<div class='dashboard-card'><span style='color:#2e7d32; font-weight:500;'>📈 CELKOVÉ PŘÍJMY</span><div class='metric-value' style='color:#2e7d32;'>{prijmy:,.2f} Kč</div></div>".replace(",", " "), unsafe_allow_html=True)
            with w_c2:
                st.markdown(f"<div class='dashboard-card'><span style='color:#c62828; font-weight:500;'>📉 CELKOVÉ VÝDAJE</span><div class='metric-value' style='color:#c62828;'>{vydaje:,.2f} Kč</div></div>".replace(",", " "), unsafe_allow_html=True)
            with w_c3:
                color_z = "#1565c0" if zustatek >= 0 else "#c62828"
                st.markdown(f"<div class='dashboard-card'><span style='color:{color_z}; font-weight:500;'>🪙 AKTUÁLNÍ BILANCE (ZŮSTATEK)</span><div class='metric-value' style='color:{color_z};'>{zustatek:,.2f} Kč</div></div>".replace(",", " "), unsafe_allow_html=True)
            
            st.markdown("<br><h4>📋 Chronologická historie transakcí</h4>", unsafe_allow_html=True)
            if vsechny_trans:
                df_p = pd.DataFrame(vsechny_trans)
                df_p = df_p[["created_at", "smer", "castka", "typ_platby", "poznamka"]]
                df_p.columns = ["Účetní datum", "Směr", "Částka (Kč)", "Kategorie", "Interní poznámka"]
                st.dataframe(df_p, use_container_width=True)
            else: st.info("Sbor nemá prozatím zaznamenané žádné účetní pohyby.")
            
        with tab_p_zadat:
            if je_spravce:
                st.subheader("Vložení nového příjmového / výdajového dokladu")
                t_smer = st.radio("Účetní operace:", ["Příjem", "Výdaj"])
                t_castka = st.number_input("Dokladová částka v Kč", min_value=1.0)
                t_typ = st.selectbox("Kategorie účetního případu", ["Příspěvek", "Dotace sboru", "Nákup materiálu", "Občerstvení / Akce", "Jiné"])
                t_hasic = st.selectbox("Spárovat se členem sboru (volitelné):", ["Ponechat bez vazby na člena"] + list(slovnik_clenu_pocka.keys()))
                t_pozn = st.text_input("Účetní popis transakce (např. Členský příspěvek na rok 2026)")
                
                if st.button("Zavést doklad do účetnictví", type="primary"):
                    h_id = None if t_hasic == "Ponechat bez vazby na člena" else slovnik_clenu_pocka[t_hasic]
                    rok_prispevku = datetime.date.today().year if t_typ == "Příspěvek" else None
                    supabase.table("pokladna").insert({
                        "sdh_id": st.session_state.sdh_id, "uzivatel_id": h_id, "castka": t_castka,
                        "typ_platby": t_typ, "smer": t_smer, "poznamka": t_pozn, "zaplaceno_rok": rok_prispevku
                    }).execute()
                    st.success("Účetní položka byla bezpečně uložena!"); st.rerun()
            else: st.info("Zápis transakcí do sborové pokladny může provádět pouze oprávněný hospodář, velitel nebo správce.")
            
        with tab_p_qr:
            st.subheader("📱 Rychlé digitální vyrovnání členských příspěvků")
            st.write("Naskenujte kód přímo ve své mobilní bankovní aplikaci. Platba obsahuje automaticky nastavené údaje pro sborový účet.")
            
            castka_prispevku = st.number_input("Aktuální roční příspěvek stanovený výborem (Kč):", value=500)
            zprava_platce = f"SDH Prispevek {st.session_state.user_jmeno}"
            
            qr_url = generuj_qr_kod_url(castka_prispevku, zprava_platce)
            col_qr1, col_qr2 = st.columns([1, 2])
            with col_qr1: st.image(qr_url, caption="Automaticky generovaný QR kód", width=260)
            with col_qr2:
                st.markdown(f"""
                <div class='dashboard-card' style='background-color:#f9f9f9;'>
                    <b>Platební parametry příkazu:</b><br><br>
                    💰 <b>Částka k úhradě:</b> {castka_prispevku} Kč <br>
                    📝 <b>Zpráva pro příjemce:</b> <code>{zprava_platce}</code>
                </div>
                """, unsafe_allow_html=True)
                st.info("💡 Po připsání peněz na účet sboru vám hospodář ručně potvrdí platbu v pokladním přehledu.")

    # --- MODUL: SEZNAM ČLENŮ ---
    elif volba == "🧑‍🚒 Seznam členů sboru":
        st.subheader("Adresář a seznam členů sboru")
        clenove_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, prezdivka, role").eq("sdh_id", st.session_state.sdh_id).execute()
        st.markdown("<br>", unsafe_allow_html=True)
        for c in (clenove_res.data if clenove_res.data else []):
            st.markdown(f"""
            <div class='dashboard-card' style='padding:14px; margin-bottom:8px;'>
                🧑‍🚒 <b>{c['jmeno']} {c['prijmeni']}</b> {f'({c["prezdivka"]})' if c['prezdivka'] else ''} — Pozice ve sboru: <span class='badge badge-info'>{c['role']}</span>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# 7. KATEGORIE: ADMINISTRACE & NASTAVENÍ
# ==========================================
    # --- MODUL: MOJE NASTAVENÍ ---
    elif volba == "Moje nastavení":
        st.subheader("Osobní profil a konfigurace účtu")
        u_aktualni = supabase.table("uzivatele").select("prezdivka, role, email").eq("id", st.session_state.user_id).execute()
        strav_avatar = ziskej_avatar_uzivatele(st.session_state.user_id)
        
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        typ_avataru = st.radio("Způsob reprezentace profilové ikony:", ["Výběr Emoji", "Nahrání vlastní fotografie"])
        vysledny_avatar = strav_avatar
        if typ_avataru == "Výběr Emoji": 
            vysledny_avatar = st.text_input("Zadejte preferované emoji:", value=strav_avatar if not str(strav_avatar).startswith("data:image") else "🧑‍🚒", max_chars=5)
        else:
            file = st.file_uploader("Nahrát fotografii z lokálního úložiště (čtvercový ořez ideální):", type=["png", "jpg", "jpeg"])
            if file:
                img = Image.open(file).convert("RGB"); img.thumbnail((120, 120))
                buf = io.BytesIO(); img.save(buf, format="PNG")
                vysledny_avatar = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
        
        nova_prez = st.text_input("Moje sborová přezdívka (volitelné):", value=u_aktualni.data[0]["prezdivka"] if u_aktualni.data and u_aktualni.data[0]["prezdivka"] else "")
        novy_email = st.text_input("Osobní komunikační e-mail:", value=u_aktualni.data[0]["email"] if u_aktualni.data else "")
        
        if st.button("Uložit změny v mém profilu", type="primary", use_container_width=True):
            supabase.table("uzivatele").update({"email": novy_email, "prezdivka": nova_prez if nova_prez else None}).eq("id", st.session_state.user_id).execute()
            uloz_avatar_uzivatele(st.session_state.user_id, vysledny_avatar)
            st.session_state.user_avatar = vysledny_avatar
            st.success("Změny profilu byly bezpečně uloženy!"); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # --- MODUL: ADMINISTRATION ---
    elif volba == "⚙️ Správa sboru (Správce)":
        st.subheader("Hlavní administrátorský a velitelský modul")
        t_adm_akce, t_adm_clen, t_adm_hes = st.tabs(["➕ Plánování nové akce / Výjezdu", "⚙️ Práva a správa členů", "🔐 Nouzový reset hesel"])
        
        with t_adm_akce:
            st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
            st.subheader("Vytvořit událost do kalendáře")
            n_nazev = st.text_input("Název chystané události")
            n_typ = st.selectbox("Charakter akce", ["Zásah", "Cvičení", "Brigáda", "Schůze", "Soutěž"])
            c_v, p_t, m_h = "", "", ""
            if n_typ == "Zásah":
                c_v = st.text_input("Číslo operačního výjezdu (KOPIS)")
                p_t = st.text_input("Nasazená mobilní technika")
                m_h = st.text_input("Vykázané motohodiny celkem")
            n_dat = st.date_input("Datum konání")
            n_cas = st.text_input("Čas zahájení (např. 17:00)")
            n_poz = st.text_area("Detailní instrukce k události")
            if st.button("Závazně publikovat do kalendáře", type="primary"):
                supabase.table("akce").insert({"sdh_id": st.session_state.sdh_id, "datum": str(n_dat), "cas": n_cas, "nazev_akce": n_nazev, "typ_akce": n_typ, "poznamka": n_poz, "cislo_vyjezdu": c_v if c_v else None, "pouzita_technika": p_t if p_t else None, "motohodiny_uziti": m_h if m_h else None}).execute()
                st.success("Událost byla propisována do kalendářů všech členů!"); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
                
        with t_adm_clen:
            st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
            cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute()
            if cl_res.data:
                slovnik_clenu = {f"{u['jmeno']} {u['prijmeni']} ({u['role']})": u for u in cl_res.data}
                vybrany = slovnik_clenu[st.selectbox("Vyberte člena k úpravě zařazení:", list(slovnik_clenu.keys()))]
                n_role_adm = st.selectbox("Přiřadit novou organizační roli:", ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"])
                if st.button("Změnit roli člena", type="primary"):
                    supabase.table("uzivatele").update({"role": n_role_adm}).eq("id", vybrany["id"]).execute()
                    st.success("Zařazení člena bylo změněno."); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
                    
        with t_adm_hes:
            st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
            st.subheader("Nouzový přepis přihlašovacího hesla")
            if cl_res.data:
                slovnik_hesla = {f"{u['jmeno']} {u['prijmeni']}": u for u in cl_res.data}
                u_reset = slovnik_hesla[st.selectbox("Vyberte člena pro generování nového hesla:", list(slovnik_hesla.keys()))]
                p_vstup = st.text_input("Nové přihlašovací heslo uživatele:", type="password")
                if st.button("Provést nucenou změnu hesla", type="primary"):
                    h_novy = bcrypt.hashpw(p_vstup.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    supabase.table("uzivatele").update({"heslo_hash": h_novy}).eq("id", u_reset["id"]).execute()
                    st.success("Heslo uživatele bylo úspěšně přepsáno."); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

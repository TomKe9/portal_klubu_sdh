import streamlit as st
from supabase import create_client, Client
import bcrypt
import datetime
import json
import os
import re
import urllib.parse
from streamlit_calendar import calendar

# ==========================================
# 1. MODERNÍ MINIMALISTICKÝ DESIGN (ČISTÝ STYL)
# ==========================================
st.set_page_config(
    page_title="RESQ Portal", 
    page_icon="🚨", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Profesionální tmavý design s modrými akcenty (bez sci-fi prvků)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Globální font a pozadí */
    html, body, [data-testid="stSidebar"], .stApp {
        font-family: 'Inter', sans-serif;
        background-color: #0f172a !important; /* Elegantní tmavě modro-šedá */
        color: #f1f5f9 !important;
    }
    
    /* Elegantní čisté karty pro obsah */
    .premium-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s, border-color 0.2s;
    }
    .premium-card:hover {
        border-color: #3b82f6;
    }
    
    /* Výrazná, ale čistá karta pro aktivní poplach */
    .emergency-pulse {
        background: linear-gradient(135deg, #451a03 0%, #1e293b 100%);
        border: 2px solid #ea580c; /* Oranžovo-červená pro emergency */
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    }
    
    /* Profesionální stavové štítky */
    .cyber-badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-alert { background-color: #7f1d1d; color: #fca5a5; }
    .badge-ok { background-color: #064e3b; color: #6ee7b7; }
    .badge-neutral { background-color: #1e3a8a; color: #93c5fd; }
    
    /* Stylizace formulářů */
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea, select {
        background-color: #0f172a !important;
        color: #ffffff !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
    }
    
    /* Čisté záložky (Tabs) */
    button[data-baseweb="tab"] {
        color: #94a3b8 !important;
        font-size: 0.95rem !important;
    }
    button[aria-selected="true"] {
        color: #3b82f6 !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SPRÁVA COOKIES (TRVALÉ PŘIHLÁŠENÍ)
# ==========================================
def nacti_trvale_prihlaseni():
    """Načte uložené cookies a automaticky přihlásí uživatele."""
    if "token_uzivatele" in st.context.cookies and not st.session_state.get("logged_in"):
        try:
            token_data = st.context.cookies["token_uzivatele"]
            user_id = int(token_data)
            res = supabase.table("uzivatele").select("*").eq("id", user_id).execute()
            if res.data:
                user = res.data[0]
                sdh_nazev_db, sdh_iban_db = "Neznámý sbor", "CZ1234567890123456789012"
                if user.get("sdh_id"):
                    sbor_res = supabase.table("sbory").select("*").eq("id", user["sdh_id"]).execute()
                    if sbor_res.data:
                        sdh_nazev_db = sbor_res.data[0].get("nazev_sdh", sbor_res.data[0].get("nazev", "Sbor bez názvu"))
                        sdh_iban_db = sbor_res.data[0].get("iban", "CZ1234567890123456789012")
                
                st.session_state.logged_in = True
                st.session_state.user_id = user["id"]
                st.session_state.user_jmeno = f"{user['jmeno']} {user['prijmeni']}"
                st.session_state.user_role = user["role"]
                st.session_state.user_schvalen = user.get("schvalen", True)
                st.session_state.sdh_id = user["sdh_id"]
                st.session_state.sdh_nazev = sdh_nazev_db
                st.session_state.sdh_iban = sdh_iban_db
                st.session_state.user_avatar = ziskej_avatar_uzivatele(user["id"])
        except Exception:
            pass

# Inicializace session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_jmeno = ""
    st.session_state.user_role = "člen"
    st.session_state.user_schvalen = False
    st.session_state.sdh_id = None
    st.session_state.sdh_nazev = ""
    st.session_state.sdh_iban = "CZ1234567890123456789012"
    st.session_state.user_avatar = "🧑‍🚒"

SOUBOR_AVATARU = "profilovky_data.json"

def nacti_vsechny_avatary():
    if os.path.exists(SOUBOR_AVATARU):
        try:
            with open(SOUBOR_AVATARU, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {}
    return {}

def ziskej_avatar_uzivatele(user_id):
    return nacti_vsechny_avatary().get(str(user_id), "🧑‍🚒")

def uloz_avatar_uzivatele(user_id, avatar_data):
    data = nacti_vsechny_avatary()
    data[str(user_id)] = avatar_data
    with open(SOUBOR_AVATARU, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase: Client = init_connection()

# Spuštění kontroly cookies hned na začátku
nacti_trvale_prihlaseni()

def zobraz_profilovku(avatar_data):
    return f"""<span style="font-size: 28px; background: rgba(255,255,255,0.05); padding: 6px 10px; border-radius: 8px; margin-right: 12px; border: 1px solid rgba(255,255,255,0.1);">{avatar_data}</span>"""

def generuj_qr_kod_url(iban, castka, zprava):
    cistý_iban = re.sub(r'\s+', '', iban)
    zprava_url = urllib.parse.quote(zprava[:20])
    return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={cistý_iban[2:]}&bankCode={cistý_iban[2:6]}&amount={castka}&currency=CZK&message={zprava_url}"

# PŮVODNÍ ČISTÉ HLAVIČKOVÉ MENU (Bez podtržítek a falešných kódů)
st.markdown("""
<div style="padding-bottom: 15px; margin-bottom: 25px; border-bottom: 1px solid #334155;">
    <h1 style="margin: 0; font-weight: 700; font-size: 2rem; color: #ffffff;">RESQ Portal</h1>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 3. PŘIHLAŠOVÁNÍ A REGISTRACE
# ==========================================
if not st.session_state.logged_in:
    col_l1, col_l2, col_l3 = st.columns([1, 1.8, 1])
    with col_l2:
        tab1, tab2 = st.tabs(["Přihlášení uživatele", "Žádost o přístup"])
        
        with tab1:
            st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
            login_input = st.text_input("E-mail nebo Přezdívka", key="login_username_input").strip()
            login_heslo = st.text_input("Heslo", type="password", key="login_heslo_input")
            
            # POLÍČKO PRO ZŮSTAT PŘIHLÁŠEN
            pamatovat_si = st.checkbox("Zůstat přihlášen na tomto zařízení", value=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Přihlásit se", type="primary", use_container_width=True):
                if login_input and login_heslo:
                    try:
                        res = supabase.table("uzivatele").select("*").eq("email", login_input).execute()
                        if not res.data:
                            try: res = supabase.table("uzivatele").select("*").eq("prezdivka", login_input).execute()
                            except Exception: res.data = []

                        if res.data:
                            user = res.data[0]
                            if bcrypt.checkpw(login_heslo.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                                sdh_nazev_db, sdh_iban_db = "Neznámý sbor", "CZ1234567890123456789012"
                                if user.get("sdh_id"):
                                    sbor_res = supabase.table("sbory").select("*").eq("id", user["sdh_id"]).execute()
                                    if sbor_res.data:
                                        sdh_nazev_db = sbor_res.data[0].get("nazev_sdh", sbor_res.data[0].get("nazev", "Sbor bez názvu"))
                                        sdh_iban_db = sbor_res.data[0].get("iban", "CZ1234567890123456789012")

                                # Nastavení Session State
                                st.session_state.logged_in = True
                                st.session_state.user_id = user["id"]
                                st.session_state.user_jmeno = f"{user['jmeno']} {user['prijmeni']}"
                                st.session_state.user_role = user["role"]
                                st.session_state.user_schvalen = user.get("schvalen", True)
                                st.session_state.sdh_id = user["sdh_id"]
                                st.session_state.sdh_nazev = sdh_nazev_db
                                st.session_state.sdh_iban = sdh_iban_db
                                st.session_state.user_avatar = ziskej_avatar_uzivatele(user["id"])
                                
                                # ZÁPIS DO COOKIE PŘI ZAŠKRTNUTÍ
                                if pamatovat_si:
                                    st.context.cookies["token_uzivatele"] = str(user["id"])
                                st.rerun()
                            else: st.error("Neplatné heslo.")
                        else: st.error("Uživatel neexistuje.")
                    except Exception as e:
                        st.error(f"Chyba spojení: {e}")
            st.markdown("</div>", unsafe_allow_html=True)

        with tab2:
            st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
            try:
                sbory_res = supabase.table("sbory").select("*").execute()
                seznam_sboru = {s.get("nazev_sdh", s.get("nazev", "Sbor")): s["id"] for s in sbory_res.data} if sbory_res.data else {}
            except Exception: seznam_sboru = {}
                
            volba_sboru = st.radio("Zvolte typ registrace:", ["Přidat se k existujícímu sboru", "Zaregistrovat nový sbor"])
            
            vybrany_sdh_id = None
            if volba_sboru == "Přidat se k existujícímu sboru":
                if seznam_sboru:
                    vybrany_sbor_nazev = st.selectbox("Vyberte sbor:", list(seznam_sboru.keys()))
                    vybrany_sdh_id = seznam_sboru[vybrany_sbor_nazev]
            else:
                novy_sbor_nazev = st.text_input("Název sboru (např. SDH Lhota)")
                novy_sbor_iban = st.text_input("Bankovní spojení (IBAN)")
                
            reg_jmeno = st.text_input("Jméno")
            reg_prijmeni = st.text_input("Příjmení")
            reg_email = st.text_input("E-mail")
            reg_heslo = st.text_input("Heslo", type="password")
            vybrana_role = st.selectbox("Funkce ve sboru:", ["velitel", "strojník", "hasič", "člen"])
            
            if st.button("Odeslat registraci", use_container_width=True):
                if reg_jmeno and reg_prijmeni and reg_email and reg_heslo and (vybrany_sdh_id or novy_sbor_nazev):
                    try:
                        if volba_sboru == "Zaregistrovat nový sbor":
                            try: sbor_ins = supabase.table("sbory").insert({"nazev_sdh": novy_sbor_nazev, "iban": novy_sbor_iban}).execute()
                            except Exception: sbor_ins = supabase.table("sbory").insert({"nazev": novy_sbor_nazev, "iban": novy_sbor_iban}).execute()
                            vybrany_sdh_id = sbor_ins.data[0]["id"]
                        
                        hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        je_prvni = len(supabase.table("uzivatele").select("id").eq("sdh_id", vybrany_sdh_id).execute().data) == 0
                        
                        supabase.table("uzivatele").insert({
                            "sdh_id": vybrany_sdh_id, "jmeno": reg_jmeno, "prijmeni": reg_prijmeni,
                            "email": reg_email, "heslo_hash": hashed, "role": vybrana_role, "schvalen": je_prvni
                        }).execute()
                        st.success("Registrace byla odeslána ke schválení veliteli.")
                    except Exception as e: st.error(f"Chyba zápisu: {e}")
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 4. BLOKACE PŘI ČEKÁNÍ NA SCHVÁLENÍ
# ==========================================
elif st.session_state.logged_in and not st.session_state.user_schvalen:
    st.markdown(f"""
    <div class='premium-card' style='border-left: 4px solid #eab308;'>
        <span class='cyber-badge' style='background:#78350f; color:#fef08a;'>Čeká na schválení</span>
        <h3 style='margin: 15px 0 5px 0; color:#fff;'>Čekání na ověření účtu</h3>
        <p style='color:#cbd5e1; margin:0;'>Váš účet byl vytvořen. Velitel sboru <b>{st.session_state.sdh_nazev}</b> vás musí schválit, než uvidíte interní data.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Odhlásit se"):
        if "token_uzivatele" in st.context.cookies:
            del st.context.cookies["token_uzivatele"]
        st.session_state.logged_in = False
        st.rerun()

# ==========================================
# 5. HLAVNÍ PORTÁL (PO PŘIHLÁŠENÍ)
# ==========================================
else:
    je_spravce = False
    try:
        vlastnik_res = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=False).limit(1).execute()
        if (vlastnik_res.data and vlastnik_res.data[0]["id"] == st.session_state.user_id) or st.session_state.user_role == "velitel":
            je_spravce = True
    except Exception:
        if st.session_state.user_role == "velitel": je_spravce = True

    # Postranní panel - Čisté zobrazení uživatele
    st.sidebar.markdown(f"""
    <div style="display: flex; align-items: center; background: #1e293b; padding: 14px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #334155;">
        {zobraz_profilovku(st.session_state.user_avatar)}
        <div>
            <div style="font-weight: 600; color: #ffffff; font-size: 0.95rem;">{st.session_state.user_jmeno}</div>
            <div style="color: #3b82f6; font-size: 0.85rem; font-weight: 500;">{str(st.session_state.user_role).capitalize()}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
    <div style="font-size: 0.8rem; color: #64748b; font-weight: 600; padding: 0 5px;">PŘIHLÁŠENÝ SBOR</div>
    <div style="padding: 2px 5px 15px 5px; font-weight:600; color:#ffffff; font-size:1.05rem; border-bottom: 1px solid #334155; margin-bottom: 20px;">{st.session_state.sdh_nazev}</div>
    """, unsafe_allow_html=True)
    
    menu_polozky = [
        "🚨 Poplach & Výjezd", 
        "📅 Plán akcí & Docházka", 
        "📢 Nástěnka sboru", 
        "📦 Sklad & Výstroj OOP", 
        "🪙 Pokladna & Příspěvky",
        "🛠️ Technika & Revize",
        "🧑‍🚒 Seznam členů",
        "⚙️ Moje nastavení"
    ]
    if je_spravce:
        menu_polozky.append("⚙️ Správa sboru (Velitel)")
        
    volba = st.sidebar.radio("Navigace", menu_polozky)

    # --- POPLACHY ---
    if volba == "🚨 Poplach & Výjezd":
        if je_spravce:
            with st.expander("🚨 Vyhlásit nový poplach jednotce"):
                pop_udalost = st.text_input("Druh události (např. Požár budovy)")
                pop_misto = st.text_input("Místo zásahu")
                if st.button("Vyhlásit poplach", type="primary", use_container_width=True):
                    if pop_udalost:
                        try:
                            supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                            supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": pop_udalost, "misto": pop_misto}).execute()
                            st.rerun()
                        except Exception as e: st.error(f"Chyba: {e}")

        try:
            pop_res = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
            aktivni_poplachy = pop_res.data
        except Exception: aktivni_poplachy = []
        
        if aktivni_poplachy:
            aktivni_poplach = aktivni_poplachy[0]
            st.markdown(f"""
            <div class="emergency-pulse">
                <span class="cyber-badge badge-alert">AKTIVNÍ POPLACH</span>
                <h2 style="color: #ffffff; margin: 10px 0 5px 0; font-weight:700;">{aktivni_poplach['udalost']}</h2>
                <p style="font-size: 1.05rem; margin: 0; color: #fecdd3;">📍 Místo: <b>{aktivni_poplach['misto']}</b></p>
            </div>
            """, unsafe_allow_html=True)
            
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                if st.button("🟢 Jedu ihned", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": "ihned"}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p2:
                cas_min = st.selectbox("Dojezd za:", ["5 min", "10 min", "15 min"], label_visibility="collapsed")
                if st.button("🟡 Jedu s prodlevou", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": cas_min}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p3:
                if st.button("🔴 Nemůžu (Omluven)", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Nedorazím", "cas_prijezdu": None}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()

            try:
                reakce_res = supabase.table("poplach_reakce").select("stav, cas_prijezdu, uzivatele(jmeno, prijmeni, role)").eq("poplach_id", aktivni_poplach["id"]).execute()
                vsechny_reakce = reakce_res.data if reakce_res.data else []
            except Exception: vsechny_reakce = []

            if vsechny_reakce:
                st.markdown("<br>", unsafe_allow_html=True)
                cg1, cg2 = st.columns(2)
                with cg1:
                    st.markdown("<div class='premium-card' style='border-top: 3px solid #22c55e;'><h4>🟢 Členové na cestě</h4>", unsafe_allow_html=True)
                    for r in vsechny_reakce:
                        if r["stav"] == "Jedu na zbrojnici" and r.get("uzivatele"): 
                            st.write(f"🧑‍🚒 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}** ({r['uzivatele']['role']}) — dojezd: `{r['cas_prijezdu']}`")
                    st.markdown("</div>", unsafe_allow_html=True)
                with cg2:
                    st.markdown("<div class='premium-card' style='border-top: 3px solid #ef4444;'><h4>🔴 Nedostupní členové</h4>", unsafe_allow_html=True)
                    for r in vsechny_reakce:
                        if r["stav"] == "Nedorazím" and r.get("uzivatele"): 
                            st.write(f"❌ **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}**")
                    st.markdown("</div>", unsafe_allow_html=True)
            
            if je_spravce and st.button("Konec poplachu / Odvolat výjezd", type="secondary", use_container_width=True):
                supabase.table("poplachy").update({"aktivni": False}).eq("id", aktivni_poplach["id"]).execute()
                st.rerun()
        else:
            st.markdown("<div class='premium-card'>🎉 Všechny sektory jsou klidné. Žádný aktivní poplach.</div>", unsafe_allow_html=True)

    # --- PLÁN AKCÍ ---
    elif volba == "📅 Plán akcí & Docházka":
        st.subheader("Harmonogram výcviků a činností")
        try:
            akce_res = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).order("datum").execute()
            vsechny_akce = akce_res.data if akce_res.data else []
        except Exception: vsechny_akce = []
        
        kalendar_udalosti = []
        for akce in vsechny_akce:
            kalendar_udalosti.append({
                "id": str(akce["id"]), "title": akce["nazev_akce"], "start": akce["datum"], "end": akce["datum"], "allDay": True, "color": "#3b82f6"
            })
        
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        calendar(events=kalendar_udalosti, options={"locale": "cs", "firstDay": 1}, key="portal_calendar")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("### 📋 Potvrzení účasti")
        for akce in vsechny_akce:
            if akce["datum"] >= datetime.date.today().isoformat():
                with st.expander(f"📅 {akce['datum']} — {akce['nazev_akce']}"):
                    st.write(akce.get("poznamka", "Bez bližších podrobností."))
                    
                    stav_moje = "Nenahlášeno"
                    try:
                        doch_res = supabase.table("dochazka").select("status").eq("akce_id", akce["id"]).eq("uzivatel_id", st.session_state.user_id).execute()
                        if doch_res.data: stav_moje = doch_res.data[0]["status"]
                    except Exception: pass
                    
                    st.write(f"Moje účast: **{stav_moje}**")
                    c1, c2 = st.columns(2)
                    if c1.button("Půjdu 👍", key=f"j_{akce['id']}", use_container_width=True):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Jdu"}, on_conflict="akce_id,uzivatel_id").execute()
                        st.rerun()
                    if c2.button("Nemůžu doručit 👎", key=f"n_{akce['id']}", use_container_width=True):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nejdu"}, on_conflict="akce_id,uzivatel_id").execute()
                        st.rerun()

    # --- POKLADNA ---
    elif volba == "🪙 Pokladna & Příspěvky":
        st.subheader("Rozpočty a členské poplatky")
        try:
            trans_res = supabase.table("pokladna").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
            vsechny_trans = trans_res.data if trans_res.data else []
        except Exception: vsechny_trans = []
        
        prijmy = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Příjem")
        vydaje = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Výdaj")
        
        wc1, wc2, wc3 = st.columns(3)
        with wc1: st.markdown(f"<div class='premium-card' style='border-top: 3px solid #22c55e;'><div>Příjmy sboru</div><div style='font-size:1.8rem; font-weight:700; color:#4ade80;'>{prijmy:,.2f} Kč</div></div>", unsafe_allow_html=True)
        with wc2: st.markdown(f"<div class='premium-card' style='border-top: 3px solid #ef4444;'><div>Výdaje sboru</div><div style='font-size:1.8rem; font-weight:700; color:#f87171;'>{vydaje:,.2f} Kč</div></div>", unsafe_allow_html=True)
        with wc3: st.markdown(f"<div class='premium-card' style='border-top: 3px solid #3b82f6;'><div>Zůstatek na účtu</div><div style='font-size:1.8rem; font-weight:700; color:#60a5fa;'>{prijmy-vydaje:,.2f} Kč</div></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.markdown("### 📱 QR platba příspěvků")
        castka_p = st.number_input("Částka (Kč):", value=500, step=100)
        msg = f"Prispevek {st.session_state.user_jmeno}"
        
        qr_url = generuj_qr_kod_url(st.session_state.sdh_iban, castka_p, msg)
        cq1, cq2 = st.columns([1, 3])
        with cq1: st.image(qr_url, width=170)
        with cq2: st.markdown(f"""
            <p style='margin-bottom:2px; font-size:0.85rem; color:#94a3b8;'>ČÍSLO ÚČTU (IBAN)</p>
            <code style='font-size:1rem; color:#fff; background:#0f172a; padding:4px 8px; border-radius:4px;'>{st.session_state.sdh_iban}</code>
            <p style='margin-bottom:2px; margin-top:12px; font-size:0.85rem; color:#94a3b8;'>ZPRÁVA PRO PŘÍJEMCE</p>
            <code style='font-size:1rem; color:#fff; background:#0f172a; padding:4px 8px; border-radius:4px;'>{msg}</code>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- NÁSTĚNKA ---
    elif volba == "📢 Nástěnka sboru":
        st.subheader("Interní rozkazy a sdělení")
        if je_spravce:
            with st.expander("📌 Přidat nové oznámení"):
                nadpis = st.text_input("Předmět")
                text = st.text_area("Obsah zprávy")
                if st.button("Publikovat"):
                    supabase.table("nastenka").insert({"sdh_id": st.session_state.sdh_id, "autor_jmeno": st.session_state.user_jmeno, "nadpis": nadpis, "text": text, "dulezite": False}).execute()
                    st.rerun()
                    
        try: zpravy = supabase.table("nastenka").select("*").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=True).execute().data
        except Exception: zpravy = []
            
        for z in (zpravy if zpravy else []):
            st.markdown(f"""
            <div class='premium-card'>
                <h4 style='margin:0 0 5px 0; color:#fff;'>{z['nadpis']}</h4>
                <p style='color:#cbd5e1;'>{z['text']}</p>
                <div style='font-size:0.8rem; color:#64748b; margin-top:10px;'>Autor: {z['autor_jmeno']} | Datum: {z['created_at'][:10]}</div>
            </div>
            """, unsafe_allow_html=True)

    # --- SKLAD ---
    elif volba == "📦 Sklad & Výstroj OOP":
        st.subheader("Evidence materiálu")
        try:
            vsechen_sklad = supabase.table("sklad").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).execute().data
        except Exception:
            try: vsechen_sklad = supabase.table("sklad").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
            except Exception: vsechen_sklad = []
        
        if je_spravce:
            with st.expander("➕ Zaevidovat novou výstroj/materiál"):
                nazev_it = st.text_input("Název položky")
                vel_it = st.text_input("Velikost / Specifikace")
                if st.button("Uložit do skladu"):
                    supabase.table("sklad").insert({"sdh_id": st.session_state.sdh_id, "nazev": nazev_it, "velikost": vel_it, "stav": "V pořádku"}).execute()
                    st.rerun()

        for i in (vsechen_sklad if vsechen_sklad else []):
            stav_text = f"👤 Vydáno: {i['uzivatele']['jmeno']} {i['uzivatele']['prijmeni']}" if i.get('uzivatele') else "📦 Skladem"
            b_style = "badge-neutral" if i.get('uzivatele') else "badge-ok"
            st.markdown(f"""
            <div class='premium-card' style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <span style='font-weight:600; color:#fff;'>{i['nazev']}</span>
                    <span style='color:#64748b; margin-left:12px; font-size:0.9rem;'>({i['velikost']})</span>
                </div>
                <span class='cyber-badge {b_style}'>{stav_text}</span>
            </div>
            """, unsafe_allow_html=True)

    # --- TECHNIKA ---
    elif volba == "🛠️ Technika & Revize":
        st.subheader("Stav techniky a revize")
        try: tech = supabase.table("technika").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
        except Exception: tech = []
        
        if je_spravce:
            with st.expander("➕ Přidat nové vozidlo/techniku"):
                t_nazev = st.text_input("Název / Označení stroje")
                t_stk = st.date_input("Platnost STK / Revize do")
                if st.button("Uložit techniku"):
                    supabase.table("technika").insert({"sdh_id": st.session_state.sdh_id, "nazev": t_nazev, "stk_revize": str(t_stk), "typ": "Vozidlo", "stav": "V pořádku"}).execute()
                    st.rerun()
                    
        for t in (tech if tech else []):
            st.markdown(f"""
            <div class='premium-card'>
                <div style='font-weight:600; color:#fff; font-size:1.1rem;'>🚒 {t['nazev']}</div>
                <div style='font-size:0.85rem; color:#94a3b8; margin-top:4px;'>Konec revize / STK: <span style='color:#ef4444; font-weight:500;'>{t['stk_revize']}</span></div>
            </div>
            """, unsafe_allow_html=True)

    # --- SEZNAM ČLENŮ ---
    elif volba == "🧑‍🚒 Seznam členů":
        st.subheader("Seznam členů sboru")
        try: clenove = supabase.table("uzivatele").select("jmeno, prijmeni, role, schvalen").eq("sdh_id", st.session_state.sdh_id).execute().data
        except Exception: clenove = []
            
        for c in (clenove if clenove else []):
            if c.get("schvalen", True):
                st.markdown(f"""
                <div class='premium-card' style='display:flex; justify-content:space-between; align-items:center;'>
                    <span style='font-weight:500; color:#fff;'>🧑‍🚒 {c['jmeno']} {c['prijmeni']}</span>
                    <span class='cyber-badge badge-neutral'>{c['role']}</span>
                </div>
                """, unsafe_allow_html=True)

    # --- MOJE NASTAVENÍ ---
    elif volba == "⚙️ Moje nastavení":
        st.subheader("Můj profil")
        strav_avatar = ziskej_avatar_uzivatele(st.session_state.user_id)
        
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        novy_em = st.text_input("Profilové Emoji:", value=strav_avatar if not str(strav_avatar).startswith("data:image") else "🧑‍🚒")
        if st.button("Uložit profil", use_container_width=True):
            uloz_avatar_uzivatele(st.session_state.user_id, novy_em)
            st.session_state.user_avatar = novy_em
            st.success("Profil byl aktualizován."); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.button("Odhlásit se", type="primary", use_container_width=True):
            # Kompletní smazání cookie při manuálním odhlášení
            if "token_uzivatele" in st.context.cookies:
                del st.context.cookies["token_uzivatele"]
            st.session_state.logged_in = False
            st.rerun()

    # --- ADMINISTRACE VELITELE ---
    elif volba == "⚙️ Správa sboru (Velitel)" and je_spravce:
        st.subheader("Administrační panel velitele")
        
        st.markdown("### 🔒 Žádosti o schválení do sboru")
        try: neschvaleni = supabase.table("uzivatele").select("id, jmeno, prijmeni, email, role").eq("sdh_id", st.session_state.sdh_id).eq("schvalen", False).execute().data
        except Exception: neschvaleni = []
        
        if neschvaleni:
            for u in neschvaleni:
                st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
                col_u1, col_u2 = st.columns([3, 1])
                with col_u1:
                    st.write(f"👤 **{u['jmeno']} {u['prijmeni']}** ({u['email']}) \nPožadovaná funkce: `{u['role']}`")
                with col_u2:
                    if st.button("Schválit člena", key=f"schv_{u['id']}", use_container_width=True):
                        supabase.table("uzivatele").update({"schvalen": True}).eq("id", u["id"]).execute()
                        st.success("Uživatel schválen.")
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Žádné nevyřízené žádosti o přístup.")
            
        st.markdown("<br>### 📅 Vytvořit novou událost", unsafe_allow_html=True)
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        n_nazev = st.text_input("Název akce")
        n_typ = st.selectbox("Typ události", ["Cvičení", "Schůze", "Soutěž", "Brigáda", "Zásah"])
        n_datum = st.date_input("Datum konání")
        n_poznamka = st.text_area("Poznámka / Instrukce")
        
        if st.button("Uložit akci do kalendáře", type="primary", use_container_width=True):
            if n_nazev:
                try:
                    supabase.table("akce").insert({
                        "sdh_id": st.session_state.sdh_id, "datum": str(n_datum), "nazev_akce": n_nazev, "typ_akce": n_typ, "poznamka": n_poznamka
                    }).execute()
                    st.success("Akce byla úspěšně vytvořena."); st.rerun()
                except Exception as e: st.error(f"Chyba: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

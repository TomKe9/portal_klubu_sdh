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
# 1. PRÉMIOVÝ MODERNÍ DESIGN (CSS 2026)
# ==========================================
st.set_page_config(
    page_title="RESQ | Hasičský Portál", 
    page_icon="🚒", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Tech & Cyberpunk-minimalistický styl pro rok 2026
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    /* Globální reset a písmo */
    html, body, [data-testid="stSidebar"], .stApp {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #0d0f12 !important;
        color: #f3f4f6 !important;
    }
    
    /* Moderní skleněné karty (Glassmorphism) */
    .modern-card {
        background: rgba(22, 28, 36, 0.8);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: all 0.3s ease;
    }
    .modern-card:hover {
        border-color: rgba(255, 255, 255, 0.1);
        transform: translateY(-2px);
    }
    
    /* Neonový poplachový panel */
    .alarm-card {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.05) 100%);
        border: 2px solid #ef4444;
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.25);
        border-radius: 16px;
        padding: 28px;
        margin-bottom: 24px;
        animation: pulse-border 2s infinite;
    }
    
    @keyframes pulse-border {
        0% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.2); }
        50% { box-shadow: 0 0 25px rgba(239, 68, 68, 0.4); }
        100% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.2); }
    }
    
    /* Custom Badges */
    .m-badge {
        display: inline-flex;
        align-items: center;
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .m-badge-danger { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .m-badge-success { background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .m-badge-info { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    
    /* Velké moderní metriky */
    .m-metric-title {
        font-size: 0.85rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
    .m-metric-value {
        font-size: 2rem;
        font-weight: 800;
        margin-top: 8px;
        letter-spacing: -0.02em;
    }
    
    /* Skrytí standardních Streamlit prvků pro čistší pocit z "appky" */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background-color: transparent !important;}
    
    /* Customizace inputů pro moderní vzhled */
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea, select {
        background-color: #161c24 !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #ef4444 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INICIALIZACE A FUNKCE
# ==========================================
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase: Client = init_connection()

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

def zobraz_profilovku(avatar_data):
    if not avatar_data: return "🧑‍🚒"
    return f"""<span style="font-size: 38px; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 12px; margin-right: 14px; box-shadow: inset 0 0 10px rgba(255,255,255,0.1);">{avatar_data}</span>"""

def generuj_qr_kod_url(iban, castka, zprava):
    cistý_iban = re.sub(r'\s+', '', iban)
    zprava_url = urllib.parse.quote(zprava[:20])
    return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={cistý_iban[2:]}&bankCode={cistý_iban[2:6]}&amount={castka}&currency=CZK&message={zprava_url}"

# Úvodní Brand hlavička
st.markdown("""
<div style="display: flex; align-items: center; justify-content: space-between; padding-bottom: 24px; border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 30px;">
    <div>
        <span style="font-size: 0.75rem; font-weight: 800; color: #ef4444; letter-spacing: 0.2em; text-transform: uppercase;">Next-Gen Mission Control</span>
        <h1 style="margin: 4px 0 0 0; font-weight: 900; letter-spacing: -0.04em; font-size: 2.5rem; color: #ffffff;">RESQ<span style="color:#ef4444;">.</span></h1>
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 3. AUTORIZACE (PŘIHLÁŠENÍ & REGISTRACE)
# ==========================================
if not st.session_state.logged_in:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        tab1, tab2 = st.tabs(["🔒 VSTUP DO SYSTÉMU", "📝 ŽÁDOST O PŘÍSTUP"])
        
        with tab1:
            st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
            login_input = st.text_input("Identifikační e-mail / Přezdívka", key="login_username_input").strip()
            login_heslo = st.text_input("Přístupové heslo", type="password", key="login_heslo_input")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("AUTORIZOVAT", type="primary", use_container_width=True):
                if login_input and login_heslo:
                    try:
                        res = supabase.table("uzivatele").select("*").eq("email", login_input).execute()
                        if not res.data:
                            try: res = supabase.table("uzivatele").select("*").eq("prezdivka", login_input).execute()
                            except Exception: res.data = []

                        if res.data:
                            user = res.data[0]
                            sdh_nazev_db, sdh_iban_db = "Neznámý sbor", "CZ1234567890123456789012"
                            
                            if user.get("sdh_id"):
                                try:
                                    sbor_res = supabase.table("sbory").select("*").eq("id", user["sdh_id"]).execute()
                                    if sbor_res.data:
                                        sdh_nazev_db = sbor_res.data[0].get("nazev_sdh", sbor_res.data[0].get("nazev", "Sbor bez názvu"))
                                        sdh_iban_db = sbor_res.data[0].get("iban", "CZ1234567890123456789012")
                                except Exception: pass

                            if bcrypt.checkpw(login_heslo.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                                st.session_state.logged_in = True
                                st.session_state.user_id = user["id"]
                                st.session_state.user_jmeno = f"{user['jmeno']} {user['prijmeni']}"
                                st.session_state.user_role = user["role"]
                                st.session_state.user_schvalen = user.get("schvalen", True)
                                st.session_state.sdh_id = user["sdh_id"]
                                st.session_state.sdh_nazev = sdh_nazev_db
                                st.session_state.sdh_iban = sdh_iban_db
                                st.session_state.user_avatar = ziskej_avatar_uzivatele(user["id"])
                                st.rerun()
                            else: st.error("Chybné heslo.")
                        else: st.error("Uživatel neexistuje.")
                    except Exception as e:
                        st.error("Chyba spojení:")
                        st.code(str(e))
            st.markdown("</div>", unsafe_allow_html=True)

        with tab2:
            st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
            try:
                sbory_res = supabase.table("sbory").select("*").execute()
                seznam_sboru = {s.get("nazev_sdh", s.get("nazev", "Sbor")): s["id"] for s in sbory_res.data} if sbory_res.data else {}
            except Exception: seznam_sboru = {}
                
            volba_sboru = st.radio("Typ registrace:", ["Přidat se k existujícímu sboru", "Zaregistrovat nový sbor"])
            
            vybrany_sdh_id, novy_sbor_nazev, novy_sbor_iban = None, "", ""
            if volba_sboru == "Přidat se k existujícímu sboru":
                if seznam_sboru:
                    vybrany_sbor_nazev = st.selectbox("Vyberte sbor:", list(seznam_sboru.keys()))
                    vybrany_sdh_id = seznam_sboru[vybrany_sbor_nazev]
            else:
                novy_sbor_nazev = st.text_input("Název nového sboru (např. SDH Lhota)").strip()
                novy_sbor_iban = st.text_input("IBAN nového sboru").strip()
                
            reg_jmeno = st.text_input("Jméno")
            reg_prijmeni = st.text_input("Příjmení")
            reg_email = st.text_input("E-mail")
            reg_heslo = st.text_input("Heslo (min. 8 znaků)", type="password")
            vybrana_role = st.selectbox("Zařazení v jednotce:", ["velitel", "strojník", "hasič", "člen"])
            
            if st.button("ODESLAT ŽÁDOST", type="secondary", use_container_width=True):
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
                        st.success("Registrace uložena. Vyčkejte na schválení administrátorem/velitelem.")
                    except Exception as e: st.error(f"Chyba: {e}")
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 4. ČEKÁNÍ NA SCHVÁLENÍ Profilu
# ==========================================
elif st.session_state.logged_in and not st.session_state.user_schvalen:
    st.markdown(f"""
    <div class='alarm-card' style='border-color: #f59e0b; box-shadow: 0 0 15px rgba(245,158,11,0.2);'>
        <span class='m-badge' style='background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3);'>PŘÍSTUP POZASTAVEN</span>
        <h3 style='margin: 15px 0 5px 0; color: #ffffff;'>Účet čeká na autorizaci</h3>
        <p style='color: #d1d5db; margin: 0;'>Velitel sboru <b>{st.session_state.sdh_nazev}</b> musí nejprve ověřit vaši totožnost a schválit vaši roli v systému.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Odhlásit se"):
        st.session_state.logged_in = False
        st.rerun()

# ==========================================
# 5. HLAVNÍ CORE ROZHRANÍ (SCHVÁLENÍ ČLENOVÉ)
# ==========================================
else:
    je_spravce = False
    try:
        vlastnik_res = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=False).limit(1).execute()
        if (vlastnik_res.data and vlastnik_res.data[0]["id"] == st.session_state.user_id) or st.session_state.user_role == "velitel":
            je_spravce = True
    except Exception:
        if st.session_state.user_role == "velitel": je_spravce = True

    # Špičkový sidebar pro rok 2026
    st.sidebar.markdown(f"""
    <div style="display: flex; align-items: center; background: rgba(255,255,255,0.03); padding: 16px; border-radius: 14px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.05);">
        {zobraz_profilovku(st.session_state.user_avatar)}
        <div>
            <div style="font-weight: 700; color: #ffffff; font-size: 1rem; letter-spacing: -0.01em;">{st.session_state.user_jmeno}</div>
            <div style="font-size: 0.7rem; color: #ef4444; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 2px;">{str(st.session_state.user_role)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
    <div style="padding: 2px 12px; font-size: 0.8rem; color:#9ca3af; font-weight:500;">AKTIVNÍ SBOR</div>
    <div style="padding: 0 12px 20px 12px; font-weight:700; color:#ffffff; font-size:1.1rem; border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 15px;">{st.session_state.sdh_nazev}</div>
    """, unsafe_allow_html=True)
    
    menu_polozky = [
        "🚨 POPLACH & Výjezd", 
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
        
    volba = st.sidebar.radio("NAVIGACE CONTROL CENTER", menu_polozky)

    # --- MODUL: POPLACH ---
    if volba == "🚨 POPLACH & Výjezd":
        st.markdown("<span style='font-size:0.8rem; color:#ef4444; font-weight:700; letter-spacing:0.1em;'>LIVE FEED</span>", unsafe_allow_html=True)
        st.h2 = "Operační monitor JSDH"
        
        if je_spravce:
            with st.expander("🚨 AKTIVACE VÝJEZDOVÉHO POPLACHU (VELITEL)"):
                pop_udalost = st.text_input("Typ mimořádné události (Druh zásahu)")
                pop_misto = st.text_input("Přesná lokalizace (Adresa / GPS koordináty)")
                if st.button("VYHLÁSIT AKUTNÍ POPLACH", type="primary", use_container_width=True):
                    if pop_udalost:
                        try:
                            supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                            supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": pop_udalost, "misto": pop_misto}).execute()
                            st.success("Poplach byl úspěšně distribuován členům jednotky.")
                            st.rerun()
                        except Exception as e: st.error(f"Chyba: {e}")

        try:
            pop_res = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
            aktivni_poplachy = pop_res.data
        except Exception: aktivni_poplachy = []
        
        if aktivni_poplachy:
            aktivni_poplach = aktivni_poplachy[0]
            st.markdown(f"""
            <div class="alarm-card">
                <span class="m-badge m-badge-danger">🚨 AKUTNÍ VÝJEZD JEDNOTKY</span>
                <h1 style="color: #ffffff; margin: 15px 0 5px 0; font-weight:800; letter-spacing:-0.03em;">{aktivni_poplach['udalost']}</h1>
                <p style="font-size: 1.1rem; margin: 0; color: #fca5a5;">📍 <b>Místo incidentu:</b> {aktivni_poplach['misto']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<p style='font-size:0.85rem; color:#9ca3af; font-weight:700; margin-bottom:10px;'>POTVRZENÍ AKCESCHOPNOSTI</p>", unsafe_allow_html=True)
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                if st.button("🟢 IHNED NA ZBROJNICI", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": "ihned"}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p2:
                cas_min = st.selectbox("DORAZÍM ZA (MIN):", ["5 min", "10 min", "15 min"], label_visibility="collapsed")
                if st.button("🟡 JEDU S PRODLEVOU", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": cas_min}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p3:
                if st.button("🔴 NEDOSTUPNÝ", use_container_width=True):
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
                    st.markdown("<div class='modern-card'><h4 style='margin-top:0; color:#4ade80;'>🟢 Na cestě do základny</h4>", unsafe_allow_html=True)
                    for r in vsechny_reakce:
                        if r["stav"] == "Jedu na zbrojnici" and r.get("uzivatele"): 
                            st.write(f"🧑‍🚒 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}** ({r['uzivatele']['role']}) — dojezd: `{r['cas_prijezdu']}`")
                    st.markdown("</div>", unsafe_allow_html=True)
                with cg2:
                    st.markdown("<div class='modern-card'><h4 style='margin-top:0; color:#f87171;'>🔴 Nedostupní členové</h4>", unsafe_allow_html=True)
                    for r in vsechny_reakce:
                        if r["stav"] == "Nedorazím" and r.get("uzivatele"): 
                            st.write(f"❌ **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}**")
                    st.markdown("</div>", unsafe_allow_html=True)
            
            if je_spravce and st.button("❌ ODVOLAT / UKONČIT POPLACH", type="secondary", use_container_width=True):
                supabase.table("poplachy").update({"aktivni": False}).eq("id", aktivni_poplach["id"]).execute()
                st.rerun()
        else:
            st.markdown("<div class='modern-card' style='border-left: 4px solid #22c55e;'>🎉 <b>Stav: Základna v klidu.</b> Žádný aktivní poplach nebyl detekován.</div>", unsafe_allow_html=True)

    # --- MODUL: KALENDÁŘ ---
    elif volba == "📅 Plán akcí & Docházka":
        st.subheader("Plán směn, výcviků a akcí")
        try:
            akce_res = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).order("datum").execute()
            vsechny_akce = akce_res.data if akce_res.data else []
        except Exception: vsechny_akce = []
        
        kalendar_udalosti = []
        for akce in vsechny_akce:
            kalendar_udalosti.append({
                "id": str(akce["id"]), "title": akce["nazev_akce"], "start": akce["datum"], "end": akce["datum"], "allDay": True,
                "color": "#ef4444" if akce["typ_akce"] == "Zásah" else "#3b82f6"
            })
        
        st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
        calendar(events=kalendar_udalosti, options={"locale": "cs", "firstDay": 1, "themeSystem": "bootstrap"}, key="portal_calendar")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("### 📋 Vyjádření k nadcházející docházce")
        for akce in vsechny_akce:
            if akce["datum"] >= datetime.date.today().isoformat():
                with st.expander(f"📅 {akce['datum']} — {akce['nazev_akce']} [{akce['typ_akce']}]"):
                    st.write(akce.get("poznamka", "Detaily k akci nebyly specifikovány."))
                    
                    stav_moje = "Nenahlášeno"
                    try:
                        doch_res = supabase.table("dochazka").select("status").eq("akce_id", akce["id"]).eq("uzivatel_id", st.session_state.user_id).execute()
                        if doch_res.data: stav_moje = doch_res.data[0]["status"]
                    except Exception: pass
                    
                    st.markdown(f"Status vaší účasti: **{stav_moje}**")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("POTVRZUJI ÚČAST 👍", key=f"j_{akce['id']}", use_container_width=True):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Jdu"}, on_conflict="akce_id,uzivatel_id").execute()
                        st.rerun()
                    if c2.button("OMMLOUVÁM SE 👎", key=f"n_{akce['id']}", use_container_width=True):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nejdu"}, on_conflict="akce_id,uzivatel_id").execute()
                        st.rerun()

    # --- MODUL: POKLADNA ---
    elif volba == "🪙 Pokladna & Příspěvky":
        st.subheader("Finanční management a členské příspěvky")
        
        try:
            trans_res = supabase.table("pokladna").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
            vsechny_trans = trans_res.data if trans_res.data else []
        except Exception: vsechny_trans = []
        
        prijmy = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Příjem")
        vydaje = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Výdaj")
        
        wc1, wc2, wc3 = st.columns(3)
        with wc1: st.markdown(f"<div class='modern-card'><span class='m-metric-title'>Celkové příjmy</span><div class='m-metric-value' style='color:#4ade80;'>{prijmy:,.2f} Kč</div></div>", unsafe_allow_html=True)
        with wc2: st.markdown(f"<div class='modern-card'><span class='m-metric-title'>Celkové výdaje</span><div class='m-metric-value' style='color:#f87171;'>{vydaje:,.2f} Kč</div></div>", unsafe_allow_html=True)
        with wc3: st.markdown(f"<div class='modern-card'><span class='m-metric-title'>Bilanční stav konta</span><div class='m-metric-value' style='color:#60a5fa;'>{prijmy-vydaje:,.2f} Kč</div></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
        st.markdown("### 📱 Okamžité vyrovnání členského příspěvku (QR Pay)")
        castka_p = st.number_input("Nastavit částku (Kč):", value=500, step=100)
        msg = f"Prispevek {st.session_state.user_jmeno}"
        
        qr_url = generuj_qr_kod_url(st.session_state.sdh_iban, castka_p, msg)
        cq1, cq2 = st.columns([1, 3])
        with cq1: st.image(qr_url, width=200)
        with cq2: st.markdown(f"""
            <div style='padding-top:10px;'>
                <p style='color:#9ca3af; margin:0 0 5px 0;'>BANKOVNÍ ÚČET SBORU</p>
                <code style='font-size:1.1rem; color:#ffffff; background:rgba(255,255,255,0.05); padding:5px 10px; border-radius:6px;'>{st.session_state.sdh_iban}</code>
                <p style='color:#9ca3af; margin:15px 0 5px 0;'>ZPRÁVA PRO PŘÍJEMCE</p>
                <code style='font-size:1.1rem; color:#ffffff; background:rgba(255,255,255,0.05); padding:5px 10px; border-radius:6px;'>{msg}</code>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- MODUL: NÁSTĚNKA ---
    elif volba == "📢 Nástěnka sboru":
        st.subheader("Informační kanál sboru")
        if je_spravce:
            with st.expander("📌 PUBLIKOVAT NOVÉ ROZKAZY / SDĚLENÍ"):
                nadpis = st.text_input("Nadpis zprávy")
                text = st.text_area("Obsah sdělení")
                if st.button("ZVEŘEJNIT"):
                    supabase.table("nastenka").insert({"sdh_id": st.session_state.sdh_id, "autor_jmeno": st.session_state.user_jmeno, "nadpis": nadpis, "text": text, "dulezite": False}).execute()
                    st.rerun()
                    
        try: zpravy = supabase.table("nastenka").select("*").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=True).execute().data
        except Exception: zpravy = []
            
        for z in (zpravy if zpravy else []):
            st.markdown(f"""
            <div class='modern-card' style='border-left: 4px solid #3b82f6;'>
                <h4 style='margin:0 0 10px 0; font-weight:700; color:#ffffff;'>{z['nadpis']}</h4>
                <p style='color:#e5e7eb; line-height:1.6;'>{z['text']}</p>
                <hr style='border:0; border-top:1px solid rgba(255,255,255,0.05); margin:15px 0 5px 0;'>
                <small style='color:#9ca3af;'>Vystavil: <b>{z['autor_jmeno']}</b> | {z['created_at'][:10]}</small>
            </div>
            """, unsafe_allow_html=True)

    # --- MODUL: SKLAD ---
    elif volba == "📦 Sklad & Výstroj OOP":
        st.subheader("Centrální registr výstroje a technických prostředků")
        try:
            vsechen_sklad = supabase.table("sklad").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).execute().data
        except Exception:
            try: vsechen_sklad = supabase.table("sklad").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
            except Exception: vsechen_sklad = []
        
        if je_spravce:
            with st.expander("➕ EVIDOVAT NOVÝ MATERIÁL / OOP"):
                nazev_it = st.text_input("Název položky (např. Zásahový kabát Bushfire)")
                vel_it = st.text_input("Velikostní specifikace")
                if st.button("Uložit položku"):
                    supabase.table("sklad").insert({"sdh_id": st.session_state.sdh_id, "nazev": nazev_it, "velikost": vel_it, "stav": "V pořádku"}).execute()
                    st.rerun()

        for i in (vsechen_sklad if vsechen_sklad else []):
            stav_text = f"👤 Vydáno: {i['uzivatele']['jmeno']} {i['uzivatele']['prijmeni']}" if i.get('uzivatele') else "📦 Skladem k dispozici"
            badge_style = "m-badge-info" if i.get('uzivatele') else "m-badge-success"
            st.markdown(f"""
            <div class='modern-card' style='display:flex; justify-content:between; align-items:center;'>
                <div>
                    <span style='font-size:1.1rem; font-weight:700; color:#fff;'>{i['nazev']}</span> 
                    <span style='color:#9ca3af; margin-left:10px;'>Velikost: {i['velikost']}</span>
                </div>
                <span class='m-badge {badge_style}'>{stav_text}</span>
            </div>
            """, unsafe_allow_html=True)

    # --- MODUL: TECHNIKA ---
    elif volba == "🛠️ Technika & Revize":
        st.subheader("Stav techniky a platnost revizních zkoušek")
        try: tech = supabase.table("technika").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
        except Exception: tech = []
        
        if je_spravce:
            with st.expander("➕ ZAŘADIT NOVOU TECHNIKU DO EVIDENCE"):
                t_nazev = st.text_input("Označení techniky (např. CAS 20 Scania)")
                t_stk = st.date_input("Konec platnosti STK / Revize")
                if st.button("Zapsat techniku"):
                    supabase.table("technika").insert({"sdh_id": st.session_state.sdh_id, "nazev": t_nazev, "stk_revize": str(t_stk), "typ": "Vozidlo", "stav": "V pořádku"}).execute()
                    st.rerun()
                    
        for t in (tech if tech else []):
            st.markdown(f"""
            <div class='modern-card'>
                <div style='font-size:1.2rem; font-weight:700; color:#ffffff;'>🚒 {t['nazev']}</div>
                <div style='color:#9ca3af; margin-top:5px; font-size:0.9rem;'>Příští kontrola / STK limit: <b style='color:#fff;'>{t['stk_revize']}</b></div>
            </div>
            """, unsafe_allow_html=True)

    # --- MODUL: SEZNAM ČLENŮ ---
    elif volba == "🧑‍🚒 Seznam členů":
        st.subheader("Členská základna a hierarchie")
        try: clenove = supabase.table("uzivatele").select("jmeno, prijmeni, role, schvalen").eq("sdh_id", st.session_state.sdh_id).execute().data
        except Exception: clenove = []
            
        for c in (clenove if clenove else []):
            if c.get("schvalen", True):
                st.markdown(f"""
                <div class='modern-card' style='display:flex; justify-content:space-between; align-items:center;'>
                    <span style='font-weight:700; font-size:1.1rem;'>🧑‍🚒 {c['jmeno']} {c['prijmeni']}</span>
                    <span class='m-badge m-badge-info'>{c['role']}</span>
                </div>
                """, unsafe_allow_html=True)

    # --- MODUL: MOJE NASTAVENÍ ---
    elif volba == "⚙️ Moje nastavení":
        st.subheader("Správa osobního profilu")
        strav_avatar = ziskej_avatar_uzivatele(st.session_state.user_id)
        
        st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
        novy_em = st.text_input("Změnit identifikátor profilu (Emoji ikonu):", value=strav_avatar if not str(strav_avatar).startswith("data:image") else "🧑‍🚒")
        if st.button("ULOŽIT NASTAVENÍ", use_container_width=True):
            uloz_avatar_uzivatele(st.session_state.user_id, novy_em)
            st.session_state.user_avatar = novy_em
            st.success("Profil aktualizován."); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.button("ODHLÁSIT SE ZE SYSTÉMU", type="primary", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # --- MODUL: ADMIN VELITELE ---
    elif volba == "⚙️ Správa sboru (Velitel)" and je_spravce:
        st.subheader("Řízení sboru a administrativní sekce")
        
        st.markdown("### 🔒 Členové čekající na schválení přístupu")
        try: neschvaleni = supabase.table("uzivatele").select("id, jmeno, prijmeni, email, role").eq("sdh_id", st.session_state.sdh_id).eq("schvalen", False).execute().data
        except Exception: neschvaleni = []
        
        if neschvaleni:
            for u in neschvaleni:
                st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
                col_u1, col_u2 = st.columns([3, 1])
                with col_u1:
                    st.markdown(f"👤 <b>{u['jmeno']} {u['prijmeni']}</b><br><small style='color:#9ca3af;'>{u['email']} | Požadovaná hodnost: {u['role']}</small>", unsafe_allow_html=True)
                with col_u2:
                    if st.button("SCHVÁLIT", key=f"schv_{u['id']}", use_container_width=True):
                        supabase.table("uzivatele").update({"schvalen": True}).eq("id", u["id"]).execute()
                        st.success("Přístup schválen.")
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Žádné nevyřízené žádosti o registraci v tomto sboru.")
            
        st.markdown("<br>### 📅 Plánování nových událostí do kalendáře", unsafe_allow_html=True)
        st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
        n_nazev = st.text_input("Název události")
        n_typ = st.selectbox("Typ činnosti", ["Cvičení", "Schůze", "Soutěž", "Brigáda", "Zásah"])
        n_datum = st.date_input("Datum konání")
        n_poznamka = st.text_area("Instrukce a doplňující text k akci")
        
        if st.button("PUBLIKOVAT AKCI DO KALENDÁŘE", type="primary", use_container_width=True):
            if n_nazev:
                try:
                    supabase.table("akce").insert({
                        "sdh_id": st.session_state.sdh_id, "datum": str(n_datum), "nazev_akce": n_nazev, "typ_akce": n_typ, "poznamka": n_poznamka
                    }).execute()
                    st.success("Událost uložena.")
                    st.rerun()
                except Exception as e: st.error(f"Chyba: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

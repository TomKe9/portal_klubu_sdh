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
import re
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

# Moderní CSS styly pro globální vzhled aplikaci
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [data-testid="stSidebar"] { font-family: 'Inter', sans-serif; }
    
    .dashboard-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #f0f0f0;
        margin-bottom: 20px;
        color: #1a1a1a;
    }
    .poplach-card {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        border-left: 6px solid #e53935;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 25px;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-success { background-color: #e8f5e9; color: #2e7d32; }
    .badge-danger { background-color: #ffebee; color: #c62828; }
    .badge-info { background-color: #e3f2fd; color: #1565c0; }
    .metric-value { font-size: 24px; font-weight: 700; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# Inicializace session state prvků
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
    st.session_state.stranka = "🚨 POPLACH & Výjezd"

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
    if str(avatar_data).startswith("data:image"):
        return f"""<img src="{avatar_data}" style="border-radius: 50%; width: 45px; height: 45px; object-fit: cover; vertical-align: middle; margin-right: 12px; border: 2px solid #e0e0e0;">"""
    return f"""<span style="font-size: 32px; vertical-align: middle; margin-right: 12px;">{avatar_data}</span>"""

def generuj_qr_kod_url(iban, castka, zprava):
    cistý_iban = re.sub(r'\s+', '', iban)
    zprava_url = urllib.parse.quote(zprava[:20])
    return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={cistý_iban[2:]}&bankCode={cistý_iban[2:6]}&amount={castka}&currency=CZK&message={zprava_url}"

# Hlavička
st.markdown("""
<div style="padding: 10px 0px 20px 0px;">
    <h1 style="margin: 0; font-weight: 700; color: #1e1e1e;">🚒 Hasičský Portál</h1>
    <p style="margin: 5px 0 0 0; color: #666; font-size: 1.05rem;">Chytré řízení sboru a výjezdové jednotky</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 2. AUTORIZACE (PŘIHLÁŠENÍ & REGISTRACE)
# ==========================================
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔒 Bezpečné přihlášení", "📝 Registrace nového člena / sboru"])
    
    with tab1:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        login_input = st.text_input("E-mail nebo uživatelská přezdívka", key="login_username_input").strip()
        login_heslo = st.text_input("Heslo", type="password", key="login_heslo_input")
        
        if st.button("Autorizovat vstup", type="primary", use_container_width=True):
            if login_input and login_heslo:
                # Bezpečný dvoukrokový dotaz - nejprve zkusíme e-mail
                res = supabase.table("uzivatele").select("*, sbory(nazev_sdh, iban)").eq("email", login_input).execute()
                
                # Pokud podle e-mailu nenajdeme, zkusíme přezdívku (pokud v DB sloupec existuje)
                if not res.data:
                    try:
                        res = supabase.table("uzivatele").select("*, sbory(nazev_sdh, iban)").eq("prezdivka", login_input).execute()
                    except Exception:
                        res.data = [] # Ošetření případu, kdy sloupec prezdivka v DB vůbec není

                if res.data:
                    user = res.data[0]
                    if bcrypt.checkpw(login_heslo.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                        st.session_state.logged_in = True
                        st.session_state.user_id = user["id"]
                        st.session_state.user_jmeno = f"{user['jmeno']} {user['prijmeni']}"
                        st.session_state.user_role = user["role"]
                        st.session_state.user_schvalen = user.get("schvalen", True)
                        st.session_state.sdh_id = user["sdh_id"]
                        st.session_state.sdh_nazev = user["sbory"]["nazev_sdh"]
                        st.session_state.sdh_iban = user["sbory"].get("iban", "CZ1234567890123456789012")
                        st.session_state.user_avatar = ziskej_avatar_uzivatele(user["id"])
                        st.rerun()
                    else: 
                        st.error("Zadané heslo není správné.")
                else: 
                    st.error("Uživatel s tímto e-mailem nebo přezdívkou neexistuje.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        sbory_res = supabase.table("sbory").select("*").execute()
        seznam_sboru = {s["nazev_sdh"]: s["id"] for s in sbory_res.data} if sbory_res.data else {}
        volba_sboru = st.radio("Zvolte typ registrace:", ["Přidat se k existujícímu sboru", "Zaregistrovat nový sbor"])
        
        vybrany_sdh_id, novy_sbor_nazev, novy_sbor_iban = None, "", ""
        if volba_sboru == "Přidat se k existujícímu sboru":
            if seznam_sboru:
                vybrany_sbor_nazev = st.selectbox("Vyberte sbor:", list(seznam_sboru.keys()))
                vybrany_sdh_id = seznam_sboru[vybrany_sbor_nazev]
        else:
            novy_sbor_nazev = st.text_input("Název sboru (např. SDH Lhota)").strip()
            novy_sbor_iban = st.text_input("Bankovní účet sboru (IBAN)").strip()
            
        reg_jmeno = st.text_input("Jméno")
        reg_prijmeni = st.text_input("Příjmení")
        reg_email = st.text_input("E-mail", key="reg_email_input")
        reg_heslo = st.text_input("Heslo", type="password", key="reg_heslo_input")
        vybrana_role = st.selectbox("Zařazení v jednotce/sboru:", ["velitel", "strojník", "hasič", "člen"])
        
        if st.button("Odeslat registraci", type="secondary"):
            if reg_jmeno and reg_prijmeni and reg_email and reg_heslo and (vybrany_sdh_id or novy_sbor_nazev):
                try:
                    if volba_sboru == "Zaregistrovat nový sbor":
                        sbor_ins = supabase.table("sbory").insert({"nazev_sdh": novy_sbor_nazev, "iban": novy_sbor_iban}).execute()
                        vybrany_sdh_id = sbor_ins.data[0]["id"]
                    
                    hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    je_prvni = len(supabase.table("uzivatele").select("id").eq("sdh_id", vybrany_sdh_id).execute().data) == 0
                    
                    supabase.table("uzivatele").insert({
                        "sdh_id": vybrany_sdh_id, "jmeno": reg_jmeno, "prijmeni": reg_prijmeni,
                        "email": reg_email, "heslo_hash": hashed, "role": vybrana_role, "schvalen": je_prvni
                    }).execute()
                    st.success("Registrace hotova! Pokud se přidáváte k existujícímu sboru, vyčkejte na schválení velitelem.")
                except Exception as e: st.error(f"Chyba při registraci: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 3. KONTROLA SCHVÁLENÍ PROFILU VELITELEM
# ==========================================
elif st.session_state.logged_in and not st.session_state.user_schvalen:
    st.warning("🔒 Váš účet zatím nebyl schválen velitelem nebo správcem vašeho sboru. Do schválení je přístup k interním datům uzamčen.")
    if st.button("Odhlásit se"):
        st.session_state.logged_in = False
        st.rerun()

# ==========================================
# 4. HLAVNÍ ROZHRANÍ PRO SCHVÁLENÉ ČLENY
# ==========================================
else:
    je_spravce = False
    vlastnik_res = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=False).limit(1).execute()
    if (vlastnik_res.data and vlastnik_res.data[0]["id"] == st.session_state.user_id) or st.session_state.user_role == "velitel":
        je_spravce = True

    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    st.sidebar.markdown(f"""
    <div style="display: flex; align-items: center; background-color: #f8f9fa; padding: 12px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #eee;">
        {zobraz_profilovku(st.session_state.user_avatar)}
        <div>
            <div style="font-weight: 600; color: #222;">{st.session_state.user_jmeno}</div>
            <div style="font-size: 0.8rem; color: #e53935; font-weight: 500;">{str(st.session_state.user_role).upper()}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.info(f"Sbor: {st.session_state.sdh_nazev}")
    
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
        
    volba = st.sidebar.radio("Navigace", menu_polozky)

    # --- MODUL: POPLACH ---
    if volba == "🚨 POPLACH & Výjezd":
        st.subheader("Výjezdový monitor JSDH")
        
        if je_spravce:
            with st.expander("🚨 VYHLÁSIT NOVÝ POPLACH"):
                pop_udalost = st.text_input("Druh události (např. Požár nízké budovy)")
                pop_misto = st.text_input("Místo / adresa zásahu")
                if st.button("Spustit poplach v systému", type="primary"):
                    if pop_udalost:
                        supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                        supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": pop_udalost, "misto": pop_misto}).execute()
                        st.success("Poplach byl vyhlášen!")
                        st.rerun()

        pop_res = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
        
        if pop_res.data:
            aktivni_poplach = pop_res.data[0]
            st.markdown(f"""
            <div class="poplach-card">
                <span class="badge badge-danger">⚠️ AKUTNÍ VÝJEZD JEDNOTKY</span>
                <h2 style="color: #c62828; margin: 10px 0;">{aktivni_poplach['udalost']}</h2>
                <p style="font-size: 1.1rem; margin: 5px 0;">📍 <b>Místo:</b> {aktivni_poplach['misto']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                if st.button("🟢 Jedu na zbrojnici", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": "ihned"}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p2:
                cas_min = st.selectbox("Dorazím za:", ["5 min", "10 min", "15 min"])
                if st.button("🟡 Jedu s prodlevou", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": cas_min}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p3:
                if st.button("🔴 Mimo výjezd (Nedorazím)", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Nedorazím", "cas_prijezdu": None}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()

            reakce_res = supabase.table("poplach_reakce").select("stav, cas_prijezdu, uzivatele(jmeno, prijmeni, role)").eq("poplach_id", aktivni_poplach["id"]).execute()
            if reakce_res.data:
                cg1, cg2 = st.columns(2)
                with cg1:
                    st.markdown("<div class='dashboard-card'><h4>✅ Na cestě do zbrojnice</h4>", unsafe_allow_html=True)
                    for r in reakce_res.data:
                        if r["stav"] == "Jedu na zbrojnici": st.write(f"🟢 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}** ({r['uzivatele']['role']}) - {r['cas_prijezdu']}")
                    st.markdown("</div>", unsafe_allow_html=True)
                with cg2:
                    st.markdown("<div class='dashboard-card'><h4>❌ Nedostupní</h4>", unsafe_allow_html=True)
                    for r in reakce_res.data:
                        if r["stav"] == "Nedorazím": st.write(f"🔴 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}**")
                    st.markdown("</div>", unsafe_allow_html=True)
            
            if je_spravce and st.button("❌ Ukončit / Odvolat poplach", type="secondary", use_container_width=True):
                supabase.table("poplachy").update({"aktivni": False}).eq("id", aktivni_poplach["id"]).execute()
                st.rerun()
        else:
            st.markdown("<div class='dashboard-card' style='border-top: 5px solid #4caf50;'>🎉 Žádný aktivní poplach. Jednotka je v klidu.</div>", unsafe_allow_html=True)

    # --- MODUL: KALENDÁŘ ---
    elif volba == "📅 Plán akcí & Docházka":
        st.subheader("Plán činností a docházka")
        akce_res = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).order("datum").execute()
        vsechny_akce = akce_res.data if akce_res.data else []
        
        kalendar_udalosti = []
        for akce in vsechny_akce:
            kalendar_udalosti.append({
                "id": str(akce["id"]), "title": akce["nazev_akce"], "start": akce["datum"], "end": akce["datum"], "allDay": True
            })
        
        calendar(events=kalendar_udalosti, options={"locale": "cs", "firstDay": 1}, key="portal_calendar")
        
        st.markdown("### 📋 Seznam nadcházejících událostí a moje účast")
        for akce in vsechny_akce:
            if akce["datum"] >= datetime.date.today().isoformat():
                with st.expander(f"📅 {akce['datum']} - {akce['nazev_akce']} ({akce['typ_akce']})"):
                    st.write(akce.get("poznamka", "Bez poznámky."))
                    
                    doch_res = supabase.table("dochazka").select("status").eq("akce_id", akce["id"]).eq("uzivatel_id", st.session_state.user_id).execute()
                    stav_moje = doch_res.data[0]["status"] if doch_res.data else "Nenahlášeno"
                    st.write(f"Můj stav: **{stav_moje}**")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("Jdu 👍", key=f"j_{akce['id']}"):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Jdu"}, on_conflict="akce_id,uzivatel_id").execute()
                        st.rerun()
                    if c2.button("Nejdu 👎", key=f"n_{akce['id']}"):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nejdu"}, on_conflict="akce_id,uzivatel_id").execute()
                        st.rerun()

    # --- MODUL: POKLADNA ---
    elif volba == "🪙 Pokladna & Příspěvky":
        st.subheader("Sborová pokladna a platba příspěvků")
        
        trans_res = supabase.table("pokladna").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
        vsechny_trans = trans_res.data if trans_res.data else []
        
        prijmy = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Příjem")
        vydaje = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Výdaj")
        
        wc1, wc2, wc3 = st.columns(3)
        with wc1: st.markdown(f"<div class='dashboard-card'>📈 Příjmy<div class='metric-value' style='color:green;'>{prijmy:,.2f} Kč</div></div>", unsafe_allow_html=True)
        with wc2: st.markdown(f"<div class='dashboard-card'>📉 Výdaje<div class='metric-value' style='color:red;'>{vydaje:,.2f} Kč</div></div>", unsafe_allow_html=True)
        with wc3: st.markdown(f"<div class='dashboard-card'>🪙 Stav konta<div class='metric-value'>{prijmy-vydaje:,.2f} Kč</div></div>", unsafe_allow_html=True)
        
        st.markdown("### 📱 Rychlá platba členského příspěvku přes QR kód")
        castka_p = st.number_input("Částka příspěvku (Kč):", value=500, step=100)
        msg = f"Prispevek {st.session_state.user_jmeno}"
        
        qr_url = generuj_qr_kod_url(st.session_state.sdh_iban, castka_p, msg)
        cq1, cq2 = st.columns([1, 2])
        with cq1: st.image(qr_url, width=220)
        with cq2: st.info(f"Naskenujte kód mobilním bankovnictvím.\n\nÚčet sboru: {st.session_state.sdh_iban}\nZpráva: {msg}")

    # --- MODUL: NÁSTĚNKA ---
    elif volba == "📢 Nástěnka sboru":
        st.subheader("Interní sdělení sboru")
        if je_spravce:
            with st.expander("📌 PŘIDAT OZNÁMENÍ"):
                nadpis = st.text_input("Nadpis")
                text = st.text_area("Text zprávy")
                if st.button("Publikovat"):
                    supabase.table("nastenka").insert({"sdh_id": st.session_state.sdh_id, "autor_jmeno": st.session_state.user_jmeno, "nadpis": nadpis, "text": text, "dulezite": False}).execute()
                    st.rerun()
                    
        zpravy = supabase.table("nastenka").select("*").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=True).execute().data
        for z in (zpravy if zpravy else []):
            st.markdown(f"""
            <div class='dashboard-card' style='border-left: 4px solid #1565c0;'>
                <h4>{z['nadpis']}</h4>
                <p>{z['text']}</p>
                <small style='color:gray;'>Zadal: {z['autor_jmeno']} | {z['created_at'][:10]}</small>
            </div>
            """, unsafe_allow_html=True)

    # --- MODUL: SKLAD ---
    elif volba == "📦 Sklad & Výstroj OOP":
        st.subheader("Evidence výstroje a majetku")
        vsechen_sklad = supabase.table("sklad").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).execute().data
        
        if je_spravce:
            with st.expander("➕ PRIDAT POLOŽKU DO SKLADU"):
                nazev_it = st.text_input("Název (např. Přilba Rosenbauer)")
                vel_it = st.text_input("Velikost")
                if st.button("Uložit do skladu"):
                    supabase.table("sklad").insert({"sdh_id": st.session_state.sdh_id, "nazev": nazev_it, "velikost": vel_it, "stav": "V pořádku"}).execute()
                    st.rerun()

        for i in (vsechen_sklad if vsechen_sklad else []):
            stav_text = f"👤 Vydáno: {i['uzivatele']['jmeno']} {i['uzivatele']['prijmeni']}" if i.get('uzivatele') else "📦 Skladem"
            st.markdown(f"<div class='dashboard-card'><b>{i['nazev']}</b> (Velikost: {i['velikost']}) — <span class='badge badge-info'>{stav_text}</span></div>", unsafe_allow_html=True)

    # --- MODUL: TECHNIKA ---
    elif volba == "🛠️ Technika & Revize":
        st.subheader("Správa techniky a vozového parku")
        tech = supabase.table("technika").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
        
        if je_spravce:
            with st.expander("➕ EVIDOVAT NOVOU TECHNIKU"):
                t_nazev = st.text_input("Název vozidla/agregátu")
                t_stk = st.date_input("Termín příští STK/revize")
                if st.button("Uložit techniku"):
                    supabase.table("technika").insert({"sdh_id": st.session_state.sdh_id, "nazev": t_nazev, "stk_revize": str(t_stk), "typ": "Vozidlo", "stav": "V pořádku"}).execute()
                    st.rerun()
                    
        for t in (tech if tech else []):
            st.markdown(f"<div class='dashboard-card'>🚒 <b>{t['nazev']}</b> <br> <small>Termín STK / revize: {t['stk_revize']}</small></div>", unsafe_allow_html=True)

    # --- MODUL: SEZNAM ČLENŮ ---
    elif volba == "🧑‍🚒 Seznam členů":
        st.subheader("Adresář členů sboru")
        clenove = supabase.table("uzivatele").select("jmeno, prijmeni, role, schvalen").eq("sdh_id", st.session_state.sdh_id).execute().data
        for c in (clenove if clenove else []):
            if c["schvalen"]:
                st.markdown(f"<div class='dashboard-card'>🧑‍🚒 <b>{c['jmeno']} {c['prijmeni']}</b> — Role: {c['role']}</div>", unsafe_allow_html=True)

    # --- MODUL: MOJE NASTAVENÍ ---
    elif volba == "⚙️ Moje nastavení":
        st.subheader("Osobní nastavení profilu")
        strav_avatar = ziskej_avatar_uzivatele(st.session_state.user_id)
        
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        novy_em = st.text_input("Změnit emoji ikonu profilu:", value=strav_avatar if not str(strav_avatar).startswith("data:image") else "🧑‍🚒")
        if st.button("Uložit profil"):
            uloz_avatar_uzivatele(st.session_state.user_id, novy_em)
            st.session_state.user_avatar = novy_em
            st.success("Profil upraven."); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.button("Odhlásit se ze systému", type="primary"):
            st.session_state.logged_in = False
            st.rerun()

    # --- MODUL: ADMIN VELITELE ---
    elif volba == "⚙️ Správa sboru (Velitel)" and je_spravce:
        st.subheader("Administrace sboru a schvalování členů")
        
        st.markdown("### 🔒 Členové čekající na schválení přístupu")
        neschvaleni = supabase.table("uzivatele").select("id, jmeno, prijmeni, email, role").eq("sdh_id", st.session_state.sdh_id).eq("schvalen", False).execute().data
        
        if neschvaleni:
            for u in neschvaleni:
                col_u1, col_u2 = st.columns([3, 1])
                with col_u1:
                    st.write(f"👤 **{u['jmeno']} {u['prijmeni']}** ({u['email']}) — Požadovaná role: `{u['role']}`")
                with col_u2:
                    if st.button("✅ Schválit přístup", key=f"schv_{u['id']}", use_container_width=True):
                        supabase.table("uzivatele").update({"schvalen": True}).eq("id", u["id"]).execute()
                        st.success(f"Uživatel {u['jmeno']} schválen!")
                        st.rerun()
        else:
            st.info("Žádost o přístup nepodal žádný nový člen.")
            
        st.markdown("<br><hr>### 📅 Naplánovat novou akci do kalendáře sboru", unsafe_allow_html=True)
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        n_nazev = st.text_input("Název události (např. Výroční schůze, Cvičení dýchací techniky)")
        n_typ = st.selectbox("Typ činnosti", ["Cvičení", "Schůze", "Soutěž", "Brigáda", "Zásah"])
        n_datum = st.date_input("Datum konání akce")
        n_poznamka = st.text_area("Bližší informace / instrukce pro členy")
        
        if st.button("Publikovat akci", type="primary", use_container_width=True):
            if n_nazev:
                supabase.table("akce").insert({
                    "sdh_id": st.session_state.sdh_id, "datum": str(n_datum), "nazev_akce": n_nazev, "typ_akce": n_typ, "poznamka": n_poznamka
                }).execute()
                st.success("Akce byla uložena a propíše se všem do kalendáře.")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

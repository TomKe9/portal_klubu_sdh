import streamlit as st
import pandas as pd
import os
import json
import bcrypt
import urllib.parse
from datetime import date
from supabase import create_client, Client
from streamlit_calendar import calendar

# ==========================================
# 1. KONFIGURACE & INICIALIZACE SYSTÉMU
# ==========================================
st.set_page_config(page_title="Hasičský Portál JSDH / SDH", page_icon="🚒", layout="wide", initial_sidebar_state="expanded")

# CSS styly
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=300;400;500;600;700&display=swap');
    html, body, [data-testid="stSidebar"] { font-family: 'Inter', sans-serif; }
    .card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f0f0; margin-bottom: 20px; }
    .poplach-card { background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); border-left: 6px solid #e53935; border-radius: 12px; padding: 24px; margin-bottom: 25px; }
    .badge { padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
    .bg-success { background-color: #e8f5e9; color: #2e7d32; }
    .bg-danger { background-color: #ffebee; color: #c62828; }
    .bg-info { background-color: #e3f2fd; color: #1565c0; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# ==========================================
# 2. POMOCNÉ FUNKCE & SESSION STATE
# ==========================================
SOUBOR_AVATARU = "profilovky_data.json"

def nacti_avatary():
    if os.path.exists(SOUBOR_AVATARU):
        with open(SOUBOR_AVATARU, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def uloz_avatar(user_id, avatar_data):
    data = nacti_avatary()
    data[str(user_id)] = avatar_data
    with open(SOUBOR_AVATARU, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

def ziskej_avatar(user_id):
    return nacti_avatary().get(str(user_id), "🧑‍🚒")

def generuj_qr(castka, zprava):
    iban = "CZ1234567890123456789012"
    return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={iban[2:]}&bankCode={iban[2:6]}&amount={castka}&currency=CZK&message={urllib.parse.quote(zprava[:20])}"

# Výchozí hodnoty Session State
session_defaults = {
    "logged_in": False, "user_id": None, "user_jmeno": "", "user_role": "člen",
    "sdh_id": None, "sdh_nazev": "", "user_avatar": "🧑‍🚒", "stranka": "🚨 POPLACH & Výjezd"
}
for k, v in session_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

def prihlas_uzivatele(user, zustat_prihlasen=False):
    st.session_state.update({
        "logged_in": True, "user_id": user["id"], "user_jmeno": f"{user['jmeno']} {user['prijmeni']}",
        "user_role": user["role"], "sdh_id": user["sdh_id"], "sdh_nazev": user["sbory"]["nazev_sdh"],
        "user_avatar": ziskej_avatar(user["id"]), "stranka": "🚨 POPLACH & Výjezd"
    })
    if zustat_prihlasen: st.query_params["user_id"] = str(user["id"])
    st.rerun()

# Trvalé přihlášení
if "user_id" in st.query_params and not st.session_state.logged_in:
    res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").eq("id", st.query_params["user_id"]).execute()
    if res.data: prihlas_uzivatele(res.data[0])

st.markdown("<div style='padding-bottom: 20px;'><h1 style='margin:0;'>🚒 Hasičský Portál</h1><p style='color:#666;'>Chytré řízení sboru a výjezdové jednotky</p></div>", unsafe_allow_html=True)

# ==========================================
# 3. HLAVNÍ ROZHRANÍ & BOČNÍ PANEL
# ==========================================
if st.session_state.logged_in:
    # Zjištění, zda je správce
    vlastnik = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at").limit(1).execute()
    je_spravce = bool(vlastnik.data and vlastnik.data[0]["id"] == st.session_state.user_id)

    # Profil v sidebaru
    st.sidebar.markdown(f"""
    <div style="display:flex; align-items:center; background:#f8f9fa; padding:12px; border-radius:10px; margin-bottom:15px; border:1px solid #eee;">
        <span style="font-size:32px; margin-right:12px;">{st.session_state.user_avatar}</span>
        <div><b>{st.session_state.user_jmeno}</b><br><span style="font-size:0.8rem; color:#e53935;">{st.session_state.user_role.upper()}</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.sidebar.button(f"🏢 {st.session_state.sdh_nazev}", use_container_width=True):
        st.session_state.stranka = "🧑‍🚒 Seznam členů sboru"; st.rerun()
    if st.sidebar.button("⚙️ Moje nastavení", use_container_width=True):
        st.session_state.stranka = "Moje nastavení"; st.rerun()
        
    st.sidebar.divider()
    
    # Menu
    menu = {
        "🚨 AKTIVNÍ SLUŽBA & VÝJEZDY": ["🚨 POPLACH & Výjezd", "📅 Plán akcí & Docházka", "📑 Kniha výjezdů & Export", "🗺️ Mapa vodních zdrojů"],
        "📦 VNITŘNÍ CHOD & MAJETEK": ["📢 Nástěnka sboru", "📦 Sklad & Výstroj OOP", "🎖️ Kvalifikace & Odbornost", "📊 Statistiky docházky", "🛠️ Technika & Revize", "🪙 Pokladna & Příspěvky", "🧑‍🚒 Seznam členů sboru"]
    }
    if je_spravce: menu["🛠️ ADMINISTRACE SBORU"] = ["⚙️ Správa sboru (Správce)"]

    flat_menu = [item for sublist in menu.values() for item in sublist]
    if st.session_state.stranka not in flat_menu: flat_menu.append(st.session_state.stranka)

    volba = st.sidebar.selectbox("Navigace systému", flat_menu, index=flat_menu.index(st.session_state.stranka))
    if st.session_state.stranka != volba:
        st.session_state.stranka = volba
        st.rerun()

    st.sidebar.write("")
    if st.sidebar.button("Odhlásit se", use_container_width=True, type="primary"):
        for k in session_defaults: st.session_state[k] = session_defaults[k]
        st.query_params.clear()
        st.rerun()

# ==========================================
# 4. NEPŘIHLÁŠENÝ UŽIVATEL (Login/Registrace)
# ==========================================
else:
    t1, t2 = st.tabs(["🔒 Přihlášení", "📝 Registrace"])
    with t1:
        with st.container(border=True):
            st.subheader("Vstup do systému")
            l_login = st.text_input("E-mail / Přezdívka").strip()
            l_heslo = st.text_input("Heslo", type="password")
            zustat = st.checkbox("Zůstat trvale přihlášen")
            if st.button("Přihlásit", type="primary", use_container_width=True):
                res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").or_(f"email.eq.{l_login},prezdivka.eq.{l_login}").execute()
                if res.data and bcrypt.checkpw(l_heslo.encode('utf-8'), res.data[0]["heslo_hash"].encode('utf-8')):
                    prihlas_uzivatele(res.data[0], zustat)
                else:
                    st.error("Neplatné přihlašovací údaje.")

    with t2:
        with st.container(border=True):
            st.subheader("Registrace")
            sbory = supabase.table("sbory").select("*").execute().data or []
            sbor_dict = {s["nazev_sdh"]: s["id"] for s in sbory}
            
            typ_reg = st.radio("Zvolte typ:", ["Existující sbor", "Nový sbor"])
            sdh_id, novy_sbor = None, ""
            
            if typ_reg == "Existující sbor" and sbor_dict:
                sdh_id = sbor_dict[st.selectbox("Vyberte sbor:", list(sbor_dict.keys()))]
            else:
                novy_sbor = st.text_input("Název nového sboru").strip()

            r_jmeno = st.text_input("Jméno")
            r_prijmeni = st.text_input("Příjmení")
            r_email = st.text_input("E-mail")
            r_heslo = st.text_input("Heslo", type="password")
            r_role = st.selectbox("Pozice:", ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"])

            if st.button("Zaregistrovat", type="secondary") and r_email and r_heslo:
                if typ_reg == "Nový sbor":
                    sdh_id = supabase.table("sbory").insert({"nazev_sdh": novy_sbor}).execute().data[0]["id"]
                hashed = bcrypt.hashpw(r_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                supabase.table("uzivatele").insert({
                    "sdh_id": sdh_id, "jmeno": r_jmeno, "prijmeni": r_prijmeni, "email": r_email, "heslo_hash": hashed, "role": r_role
                }).execute()
                st.success("Úspěšně registrováno! Můžete se přihlásit.")

# ==========================================
# 5. KATEGORIE & MODULY (Přihlášený uživatel)
# ==========================================
elif st.session_state.logged_in:

    # --- POPLACH & VÝJEZD ---
    if volba == "🚨 POPLACH & Výjezd":
        st.subheader("Výjezdový monitor")
        if je_spravce:
            with st.expander("🚨 VYHLÁŠENÍ POPLACHU"):
                p_udalost = st.text_input("Druh události")
                p_misto = st.text_input("Místo události")
                if st.button("VYHLÁSIT", type="primary"):
                    supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                    supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": p_udalost, "misto": p_misto}).execute()
                    st.rerun()

        poplach = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
        
        if poplach.data:
            p = poplach.data[0]
            st.markdown(f"""
            <div class="poplach-card">
                <span class="badge bg-danger">⚠️ AKUTNÍ VÝJEZD</span>
                <h2 style="color:#c62828;">{p['udalost']}</h2>
                <p>📍 <b>{p['misto']}</b><br><small>Vyhlášeno: {p['created_at'][11:16]}</small></p>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            def reaguj(stav, cas=None):
                supabase.table("poplach_reakce").upsert({"poplach_id": p["id"], "uzivatel_id": st.session_state.user_id, "stav": stav, "cas_prijezdu": cas}, on_conflict="poplach_id,uzivatel_id").execute()
                st.rerun()

            if c1.button("🟢 Jedu ihned", use_container_width=True): reaguj("Jedu", "ihned")
            with c2:
                if st.button("🟡 Jedu se zpožděním", use_container_width=True): reaguj("Jedu", st.selectbox("Za:", ["5 min", "10 min", "15 min"]))
            if c3.button("🔴 Nedorazím", use_container_width=True): reaguj("Nedorazím")

            st.divider()
            st.subheader("Připravenost posádky")
            reakce = supabase.table("poplach_reakce").select("stav, cas_prijezdu, uzivatele(jmeno, prijmeni, role)").eq("poplach_id", p["id"]).execute().data or []
            
            rg1, rg2 = st.columns(2)
            with rg1:
                st.markdown("<div class='card' style='border-top:4px solid #4caf50;'><h4>✅ Na cestě</h4>", unsafe_allow_html=True)
                for r in [x for x in reakce if x["stav"] == "Jedu"]: st.write(f"🟢 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}** ({r['cas_prijezdu']})")
                st.markdown("</div>", unsafe_allow_html=True)
            with rg2:
                st.markdown("<div class='card' style='border-top:4px solid #f44336;'><h4>❌ Omluveni</h4>", unsafe_allow_html=True)
                for r in [x for x in reakce if x["stav"] == "Nedorazím"]: st.write(f"🔴 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}**")
                st.markdown("</div>", unsafe_allow_html=True)

            if je_spravce and st.button("❌ Ukončit poplach", use_container_width=True):
                supabase.table("poplachy").update({"aktivni": False}).eq("id", p["id"]).execute()
                st.rerun()
        else:
            st.success("🎉 Jednotka je v klidu, žádný aktivní výjezd.")

    # --- PLÁN & DOCHÁZKA ---
    elif volba == "📅 Plán akcí & Docházka":
        st.subheader("Kalendář akcí")
        akce = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        events = [{"title": a["nazev_akce"], "start": a["datum"], "end": a["datum"]} for a in akce]
        calendar(events=events, options={"locale": "cs"})
        
        st.divider()
        dnes = date.today().isoformat()
        t_budouci, t_minule = st.tabs(["📋 Nadcházející", "🗄️ Archiv"])
        
        def vykresli_akce(seznam):
            for a in seznam:
                with st.expander(f"{a['datum']} - {a['nazev_akce']} ({a['typ_akce']})"):
                    st.write(a.get("poznamka", ""))
                    if st.button("Zapsat účast", key=f"btn_{a['id']}"): st.toast("Účast zaznamenána!") # Zjednodušená ukázka
        
        with t_budouci: vykresli_akce([a for a in akce if a["datum"] >= dnes])
        with t_minule: vykresli_akce([a for a in akce if a["datum"] < dnes])

    # --- KNIHA VÝJEZDŮ ---
    elif volba == "📑 Kniha výjezdů & Export":
        st.subheader("Přehled zásahů")
        zasahy = supabase.table("akce").select("datum, cas, nazev_akce, cislo_vyjezdu, pouzita_technika").eq("sdh_id", st.session_state.sdh_id).eq("typ_akce", "Zásah").execute().data
        if zasahy:
            df = pd.DataFrame(zasahy)
            st.dataframe(df, use_container_width=True)
            st.download_button("📥 Export (CSV)", df.to_csv(index=False), "vyjezdy.csv", "text/csv")
        else:
            st.info("Žádné evidované zásahy.")

    # --- MAPA VODNÍCH ZDROJŮ ---
    elif volba == "🗺️ Mapa vodních zdrojů":
        st.subheader("Hydrantová síť")
        if je_spravce:
            with st.expander("➕ Přidat zdroj"):
                v_nazev, v_typ = st.text_input("Název"), st.selectbox("Typ", ["Nadzemní", "Podzemní", "Nádrž"])
                v_lat, v_lon = st.number_input("Lat", format="%.5f"), st.number_input("Lon", format="%.5f")
                if st.button("Uložit"):
                    supabase.table("vodni_zdroje").insert({"sdh_id": st.session_state.sdh_id, "nazev": v_nazev, "typ": v_typ, "latitude": v_lat, "longitude": v_lon}).execute()
                    st.rerun()

        zdroje = supabase.table("vodni_zdroje").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
        if zdroje:
            st.map(pd.DataFrame(zdroje))
            for z in zdroje: st.write(f"📍 **{z['nazev']}** ({z['typ']})")
            
    # --- NÁSTĚNKA ---
    elif volba == "📢 Nástěnka sboru":
        st.subheader("Aktuální oznámení")
        if je_spravce:
            with st.expander("📌 Nové oznámení"):
                n_nadpis, n_text = st.text_input("Nadpis"), st.text_area("Text")
                if st.button("Publikovat") and n_nadpis:
                    supabase.table("nastenka").insert({"sdh_id": st.session_state.sdh_id, "autor_jmeno": st.session_state.user_jmeno, "nadpis": n_nadpis, "text": n_text, "dulezite": False}).execute()
                    st.rerun()

        zpravy = supabase.table("nastenka").select("*").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=True).execute().data or []
        for z in zpravy:
            st.markdown(f"<div class='card'><h3>{z['nadpis']}</h3><p>{z['text']}</p><small>{z['autor_jmeno']}</small></div>", unsafe_allow_html=True)

    # --- SKLAD ---
    elif volba == "📦 Sklad & Výstroj OOP":
        st.subheader("Sklad a výstroj")
        cleni = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        slovnik_clenu = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cleni}

        tm, ts = st.tabs(["🎒 Moje výstroj", "🔧 Správa skladu"])
        with tm:
            moje = supabase.table("sklad").select("*").eq("prideleno_uzivatel_id", st.session_state.user_id).execute().data or []
            for item in moje: st.info(f"🧥 **{item['nazev']}** (Vel.: {item['velikost']})")
        
        with ts:
            if je_spravce:
                with st.expander("➕ Přidat do skladu"):
                    mat, vel = st.text_input("Materiál"), st.text_input("Velikost")
                    kdo = st.selectbox("Přiřadit:", ["Skladem"] + list(slovnik_clenu.keys()))
                    if st.button("Naskladnit"):
                        supabase.table("sklad").insert({"sdh_id": st.session_state.sdh_id, "nazev": mat, "velikost": vel, "prideleno_uzivatel_id": slovnik_clenu.get(kdo)}).execute()
                        st.rerun()

            sklad_vse = supabase.table("sklad").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).execute().data or []
            for i in sklad_vse:
                vlastnik = f"{i['uzivatele']['jmeno']} {i['uzivatele']['prijmeni']}" if i.get("uzivatele") else "Skladem"
                st.write(f"📦 **{i['nazev']}** ({i['velikost']}) -> {vlastnik}")

    # --- KVALIFIKACE ---
    elif volba == "🎖️ Kvalifikace & Odbornost":
        st.subheader("Platnost licencí a odborností")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute()
        slovnik_hasicu = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cl_res.data} if cl_res.data else {}
        
        if je_spravce:
            with st.expander("➕ Zapsat kvalifikaci"):
                k_hasic = st.selectbox("Vyberte hasiče:", list(slovnik_hasicu.keys()))
                k_typ = st.text_input("Typ kvalifikace (např. Dýchací technika, Řidič, Pilař)")
                k_platnost = st.date_input("Platnost do:")
                
                if st.button("Uložit kvalifikaci", type="primary"):
                    try:
                        supabase.table("kvalifikace").insert({
                            "sdh_id": st.session_state.sdh_id, 
                            "uzivatel_id": slovnik_hasicu[k_hasic], 
                            "typ": k_typ, 
                            "platnost_do": k_platnost.isoformat()
                        }).execute()
                        st.success("Kvalifikace byla úspěšně přidána.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Chyba při ukládání: {e}")

        st.markdown("<br><h4>📋 Přehled kvalifikací jednotky</h4>", unsafe_allow_html=True)
        kvalifikace_res = supabase.table("kvalifikace").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).order("platnost_do").execute()
        
        if kvalifikace_res.data:
            dnes = date.today().isoformat()
            for kv in kvalifikace_res.data:
                je_propadla = kv["platnost_do"] < dnes
                barva = "red" if je_propadla else "green"
                status = "🔴 Propadlé" if je_propadla else "🟢 Platné"
                
                st.markdown(f"""
                <div class="card" style="border-left: 4px solid {barva}; padding: 15px;">
                    <b>{kv['uzivatele']['jmeno']} {kv['uzivatele']['prijmeni']}</b> — {kv['typ']}<br>
                    <span style="color: {barva}; font-size: 0.9em;">{status} (do {kv['platnost_do']})</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Zatím nejsou evidovány žádné kvalifikace.")

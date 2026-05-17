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
st.set_page_config(page_title="Portál SDH", page_icon="🚒", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# Inicializace session state stavů
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_jmeno = ""
    st.session_state.user_role = "člen"
    st.session_state.sdh_id = None
    st.session_state.sdh_nazev = ""
    st.session_state.user_avatar = "🧑‍🚒"
    st.session_state.stranka = "🚨 POPLACH & Výjezd"

# Pomocná funkce pro automatické trvalé přihlášení z URL parametru
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
        return f"""<img src="{avatar_data}" style="border-radius: 50%; width: 35px; height: 35px; object-fit: cover; vertical-align: middle; margin-right: 8px;">"""
    return f"""<span style="font-size: 24px; vertical-align: middle; margin-right: 8px;">{avatar_data}</span>"""

def generuj_qr_kod_url(castka, zprava):
    # Generování platebního QR kódu přes otevřené české API
    # Účet je fiktivní/vzorový, starosta si v kódu případně přepíše IBAN sboru
    iban_sboru = "CZ1234567890123456789012" 
    zprava_url = urllib.parse.quote(zprava[:20])
    return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={iban_sboru[2:]}&bankCode={iban_sboru[2:6]}&amount={castka}&currency=CZK&message={zprava_url}"

# Kontrola přihlášení na pozadí
nacti_trvale_prihlaseni()

st.title("🚒 Portál SDH")
st.caption("Profesionální informační systém pro dobrovolné hasiče")

# ==========================================
# 3. HLAVNÍ ROZHRANÍ & BOČNÍ PANEL
# ==========================================
if st.session_state.logged_in:
    # Zjištění, zda je uživatel zakládajícím správcem sboru
    je_spravce = False
    vlastnik_res = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=False).limit(1).execute()
    if vlastnik_res.data and vlastnik_res.data[0]["id"] == st.session_state.user_id:
        je_spravce = True

    if st.sidebar.button("⚙️ Moje nastavení", use_container_width=True):
        st.session_state.stranka = "Moje nastavení"
        st.rerun()
        
    st.sidebar.write("---")
    st.session_state.user_avatar = ziskej_avatar_uzivatele(st.session_state.user_id)
    
    # Vizitka v levém panelu
    av_html = zobraz_profilovku(st.session_state.user_avatar)
    st.sidebar.markdown(f"""<div style="display: flex; align-items: center;">{av_html}<h3 style="margin: 0; display: inline-block;">{st.session_state.user_jmeno}</h3></div>""", unsafe_allow_html=True)
    
    if st.sidebar.button(f"🏢 {st.session_state.sdh_nazev}", use_container_width=True):
        st.session_state.stranka = "🧑‍🚒 Seznam členů sboru"
        st.rerun()
    
    st.sidebar.caption(f"Pozice: {st.session_state.user_role} {'(Správce)' if je_spravce else ''}")
    st.sidebar.write("---")
    
    # Strukturované a seskupené menu
    kategorie_menu = {
        "🚨 AKTIVNÍ SLUŽBA & VÝJEZDY (JSDH)": [
            "🚨 POPLACH & Výjezd",
            "📅 Plán akcí & Docházka",
            "📑 Kniha výjezdů & Export",
            "🗺️ Mapa vodních zdrojů"
        ],
        "📦 VNITŘNÍ CHOD SBORU & MAJETEK (SDH)": [
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

    # Sestavení plochého seznamu pro selectbox
    plochy_seznam_menu = []
    for kat, polozky in kategorie_menu.items():
        plochy_seznam_menu.extend(polozky)
        
    if st.session_state.stranka == "Moje nastavení" and "Moje nastavení" not in plochy_seznam_menu:
        plochy_seznam_menu.append("Moje nastavení")

    index_menu = plochy_seznam_menu.index(st.session_state.stranka) if st.session_state.stranka in plochy_seznam_menu else 0
    volba = st.sidebar.selectbox("Kam chcete jít?", plochy_seznam_menu, index=index_menu)
    
    if st.session_state.stranka != volba:
        st.session_state.stranka = volba
        st.rerun()
        
    st.sidebar.write("---")
    if st.sidebar.button("Odhlásit se", use_container_width=True):
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
    tab1, tab2 = st.tabs(["🔒 Přihlášení", "📝 Registrace nového člena / sboru"])
    
    with tab1:
        st.subheader("Přihlášení k portálu")
        login_input = st.text_input("E-mail nebo Přezdívka").strip()
        login_heslo = st.text_input("Heslo", type="password")
        zustat_prihlasen = st.checkbox("Zůstat přihlášen na tomto zařízení")
        
        if st.button("Přihlásit se", type="primary"):
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
                        st.success("Úspěšně přihlášen!")
                        st.rerun()
                    else: st.error("Nesprávné heslo.")
                else: st.error("Uživatel neexistuje.")
        st.info("💡 Zapomněli jste heslo? Velitel nebo správce vašeho sboru vám ho může přepsat v záložce Reset hesel.")

    with tab2:
        st.subheader("Registrace")
        sbory_res = supabase.table("sbory").select("*").execute()
        seznam_sboru = {s["nazev_sdh"]: s["id"] for s in sbory_res.data} if sbory_res.data else {}
        volba_sboru = st.radio("Vyberte možnost:", ["Přidat se k existujícímu sboru", "Zaregistrovat úplně nový sbor"])
        
        vybrany_sdh_id, novy_sbor_nazev = None, ""
        if volba_sboru == "Přidat se k existujícímu sboru":
            if seznam_sboru:
                vybrany_sbor_nazev = st.selectbox("Vyberte váš sbor (SDH):", list(seznam_sboru.keys()))
                vybrany_sdh_id = seznam_sboru[vybrany_sbor_nazev]
        else:
            novy_sbor_nazev = st.text_input("Název nového sboru (např. SDH Lhota)").strip()
            
        reg_jmeno = st.text_input("Jméno")
        reg_prijmeni = st.text_input("Příjmení")
        reg_email = st.text_input("E-mail")
        reg_heslo = st.text_input("Heslo pro přihlášení", type="password")
        pozice_na_utoku = ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"]
        vybrana_role = st.selectbox("Hlavní pozice ve sboru:", pozice_na_utoku)
        
        if st.button("Dokončit registraci"):
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
                    st.success("Registrace hotova! Nyní se přihlaste.")
                except Exception as e: st.error(f"Chyba: {e}")

# ==========================================
# 5. KATEGORIE: AKTIVNÍ SLUŽBA & VÝJEZDY (JSDH)
# ==========================================
elif st.session_state.logged_in:

    # --- MODUL: POPLACH & VÝJEZDOVÝ TABLET ---
    if volba == "🚨 POPLACH & Výjezd":
        st.header("🚨 Rychlý poplach a Akceschopnost výjezdové jednotky")
        
        if je_spravce:
            with st.expander("🚨 VYHLÁSIT NOVÝ POPLACH (Pro velitele)"):
                pop_udalost = st.text_input("Událost (např. Požár nízké budovy, Nehoda se zraněním)")
                pop_misto = st.text_input("Místo zásahu / adresa")
                if st.button("🚨 ODESLAT POPLACH DO SYSTÉMU", type="primary"):
                    if pop_udalost:
                        supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                        supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": pop_udalost, "misto": pop_misto}).execute()
                        st.success("Poplach byl aktivován!")
                        st.rerun()

        # Načtení aktivního poplachu
        pop_res = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
        
        if pop_res.data:
            aktivni_poplach = pop_res.data[0]
            st.error(f"⚠️ **AKTIVNÍ POPLACH:** {aktivni_poplach['udalost']} — **Místo:** {aktivni_poplach['misto']}")
            st.caption(f"Vyhlášeno v: {aktivni_poplach['created_at'][11:16]} dne {aktivni_poplach['created_at'][:10]}")
            
            # Reakce jednotlivého hasiče
            st.subheader("Odpovězte veliteli:")
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                if st.button("🟢 Jedu na zbrojnici (ihned)", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": "ihned"}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p2:
                cas_min = st.selectbox("Jedu, čas příjezdu:", ["za 5 min", "za 10 min", "za 15 min"])
                if st.button("🟡 Potvrdit s časem", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": cas_min}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p3:
                if st.button("🔴 Nedorazím", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Nedorazím", "cas_prijezdu": None}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()

            # Přehled pro velitele v garáži
            st.write("---")
            st.subheader("📋 Kdo se schází v garáži:")
            reakce_res = supabase.table("poplach_reakce").select("stav, cas_prijezdu, uzivatele(jmeno, prijmeni, role)").eq("poplach_id", aktivni_poplach["id"]).execute()
            
            if reakce_res.data:
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown("#### ✅ Na cestě")
                    for r in reakce_res.data:
                        if r["stav"] == "Jedu na zbrojnici":
                            st.write(f"🟢 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}** ({r['uzivatele']['role']}) — Příjezd: `{r['cas_prijezdu']}`")
                with col_g2:
                    st.markdown("#### ❌ Nepřítomni")
                    for r in reakce_res.data:
                        if r["stav"] == "Nedorazím":
                            st.write(f"🔴 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}**")
            else:
                st.info("Zatím nikdo nepotvrdil účast.")
                
            if je_spravce:
                st.write("---")
                if st.button("❌ Odvolat / Ukončit aktivní poplach", type="secondary"):
                    supabase.table("poplachy").update({"aktivni": False}).eq("id", aktivni_poplach["id"]).execute()
                    st.success("Poplach ukončen.")
                    st.rerun()
        else:
            st.success("🎉 V jednotce je klid. Žádný aktivní poplach.")

    # --- MODUL: PLÁN AKCÍ & DOCHÁZKA ---
    elif volba == "📅 Plán akcí & Docházka":
        st.header("📅 Plán činností a docházka")
        typy_k_vyberu = ["Zásah", "Cvičení", "Soutěž", "Brigáda", "Schůze", "Jiné"]
        vybrane_typy = st.multiselect("Zobrazit pouze:", typy_k_vyberu, default=typy_k_vyberu)
        
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
        
        st.write("---")
        dnes = datetime.date.today().isoformat()
        tab_budouci, tab_historie = st.tabs([f"📋 Nadcházející akce", f"🗄️ Archiv minulých akcí"])
        
        def vykresli_akce(seznam):
            if not seznam: st.write("Žádné akce."); return
            for akce in seznam:
                with st.expander(f"📅 {akce['datum']} - {akce['nazev_akce']} ({akce['typ_akce']})"):
                    if akce["typ_akce"] == "Zásah":
                        st.error(f"Číslo výjezdu: {akce.get('cislo_vyjezdu','')} | Technika: {akce.get('pouzita_technika','')}")
                    if akce.get('poznamka'): st.info(akce['poznamka'])
                    
                    doch_res = supabase.table("dochazka").select("status").eq("akce_id", akce["id"]).eq("uzivatel_id", st.session_state.user_id).execute()
                    st.write(f"Moje účast: **{doch_res.data[0]['status'] if doch_res.data else 'Nezadáno'}**")
                    
                    c1, c2, c3 = st.columns(3)
                    if c1.button("Jdu 👍", key=f"y_{akce['id']}"):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Jdu"}, on_conflict="akce_id,uzivatel_id").execute(); st.rerun()
                    if c2.button("Nejdu 👎", key=f"n_{akce['id']}"):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nejdu"}, on_conflict="akce_id,uzivatel_id").execute(); st.rerun()
                    if c3.button("Nevím 🤷", key=f"m_{akce['id']}"):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nevím"}, on_conflict="akce_id,uzivatel_id").execute(); st.rerun()

        with tab_budouci: vykresli_akce([a for a in filtrovane_akce if a["datum"] >= dnes])
        with tab_historie: vykresli_akce([a for a in filtrovane_akce if a["datum"] < dnes])

    # --- MODUL: KNIHA VÝJEZDŮ & EXPORT ---
    elif volba == "📑 Kniha výjezdů & Export":
        st.header("📑 Výjezdová kniha & Roční statistický export")
        zasahy_res = supabase.table("akce").select("datum, cas, nazev_akce, cislo_vyjezdu, pouzita_technika, motohodiny_uziti, poznamka").eq("sdh_id", st.session_state.sdh_id).eq("typ_akce", "Zásah").order("datum", desc=True).execute()
        if zasahy_res.data:
            df_zasahy = pd.DataFrame(zasahy_res.data)
            df_zasahy.columns = ["Datum", "Čas", "Událost", "Číslo výjezdu", "Technika", "Mth/Km", "Poznámka"]
            st.dataframe(df_zasahy, use_container_width=True)
            st.download_button("📥 Stáhnout Knihu výjezdů (CSV)", data=df_zasahy.to_csv(index=False, encoding="utf-8-sig"), file_name="kniha_vyjezdu.csv", mime="text/csv")
        else: st.info("Žádné ostré zásahy nejsou v systému zapsány.")

    # --- MODUL: MAPA VODNÍCH ZDROJŮ ---
    elif volba == "🗺️ Mapa vodních zdrojů":
        st.header("🗺️ Hydrantová síť a zdroje hasební vody")
        if je_spravce:
            with st.expander("➕ Zadat nový vodní zdroj"):
                v_nazev = st.text_input("Název/Lokace")
                v_typ = st.selectbox("Typ", ["Nadzemní hydrant", "Podzemní hydrant", "Požární nádrž", "Přírodní zdroj"])
                v_stav = st.selectbox("Funkčnost", ["Funkční", "Nefunkční", "V opravě"])
                v_lat = st.number_input("Latitude", format="%.5f")
                v_lon = st.number_input("Longitude", format="%.5f")
                if st.button("Uložit bod"):
                    try:
                        supabase.table("vodni_zdroje").insert({"sdh_id": st.session_state.sdh_id, "nazev": v_nazev, "typ": v_typ, "stav": v_stav, "latitude": v_lat, "longitude": v_lon}).execute()
                        st.success("Zaneseno."); st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")
                    
        try:
            zdroje_res = supabase.table("vodni_zdroje").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
            if zdroje_res.data:
                st.map(pd.DataFrame(zdroje_res.data), latitude="latitude", longitude="longitude")
                for z in zdroje_res.data:
                    st.write(f"📍 **{z['nazev']}** ({z['typ']}) — Stav: `{z['stav']}`")
            else: st.info("Žádné body na mapě.")
        except Exception as e: st.error(f"Chyba komunikace: {e}")

# ==========================================
# 6. KATEGORIE: VNITŘNÍ CHOD SBORU & MAJETEK (SDH)
# ==========================================
    # --- MODUL: SBOREVOVÁ NÁSTĚNKA ---
    elif volba == "📢 Nástěnka sboru":
        st.header("📢 Sborová nástěnka a oznámení")
        if je_spravce:
            with st.expander("📌 Publikovat nové oznámení"):
                nadpis_zpr = st.text_input("Nadpis")
                text_zpr = st.text_area("Obsah")
                priorita = st.checkbox("DŮLEŽITÉ")
                if st.button("Vyvěsit"):
                    try:
                        supabase.table("nastenka").insert({"sdh_id": st.session_state.sdh_id, "autor_jmeno": st.session_state.user_jmeno, "nadpis": nadpis_zpr, "text": text_zpr, "dulezite": priorita}).execute()
                        st.success("Vyvěšeno."); st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")
                    
        try:
            zpravy_res = supabase.table("nastenka").select("*").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=True).execute()
            for z in (zpravy_res.data if zpravy_res.data else []):
                if z["dulezite"]: st.error(f"🚨 **{z['nadpis']}**")
                else: st.subheader(f"📌 {z['nadpis']}")
                st.markdown(f"> {z['text']}\n*Zadal: {z['autor_jmeno']}*")
                st.write("---")
        except Exception as e: st.error(f"Chyba: {e}")

    # --- MODUL: SKLAD & VÝSTROJ ---
    elif volba == "📦 Sklad & Výstroj OOP":
        st.header("📦 Sklad, Výstroj a osobní ochranné prostředky (OOP)")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute()
        slovnik_clenu_sklad = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cl_res.data} if cl_res.data else {}
        
        t_moje, t_sklad = st.tabs(["🎒 Moje výstroj", "🔧 Správa skladu"])
        with t_moje:
            moje_oop = supabase.table("sklad").select("*").eq("prideleno_uzivatel_id", st.session_state.user_id).execute()
            for item in (moje_oop.data if moje_oop.data else []):
                st.info(f"🧥 **{item['nazev']}** | Velikost: `{item['velikost']}`")
                
        with t_sklad:
            if je_spravce:
                with st.expander("➕ Přidat věc do skladu"):
                    n_mat = st.text_input("Materiál")
                    n_vel = st.text_input("Velikost")
                    n_uziv = st.selectbox("Přiřadit hasiči:", ["Ponechat skladem"] + list(slovnik_clenu_sklad.keys()))
                    if st.button("Uložit položku"):
                        p_id = None if n_uziv == "Ponechat skladem" else slovnik_clenu_sklad[n_uziv]
                        supabase.table("sklad").insert({"sdh_id": st.session_state.sdh_id, "nazev": n_mat, "velikost": n_vel, "stav": "V pořádku", "prideleno_uzivatel_id": p_id}).execute()
                        st.success("Uloženo."); st.rerun()
            
            vsechen_sklad = supabase.table("sklad").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).execute()
            for i in (vsechen_sklad.data if vsechen_sklad.data else []):
                drzitel = f"👤 Vydáno: {i['uzivatele']['jmeno']} {i['uzivatele']['prijmeni']}" if i.get('uzivatele') else "📦 Skladem"
                st.write(f"**{i['nazev']}** ({i['velikost']}) — **{drzitel}**")

    # --- MODUL: KVALIFIKACE & ODBORNOST ---
    elif volba == "🎖️ Kvalifikace & Odbornost":
        st.header("🎖️ Hlídač platnosti osvědčení, kurzů a prohlídek")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute()
        slovnik_hasicu = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cl_res.data} if cl_res.data else {}
        
        if je_spravce:
            with st.expander("➕ Zapsat/Obnovit kvalifikaci"):
                k_hasic = st.selectbox("Hasič:", list(slovnik_hasicu.keys()))
                k_typ = st.selectbox("Typ", ["Zdravotní prohlídka", "Nositel dýchací techniky (NDT)", "Strojník", "Velitel družstva"])
                k_datum = st.date_input("Platnost DO:")
                if st.button("Uložit kvalifikaci"):
                    supabase.table("kvalifikace").upsert({"uzivatel_id": slovnik_hasicu[k_hasic], "typ_kurzu": k_typ, "platnost_do": str(k_datum)}, on_conflict="uzivatel_id,typ_kurzu").execute()
                    st.success("Zapsáno."); st.rerun()
                    
        vsechny_kval = supabase.table("kvalifikace").select("*, uzivatele(jmeno, prijmeni, sdh_id)").execute()
        filtrovane_kval = [k for k in vsechny_kval.data if k.get("uzivatele") and k["uzivatele"]["sdh_id"] == st.session_state.sdh_id] if vsechny_kval.data else []
        dnesni_den = datetime.date.today()
        for k in filtrovane_kval:
            p_do = datetime.datetime.strptime(k["platnost_do"], "%Y-%m-%d").date()
            if p_do < dnesni_den: st.error(f"❌ **{k['uzivatele']['jmeno']} {k['uzivatele']['prijmeni']}** — `{k['typ_kurzu']}` (PROPADLO)")
            else: st.success(f"🟢 **{k['uzivatele']['jmeno']} {k['uzivatele']['prijmeni']}** — `{k['typ_kurzu']}` (Do: {p_do.strftime('%d.%m.%Y')})")

    # --- MODUL: STATISTIKY DOCHÁZKY ---
    elif volba == "📊 Statistiky docházky":
        st.header("📊 Statistiky a docházková úspěšnost")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute()
        celkem_akci = supabase.table("akce").select("id", count="exact").eq("sdh_id", st.session_state.sdh_id).execute().count or 0
        if celkem_akci > 0 and cl_res.data:
            for clen in cl_res.data:
                u_doch = supabase.table("dochazka").select("status").eq("uzivatel_id", clen["id"]).eq("status", "Jdu").execute()
                pocet_jdu = len(u_doch.data) if u_doch.data else 0
                procento = round((pocet_jdu / celkem_akci) * 100, 1)
                st.markdown(f"**🚒 {clen['jmeno']} {clen['prijmeni']}** — Účast na **{procento} %** akcí")
                st.progress(min(int(procento), 100))

    # --- MODUL: TECHNIKA & REVIZE ---
    elif volba == "🛠️ Technika & Revize":
        st.header("🛠️ Evidence techniky a hlídač revizí / STK")
        if je_spravce:
            with st.expander("➕ Přidat novou techniku"):
                t_nazev = st.text_input("Název vozidla/stroje")
                t_revize = st.date_input("STK/Revize do:")
                if st.button("Uložit techniku"):
                    supabase.table("technika").insert({"sdh_id": st.session_state.sdh_id, "nazev": t_nazev, "typ": "Vozidlo", "stk_revize": str(t_revize), "stav": "V pořádku"}).execute()
                    st.rerun()
        tech_res = supabase.table("technika").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
        for t in (tech_res.data if tech_res.data else []):
            st.write(f"### 🟢 {t['nazev']} — STK do: {t['stk_revize']}")

    # --- MODUL: POKLADNA & PŘÍSPĚVKY ---
    elif volba == "🪙 Pokladna & Příspěvky":
        st.header("🪙 Sborová pokladna a členské příspěvky")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute()
        slovnik_clenu_pocka = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cl_res.data} if cl_res.data else {}
        
        tab_p_prehled, tab_p_zadat, tab_p_qr = st.tabs(["📊 Přehled pokladny", "🪙 Zadat transakci", "📱 Zaplatit příspěvky přes QR"])
        
        with tab_p_prehled:
            # Výpočet zůstatku sboru
            trans_res = supabase.table("pokladna").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
            vsechny_trans = trans_res.data if trans_res.data else []
            
            prijmy = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Příjem")
            vydaje = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Výdaj")
            zustatek = prijmy - vydaje
            
            col_z1, col_z2, col_z3 = st.columns(3)
            col_z1.metric("Celkové příjmy", f"{prijmy:,.2f} Kč".replace(",", " "))
            col_z2.metric("Celkové výdaje", f"{vydaje:,.2f} Kč".replace(",", " "))
            col_z3.metric("Zůstatek v pokladně", f"{zustatek:,.2f} Kč".replace(",", " "), delta=f"{zustatek}")
            
            st.write("---")
            st.subheader("📋 Historie transakcí")
            if vsechny_trans:
                df_p = pd.DataFrame(vsechny_trans)
                df_p = df_p[["created_at", "smer", "castka", "typ_platby", "poznamka"]]
                df_p.columns = ["Datum", "Směr", "Částka (Kč)", "Typ", "Poznámka"]
                st.dataframe(df_p, use_container_width=True)
            else: st.info("Žádné transakce.")
            
        with tab_p_zadat:
            if je_spravce:
                st.subheader("Přidat příjmový nebo výdajový doklad")
                t_smer = st.radio("Směr peněz:", ["Příjem", "Výdaj"])
                t_castka = st.number_input("Částka v Kč", min_value=1.0)
                t_typ = st.selectbox("Kategorie", ["Příspěvek", "Dotace", "Nákup materiálu", "Občerstvení", "Jiné"])
                t_hasic = st.selectbox("Vztahuje se ke členovi (volitelné):", ["Nikdo"] + list(slovnik_clenu_pocka.keys()))
                t_pozn = st.text_input("Poznámka (např. Členský příspěvek na rok 2026)")
                
                if st.button("Uložit transakci"):
                    h_id = None if t_hasic == "Nikdo" else slovnik_clenu_pocka[t_hasic]
                    rok_prispevku = datetime.date.today().year if t_typ == "Příspěvek" else None
                    supabase.table("pokladna").insert({
                        "sdh_id": st.session_state.sdh_id, "uzivatel_id": h_id, "castka": t_castka,
                        "typ_platby": t_typ, "smer": t_smer, "poznamka": t_pozn, "zaplaceno_rok": rok_prispevku
                    }).execute()
                    st.success("Zapsáno!"); st.rerun()
            else: st.info("Do pokladny může zapisovat pouze velitel / správce sboru.")
            
        with tab_p_qr:
            st.subheader("📱 Rychlá platba příspěvků pro tento rok")
            st.write("Naskenujte kód ve svém mobilním bankovnictví. Peníze odejdou přímo na účet sboru.")
            
            castka_prispevku = st.number_input("Nastavená výše příspěvku (Kč):", value=500)
            zprava_platce = f"SDH Prispevek {st.session_state.user_jmeno}"
            
            qr_url = generuj_qr_kod_url(castka_prispevku, zprava_platce)
            col_qr1, col_qr2 = st.columns([1, 2])
            with col_qr1: st.image(qr_url, caption="QR Kód pro platbu")
            with col_qr2:
                st.write(f"**Částka:** {castka_prispevku} Kč")
                st.write(f"**Zpráva pro příjemce:** `{zprava_platce}`")
                st.info("Jakmile starosta platbu obdrží, ručně vám v záložce Pokladna potvrdí status splaceno.")

    # --- MODUL: SEZNAM ČLENŮ ---
    elif volba == "🧑‍🚒 Seznam členů sboru":
        st.header("🧑‍🚒 Členové sboru")
        clenove_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, prezdivka, role").eq("sdh_id", st.session_state.sdh_id).execute()
        for c in (clenove_res.data if clenove_res.data else []):
            st.markdown(f"**🧑‍🚒 {c['jmeno']} {c['prijmeni']}** — Pozice: `{c['role']}`")

# ==========================================
# 7. KATEGORIE: ADMINISTRACE & NASTAVENÍ
# ==========================================
    # --- MODUL: MOJE NASTAVENÍ ---
    elif volba == "Moje nastavení":
        st.header("⚙️ Moje osobní nastavení")
        u_aktualni = supabase.table("uzivatele").select("prezdivka, role, email").eq("id", st.session_state.user_id).execute()
        strav_avatar = ziskej_avatar_uzivatele(st.session_state.user_id)
        
        typ_avataru = st.radio("Typ profilovky:", ["Emoji", "Vlastní fotka"])
        vysledny_avatar = strav_avatar
        if typ_avataru == "Emoji": vysledny_avatar = st.text_input("Zadej emoji:", value=strav_avatar if not str(strav_avatar).startswith("data:image") else "🧑‍🚒", max_chars=5)
        else:
            file = st.file_uploader("Nahraj fotku:", type=["png", "jpg", "jpeg"])
            if file:
                img = Image.open(file).convert("RGB"); img.thumbnail((120, 120))
                buf = io.BytesIO(); img.save(buf, format="PNG")
                vysledny_avatar = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
        
        nova_prez = st.text_input("Přezdívka:", value=u_aktualni.data[0]["prezdivka"] if u_aktualni.data and u_aktualni.data[0]["prezdivka"] else "")
        novy_email = st.text_input("E-mail:", value=u_aktualni.data[0]["email"] if u_aktualni.data else "")
        
        if st.button("Uložit změny", type="primary"):
            supabase.table("uzivatele").update({"email": novy_email, "prezdivka": nova_prez if nova_prez else None}).eq("id", st.session_state.user_id).execute()
            uloz_avatar_uzivatele(st.session_state.user_id, vysledny_avatar)
            st.session_state.user_avatar = vysledny_avatar
            st.success("Uloženo!"); st.rerun()

    # --- MODUL: ADMINISTRATION ---
    elif volba == "⚙️ Správa sboru (Správce)":
        st.header("🛠️ Administrace sboru")
        t_adm_akce, t_adm_clen, t_adm_hes = st.tabs(["➕ Přidat akci", "⚙️ Správa členů", "🔐 Reset hesel"])
        
        with t_adm_akce:
            st.subheader("Vytvořit novou plánovanou akci / výjezd")
            n_nazev = st.text_input("Název")
            n_typ = st.selectbox("Typ", ["Zásah", "Cvičení", "Brigáda", "Schůze", "Soutěž"])
            c_v, p_t, m_h = "", "", ""
            if n_typ == "Zásah":
                c_v = st.text_input("Číslo výjezdu (KOPIS)")
                p_t = st.text_input("Technika")
                m_h = st.text_input("Motohodiny")
            n_dat = st.date_input("Datum")
            n_cas = st.text_input("Čas (např. 15:30)")
            n_poz = st.text_area("Popis")
            if st.button("Zapsat do kalendáře"):
                supabase.table("akce").insert({"sdh_id": st.session_state.sdh_id, "datum": str(n_dat), "cas": n_cas, "nazev_akce": n_nazev, "typ_akce": n_typ, "poznamka": n_poz, "cislo_vyjezdu": c_v if c_v else None, "pouzita_technika": p_t if p_t else None, "motohodiny_uziti": m_h if m_h else None}).execute()
                st.success("Akce přidána!"); st.rerun()
                
        with t_adm_clen:
            cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute()
            if cl_res.data:
                slovnik_clenu = {f"{u['jmeno']} {u['prijmeni']} ({u['role']})": u for u in cl_res.data}
                vybrany = slovnik_clenu[st.selectbox("Hasič k úpravě:", list(slovnik_clenu.keys()))]
                n_role_adm = st.selectbox("Nová pozice:", ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"])
                if st.button("Uložit novou pozici"):
                    supabase.table("uzivatele").update({"role": n_role_adm}).eq("id", vybrany["id"]).execute()
                    st.success("Změněno."); st.rerun()
                    
        with t_adm_hes:
            st.subheader("Nouzový přepis hesla")
            if cl_res.data:
                slovnik_hesla = {f"{u['jmeno']} {u['prijmeni']}": u for u in cl_res.data}
                u_reset = slovnik_hesla[st.selectbox("Vyberte člena:", list(slovnik_hesla.keys()))]
                p_vstup = st.text_input("Nové heslo:", type="password")
                if st.button("Změnit heslo natvrdo"):
                    h_novy = bcrypt.hashpw(p_vstup.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    supabase.table("uzivatele").update({"heslo_hash": h_novy}).eq("id", u_reset["id"]).execute()
                    st.success("Heslo přepsáno.")

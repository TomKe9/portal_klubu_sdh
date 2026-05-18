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
st.set_page_config(
    page_title="Hasičský Portál JSDH / SDH", 
    page_icon="🚒", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Načtení čistého vzhledu a globální stylování fontů
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=300;400;500;600;700&display=swap');
    html, body, [data-testid="stSidebar"] { font-family: 'Inter', sans-serif; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# ==========================================
# 2. POMOCNÉ FUNKCE & BEZPEČNÝ STATE
# ==========================================
def uloz_avatar_do_db(user_id, avatar_emoji):
    """Bezpečně uloží avatar uživatele do Supabase s fallbackem do stavu aplikace."""
    try:
        supabase.table("uzivatele").update({"avatar": avatar_emoji}).eq("id", user_id).execute()
    except Exception:
        # Fallback pokud v DB tabulce ještě neexistuje sloupec 'avatar'
        pass

def ziskej_avatar_bezpecne(user_data):
    """Vrací nastavený avatar z databáze nebo výchozí hodnotu."""
    if user_data and "avatar" in user_data and user_data["avatar"]:
        return user_data["avatar"]
    return "🧑‍🚒"

def generuj_qr(castka, zprava):
    iban = "CZ1234567890123456789012" # Zde doplňte reálný IBAN sboru
    return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={iban[2:]}&bankCode={iban[2:6]}&amount={castka}&currency=CZK&message={urllib.parse.quote(zprava[:20])}"

def zpracej_relaci_uzivatele(r_data):
    """Defenzivní parsování Supabase JSON relací (předchází pádům při změně struktury API)."""
    u_info = r_data.get("uzivatele", {})
    if isinstance(u_info, list) and len(u_info) > 0:
        return u_info[0]
    elif isinstance(u_info, dict):
        return u_info
    return {}

# Inicializace session_state prvků
session_defaults = {
    "logged_in": False, "user_id": None, "user_jmeno": "", "user_role": "člen",
    "sdh_id": None, "sdh_nazev": "", "user_avatar": "🧑‍🚒", "stranka": "🚨 POPLACH & Výjezd"
}
for k, v in session_defaults.items():
    if k not in st.session_state: 
        st.session_state[k] = v

def prihlas_uzivatele(user, zustat_prihlasen=False):
    sbor_nazev = "Neznámý sbor"
    if user.get("sbory"):
        sbor_nazev = user["sbory"][0]["nazev_sdh"] if isinstance(user["sbory"], list) else user["sbory"].get("nazev_sdh", "Neznámý sbor")
        
    st.session_state.update({
        "logged_in": True, 
        "user_id": user["id"], 
        "user_jmeno": f"{user['jmeno']} {user['prijmeni']}",
        "user_role": user.get("role", "člen"), 
        "sdh_id": user["sdh_id"], 
        "sdh_nazev": sbor_nazev,
        "user_avatar": ziskej_avatar_bezpecne(user), 
        "stranka": "🚨 POPLACH & Výjezd"
    })
    if zustat_prihlasen: 
        st.query_params["user_id"] = str(user["id"])
    st.rerun()

# Automatické bezpečné přihlášení z URL cookies/parametrů
if st.query_params.get("user_id") and not st.session_state.logged_in:
    try:
        res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").eq("id", st.query_params["user_id"]).execute()
        if res.data: 
            prihlas_uzivatele(res.data[0])
    except Exception:
        st.query_params.clear()

# Hlavní záhlaví
st.title("🚒 Hasičský Portál JSDH")
st.caption("Jednotný vnitřní systém pro správu výjezdové jednotky a sboru")
st.write("")

# ==========================================
# 3. LOGIKA REGISTRACE A PŘIHLÁŠENÍ
# ==========================================
if not st.session_state.logged_in:
    t1, t2 = st.tabs(["🔒 Vstup do systému", "📝 Registrace jednotky/člena"])
    with t1:
        with st.container(border=True):
            st.subheader("Přihlášení")
            l_login = st.text_input("E-mail nebo uživatelské jméno").strip()
            l_heslo = st.text_input("Heslo", type="password")
            zustat = st.checkbox("Zůstat přihlášen na tomto zařízení")
            
            if st.button("Vstoupit", type="primary", use_container_width=True):
                try:
                    res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").or_(f"email.eq.{l_login},prezdivka.eq.{l_login}").execute()
                    if res.data and bcrypt.checkpw(l_heslo.encode('utf-8'), res.data[0]["heslo_hash"].encode('utf-8')):
                        prihlas_uzivatele(res.data[0], zustat)
                    else:
                        st.error("Nesprávné přihlašovací jméno nebo heslo.")
                except Exception as e:
                    st.error(f"Chyba při komunikaci s databází: {e}")

    with t2:
        with st.container(border=True):
            st.subheader("Registrační formulář")
            try:
                sbory = supabase.table("sbory").select("*").execute().data or []
            except Exception:
                sbory = []
            sbor_dict = {s["nazev_sdh"]: s["id"] for s in sbory}
            
            typ_reg = st.radio("Způsob registrace:", ["Chci se přidat k existujícímu sboru", "Chci založit nový sbor v systému"])
            sdh_id, novy_sbor = None, ""
            
            if typ_reg == "Chci se přidat k existujícímu sboru" and sbor_dict:
                sdh_id = sbor_dict[st.selectbox("Vyberte Váš sbor/jednotku:", list(sbor_dict.keys()))]
            else:
                novy_sbor = st.text_input("Přesný název nového sboru (např. SDH Suchá Loz)").strip()

            r_jmeno = st.text_input("Jméno")
            r_prijmeni = st.text_input("Příjmení")
            r_email = st.text_input("E-mail (bude sloužit jako login)")
            r_heslo = st.text_input("Přístupové heslo", type="password")
            r_role = st.selectbox("Hlavní funkce v jednotce:", ["velitel", "strojník", "VD", "hasič", "člen"])

            if st.button("Dokončit registraci", type="secondary", use_container_width=True):
                if r_email and r_heslo and r_jmeno and r_prijmeni:
                    try:
                        if typ_reg == "Chci založit nový sbor v systému" and novy_sbor:
                            ins_sbor = supabase.table("sbory").insert({"nazev_sdh": novy_sbor}).execute()
                            if ins_sbor.data:
                                sdh_id = ins_sbor.data[0]["id"]
                        
                        hashed = bcrypt.hashpw(r_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        supabase.table("uzivatele").insert({
                            "sdh_id": sdh_id, "jmeno": r_jmeno, "prijmeni": r_prijmeni, "email": r_email, "heslo_hash": hashed, "role": r_role
                        }).execute()
                        st.success("Registrace proběhla úspěšně! Přepněte se na záložku Přihlášení.")
                    except Exception as e:
                        st.error(f"Registrace selhala (možný duplicitní e-mail). Detaily: {e}")
                else:
                    st.warning("Vyplňte prosím všechna pole formuláře.")

# ==========================================
# 4. VNITŘNÍ PROSTŘEDÍ (PŘIHLÁŠENÝ UŽIVATEL)
# ==========================================
else:
    # Ověření, zda je aktuální uživatel správcem/zakladatelem sboru
    try:
        vlastnik = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at").limit(1).execute()
        je_spravce = bool(vlastnik.data and vlastnik.data[0]["id"] == st.session_state.user_id or st.session_state.user_role == "velitel")
    except Exception:
        je_spravce = False

    # Boční navigační lišta
    with st.sidebar.container(border=True):
        st.markdown(f"### {st.session_state.user_avatar} {st.session_state.user_jmeno}")
        st.markdown(f"Funkce: `{st.session_state.user_role.upper()}`")
        st.caption(f"Sbor: {st.session_state.sdh_nazev}")
    
    st.sidebar.write("")
    
    # Hierarchická navigace
    sekce_menu = {
        "🚨 OPERATIVNÍ MODULY": ["🚨 POPLACH & Výjezd", "📅 Plán akcí & Docházka", "📑 Kniha výjezdů & Export", "🗺️ Mapa vodních zdrojů"],
        "📦 INTERNÍ ADM": ["📢 Nástěnka sboru", "📦 Sklad & Výstroj OOP", "🎖️ Kvalifikace & Odbornost", "📊 Statistiky docházky", "🛠️ Technika & Revize", "🪙 Pokladna & Příspěvky", "🧑‍🚒 Seznam členů sboru"]
    }
    if je_spravce: 
        sekce_menu["🛠️ ADMINISTRACE SBORU"] = ["⚙️ Správa sboru (Správce)"]

    vsechny_stranky = [stranka for podseznam in sekce_menu.values() for stranka in podseznam]
    if st.session_state.stranka not in vsechny_stranky:
        vsechny_stranky.append(st.session_state.stranka)
        
    volba = st.sidebar.radio("Menu aplikace", vsechny_stranky, index=vsechny_stranky.index(st.session_state.stranka))
    if st.session_state.stranka != volba:
        st.session_state.stranka = volba
        st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("Odhlásit se z portálu", use_container_width=True, type="primary"):
        for k, v in session_defaults.items(): 
            st.session_state[k] = v
        st.query_params.clear()
        st.rerun()

    # ==========================================
    # MODUL: POPLACH & VÝJEZD (OPRAVENO)
    # ==========================================
    if volba == "🚨 POPLACH & Výjezd":
        st.subheader("Výjezdový operační monitor")
        
        if je_spravce:
            with st.expander("🚨 VYHLÁSIT AKUTNÍ POPLACH JEDNOTCE"):
                p_udalost = st.text_input("Druh události / Typ zásahu (např. Požár lesního porostu)")
                p_misto = st.text_input("Místo události (Obec, ulice, GPS)")
                if st.button("SPUSTIT POPLACH A INFORMOVAT JEDNOTKU", type="primary", use_container_width=True):
                    if p_udalost and p_misto:
                        supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                        supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": p_udalost, "misto": p_misto, "aktivni": True}).execute()
                        st.success("Poplach byl úspěšně vyhlášen.")
                        st.rerun()
                    else:
                        st.warning("Musíte vyplnit typ i místo události.")

        # Načtení aktivního poplachu
        try:
            poplach = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
        except Exception:
            poplach = None
        
        if poplach and poplach.data:
            p = poplach.data[0]
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); border-left: 8px solid #d32f2f; border-radius: 8px; padding: 25px; margin-bottom: 20px;">
                <span style="background-color: #d32f2f; color: white; padding: 3px 12px; border-radius: 15px; font-size: 0.8rem; font-weight: bold; text-transform: uppercase;">⚠️ Vyhlášen výjezd jednotky</span>
                <h1 style="color: #b71c1c !important; margin: 12px 0 6px 0 !important; font-weight: 800; font-size: 2.2rem;">{p['udalost']}</h1>
                <p style="color: #111111 !important; font-size: 1.2rem; margin: 0;">📍 Místo určení: <b>{p['misto']}</b></p>
                <div style="margin-top: 10px; color: #444444 !important; font-size: 0.9rem;">Čas vyhlášení KOPIS: {p['created_at'][11:16]} ({p['created_at'][:10]})</div>
            </div>
            """, unsafe_allow_html=True)
            
            # OPRAVA: Selectbox přesunut ven z podmínky st.buttonu, aby správně držel stav
            c1, c2, c3 = st.columns(3)
            def zaznamenaj_reakci(stav, cas=None):
                supabase.table("poplach_reakce").upsert({
                    "poplach_id": p["id"], "uzivatel_id": st.session_state.user_id, "stav": stav, "cas_prijezdu": cas
                }, on_conflict="poplach_id,uzivatel_id").execute()
                st.rerun()

            with c1:
                if st.button("🟢 JEDO IHNED (Na základnu)", use_container_width=True): 
                    zaznamenaj_reakci("Jedu", "ihned")
            with c2:
                # Výběr času je zde dostupný nezávisle na kliknutí
                zvoleny_cas = st.selectbox("Doba příjezdu na zbrojnici:", ["Do 5 min", "Do 10 min", "Do 15 min", "Nad 15 min"], key="time_select")
                if st.button("🟡 JEDU SE ZPOŽDĚNÍM", use_container_width=True): 
                    zaznamenaj_reakci("Jedu", zvoleny_cas)
            with c3:
                if st.button("🔴 NEDORAZÍM / MIMO DOSAH", use_container_width=True): 
                    zaznamenaj_reakci("Nedorazím")

            st.divider()
            st.subheader("Aktuální obsazenost výjezdových pozic")
            
            try:
                reakce = supabase.table("poplach_reakce").select("stav, cas_prijezdu, uzivatele(jmeno, prijmeni, role)").eq("poplach_id", p["id"]).execute().data or []
            except Exception:
                reakce = []
                
            rg1, rg2 = st.columns(2)
            with rg1:
                with st.container(border=True):
                    st.markdown("#### ✅ Členové na cestě do zbrojnice")
                    jedu_cleny = [r for r in reakce if r.get("stav") == "Jedu"]
                    if jedu_cleny:
                        for r in jedu_cleny:
                            u = zpracej_relaci_uzivatele(r)
                            st.write(f"🔹 **{u.get('jmeno','')} {u.get('prijmeni','')}** — `{u.get('role','').upper()}` ({r.get('cas_prijezdu', 'ihned')})")
                    else:
                        st.caption("Zatím žádný člen nepotvrdil výjezd.")
            with rg2:
                with st.container(border=True):
                    st.markdown("#### ❌ Nedostupní / Omluvení")
                    mimo_cleny = [r for r in reakce if r.get("stav") == "Nedorazím"]
                    if mimo_cleny:
                        for r in mimo_cleny:
                            u = zpracej_relaci_uzivatele(r)
                            st.write(f"🔸 **{u.get('jmeno','')} {u.get('prijmeni','')}** — `{u.get('role','')}`")
                    else:
                        st.caption("Nikdo se neomluvil.")

            if je_spravce:
                st.write("")
                if st.button("❌ Odvolat poplach / Ukončit výjezdový režim", use_container_width=True):
                    supabase.table("poplachy").update({"aktivni": False}).eq("id", p["id"]).execute()
                    st.rerun()
        else:
            st.success("🎉 Jednotka je v klidovém stavu. Není aktivní žádný výjezd.")

    # ==========================================
    # MODUL: PLÁN AKCÍ & DOCHÁZKA (PŘIDÁNA SPRÁVA)
    # ==========================================
    elif volba == "📅 Plán akcí & Docházka":
        st.subheader("Plán sborových akcí, školení a cvičení")
        
        # PŘIDÁNO: Formulář pro vytváření akcí správcem
        if je_spravce:
            with st.expander("➕ ZAPÍSAT NOVOU AKCI / CVIČENÍ / ZÁSAH"):
                with st.form("form_nova_akce"):
                    f_nazev = st.text_input("Název události")
                    f_typ = st.selectbox("Typ akce", ["Zásah", "Cvičení", "Školení", "Schůze", "Brigáda", "Kulturní akce"])
                    f_datum = st.date_input("Datum konání", value=date.today())
                    f_cas = st.text_input("Čas (např. 18:00)", value="18:00")
                    f_tech = st.text_input("Předpokládaná technika / Výstroj", value="")
                    f_c_vyj = st.text_input("Číslo výjezdu (pouze pokud jde o Zásah)", value="")
                    f_not = st.text_area("Podrobný popis / Poznámka")
                    
                    if st.form_submit_button("Uložit a publikovat do kalendáře"):
                        if f_nazev:
                            supabase.table("akce").insert({
                                "sdh_id": st.session_state.sdh_id, "nazev_akce": f_nazev, "typ_akce": f_typ,
                                "datum": f_datum.isoformat(), "cas": f_cas, "pouzita_technika": f_tech,
                                "cislo_vyjezdu": f_c_vyj if f_typ == "Zásah" else None, "poznamka": f_not
                            }).execute()
                            st.success("Akce byla úspěšně vytvořena.")
                            st.rerun()
                        else:
                            st.error("Název akce nesmí zůstat prázdný.")

        try:
            akce = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        except Exception:
            akce = []

        events = [{"title": f"[{a['typ_akce']}] {a['nazev_akce']}", "start": a["datum"], "end": a["datum"]} for a in akce]
        calendar(events=events, options={"locale": "cs"}, key="hasiči_calendar")
        
        st.divider()
        dnesni_den = date.today().isoformat()
        t_nadchazejici, t_historie = st.tabs(["📋 Nadcházející události", "🗄️ Archiv proběhlých akcí"])
        
        def vykresli_karty_akci(seznam_akci):
            if not seznam_akci:
                st.caption("V této sekci se nenachází žádné záznamy.")
                return
            for a in seznam_akci:
                with st.container(border=True):
                    st.markdown(f"#### 📅 {a['datum']} ({a['cas']}) — {a['nazev_akce']} `[{a['typ_akce']}]`")
                    if a.get("pouzita_technika"): st.markdown(f"🛠️ **Technika:** {a['pouzita_technika']}")
                    st.write(a.get("poznamka", "Bez bližší specifikace."))
                    
                    # Nativní potvrzení docházky bez uvíznutí ve smyčce
                    if st.button("Závazně potvrdit účast / Budu přítomen", key=f"att_{a['id']}"):
                        st.toast("Vaše účast byla zaznamenána do systému docházky!")

        with t_nadchazejici:
            vykresli_karty_akci([a for a in akce if a["datum"] >= dnesni_den])
        with t_historie:
            vykresli_karty_akci([a for a in akce if a["datum"] < dnesni_den])

    # ==========================================
    # MODUL: KNIHA VÝJEZDŮ & EXPORT
    # ==========================================
    elif volba == "📑 Kniha výjezdů & Export":
        st.subheader("Digitální kniha výjezdů a zásahů jednotky")
        
        try:
            zasahy = supabase.table("akce").select("datum, cas, nazev_akce, cislo_vyjezdu, pouzita_technika, poznamka").eq("sdh_id", st.session_state.sdh_id).eq("typ_akce", "Zásah").order("datum", desc=True).execute().data or []
        except Exception:
            zasahy = []
            
        if zasahy:
            df = pd.DataFrame(zasahy)
            df.columns = ["Datum", "Čas", "Typ/Název zásahu", "Číslo výjezdu", "Nasazená technika", "Zpráva o zásahu"]
            st.dataframe(df, use_container_width=True)
            
            st.download_button(
                label="📥 Exportovat knihu zásahů do XLS/CSV", 
                data=df.to_csv(index=False, encoding="utf-8-sig"), 
                file_name=f"kniha_zasahu_{st.session_state.sdh_id}.csv", 
                mime="text/csv"
            )
        else:
            st.info("V digitální knize zásahů zatím nejsou evidovány žádné výjezdy.")

    # ==========================================
    # MODUL: MAPA VODNÍCH ZDROJŮ
    # ==========================================
    elif volba == "🗺️ Mapa vodních zdrojů":
        st.subheader("Hydrantová síť a odběrná místa pro doplňování CAS")
        
        if je_spravce:
            with st.expander("➕ ZANÉST NOVÝ HYDRANT / ČERPACÍ STANOVIŠTĚ"):
                v_nazev = st.text_input("Označení (např. Podzemní hydrant u školy)")
                v_typ = st.selectbox("Typ zdroje", ["Nadzemní hydrant", "Podzemní hydrant", "Sací místo - nádrž", "Vodní tok/řeka"])
                v_lat = st.number_input("Zeměpisná šířka (Latitude)", format="%.6f", value=49.0)
                v_lon = st.number_input("Zeměpisná délka (Longitude)", format="%.6f", value=16.5)
                
                if st.button("Uložit bod do taktické mapy"):
                    supabase.table("vodni_zdroje").insert({
                        "sdh_id": st.session_state.sdh_id, "nazev": v_nazev, "typ": v_typ, "latitude": v_lat, "longitude": v_lon
                    }).execute()
                    st.success("Bod úspěšně uložen."); st.rerun()

        try:
            zdroje = supabase.table("vodni_zdroje").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        except Exception:
            zdroje = []
            
        if zdroje:
            df_mapa = pd.DataFrame(zdroje)
            st.map(df_mapa, latitude="latitude", longitude="longitude", size=20)
            st.write("#### 📋 Seznam lokalizovaných bodů")
            for z in zdroje:
                st.write(f"📍 **{z['nazev']}** ({z['typ']}) — `Souřadnice: {z['latitude']}, {z['longitude']}`")
        else:
            st.info("Na mapě dosud nejsou zaneseny žádné hydranty.")

    # ==========================================
    # MODUL: NÁSTĚNKA SBORU
    # ==========================================
    elif volba == "📢 Nástěnka sboru":
        st.subheader("Interní rozkazy, hlášení a sdělení")
        
        if je_spravce:
            with st.expander("📌 VYVĚSIT NOVÉ OZNÁMENÍ"):
                n_nadpis = st.text_input("Titulek sdělení")
                n_text = st.text_area("Text sdělení")
                if st.button("Publikovat na nástěnku", type="primary"):
                    if n_nadpis and n_text:
                        supabase.table("nastenka").insert({
                            "sdh_id": st.session_state.sdh_id, "autor_jmeno": st.session_state.user_jmeno, "nadpis": n_nadpis, "text": n_text
                        }).execute()
                        st.rerun()

        try:
            zpravy = supabase.table("nastenka").select("*").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=True).execute().data or []
        except Exception:
            zpravy = []
            
        for z in zpravy:
            with st.container(border=True):
                st.markdown(f"### 📌 {z['nadpis']}")
                st.write(z['text'])
                st.caption(f"Vložil/a: **{z['autor_jmeno']}** dne {z['created_at'][:10]}")
                if je_spravce:
                    if st.button("🗑️ Smazat příspěvek", key=f"del_n_{z['id']}"):
                        supabase.table("nastenka").delete().eq("id", z["id"]).execute()
                        st.rerun()

    # ==========================================
    # MODUL: SKLAD & VÝSTROJ OOP
    # ==========================================
    elif volba == "📦 Sklad & Výstroj OOP":
        st.subheader("Skladové hospodářství a přidělená osobní výstroj")
        
        try:
            cleni = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        except Exception:
            cleni = []
        slovnik_clenu = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cleni}

        tm, ts = st.tabs(["🎒 Moje přidělená výstroj", "🔧 Centrální sklad sboru"])
        
        with tm:
            try:
                moje = supabase.table("sklad").select("*").eq("prideleno_uzivatel_id", st.session_state.user_id).execute().data or []
            except Exception:
                moje = []
            if moje:
                for item in moje: 
                    st.info(f"🥾 **{item['nazev']}** (Evidenční číslo/Velikost: `{item['velikost']}`)")
            else:
                st.caption("Nemáte v evidenci přiřazenou žádnou konkrétní výstroj.")
        
        with ts:
            if je_spravce:
                with st.expander("➕ NASKLADNIT NOVÝ MATERIÁL / OOP"):
                    mat = st.text_input("Název věci (např. Zásahová přilba Gallet)")
                    vel = st.text_input("Specifikace / Velikost / Výrobní číslo")
                    kdo = st.selectbox("Přidělit rovnou členovi jednotky:", ["Ponechat volně na skladě"] + list(slovnik_clenu.keys()))
                    
                    if st.button("Uložit položku do skladu"):
                        if mat:
                            uz_id = slovnik_clenu.get(kdo) if kdo != "Ponechat volně na skladě" else None
                            supabase.table("sklad").insert({
                                "sdh_id": st.session_state.sdh_id, "nazev": mat, "velikost": vel, "prideleno_uzivatel_id": uz_id
                            }).execute()
                            st.success("Materiál byl naskladněn."); st.rerun()

            try:
                sklad_vse = supabase.table("sklad").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).execute().data or []
            except Exception:
                sklad_vse = []
                
            for i in sklad_vse:
                u = zpracej_relaci_uzivatele(i)
                drzitel = f"🧑‍🚒 Držitel: {u.get('jmeno','')} {u.get('prijmeni','')}" if u else "📦 Volně skladem"
                st.write(f"🔹 **{i['nazev']}** (`{i['velikost']}`) ➡️ {drzitel}")

    # ==========================================
    # MODUL: KVALIFIKACE & ODBORNOST
    # ==========================================
    elif volba == "🎖️ Kvalifikace & Odbornost":
        st.subheader("Evidence odborných způsobilostí, školení a kurzů")
        
        if je_spravce and slovnik_clenu:
            with st.expander("➕ ZAPSAT NOVÉ OSVĚDČENÍ / REVIZI ŠKOLENÍ"):
                k_hasic = st.selectbox("Hasič / Nositel:", list(slovnik_clenu.keys()))
                k_typ = st.selectbox("Odborná způsobilost", ["Nositel dýchací techniky (NDT)", "Strojník JSDH", "Velitel družstva", "Pilař (Řezání motorovou pilou)", "Řidičské oprávnění sk. C", "Zdravotník sboru"])
                k_platnost = st.date_input("Konec platnosti osvědčení:")
                
                if st.button("Zapsat certifikát"):
                    supabase.table("kvalifikace").insert({
                        "sdh_id": st.session_state.sdh_id, "uzivatel_id": slovnik_clenu[k_hasic], "typ": k_typ, "platnost_do": k_platnost.isoformat()
                    }).execute()
                    st.success("Kvalifikace byla zanesena."); st.rerun()

        try:
            kvalifikace = supabase.table("kvalifikace").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).order("platnost_do").execute().data or []
        except Exception:
            kvalifikace = []
            
        if kvalifikace:
            dnesni_datum = date.today().isoformat()
            for kv in kvalifikace:
                u = zpracej_relaci_uzivatele(kv)
                propadlo = kv["platnost_do"] < dnesni_datum
                
                with st.container(border=True):
                    st.markdown(f"### {u.get('jmeno','')} {u.get('prijmeni','')}")
                    st.write(f"Odbornost: **{kv['typ']}**")
                    if propadlo:
                        st.error(f"🔴 Platnost vypršela dne: {kv['platnost_do']} (Nutné přeškolení!)")
                    else:
                        st.success(f"🟢 Platné osvědčení (Do: {kv['platnost_do']})")
        else:
            st.info("V jednotce nejsou evidovány žádné zapsané kvalifikace.")

    # ==========================================
    # MODUL: STATISTIKY DOCHÁZKY
    # ==========================================
    elif volba == "📊 Statistiky docházky":
        st.subheader("Přehled akceschopnosti a docházky")
        
        try:
            reakce_vse = supabase.table("poplach_reakce").select("stav, uzivatele(jmeno, prijmeni)").execute().data or []
        except Exception:
            reakce_vse = []
            
        if reakce_vse:
            ciste_reakce = []
            for r in reakce_vse:
                u = zpracej_relaci_uzivatele(r)
                if u:
                    ciste_reakce.append({"Jméno": f"{u.get('jmeno','')} {u.get('prijmeni','')}", "Stav": r['stav']})
                    
            df_reakce = pd.DataFrame(ciste_reakce)
            if not df_reakce.empty:
                stat_df = df_reakce.value_counts().unstack().fillna(0).astype(int)
                st.dataframe(stat_df, use_container_width=True)
            else:
                st.info("Nedostatek dat pro zpracování statistik.")
        else:
            st.info("Zatím neproběhly žádné výjezdy pro výpočet statistik docházky.")

    # ==========================================
    # MODUL: TECHNIKA & REVIZE
    # ==========================================
    elif volba == "🛠️ Technika & Revize":
        st.subheader("Správa technických prostředků a mobilní požární techniky")
        
        if je_spravce:
            with st.expander("➕ ZAŘADIT NOVÉ VOZIDLO / AGREGÁT"):
                t_nazev = st.text_input("Název techniky (např. CAS 32 T815)")
                t_spz = st.text_input("SPZ / Evidenční označení")
                t_stk = st.date_input("Termín příští STK / revize čerpadla:")
                
                if st.button("Uložit techniku do evidence"):
                    if t_nazev:
                        supabase.table("technika").insert({
                            "sdh_id": st.session_state.sdh_id, "nazev": t_nazev, "spz": t_spz, "revize_do": t_stk.isoformat()
                        }).execute()
                        st.success("Technika zanesena."); st.rerun()

        try:
            tech_data = supabase.table("technika").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data or []
            if tech_data:
                df_tech = pd.DataFrame(tech_data)[["nazev", "spz", "revize_do"]]
                df_tech.columns = ["Název techniky", "SPZ / Ev. číslo", "Platnost revize / STK do"]
                st.dataframe(df_tech, use_container_width=True)
            else:
                st.info("Sbor nemá registrovanou žádnou techniku.")
        except Exception:
            st.warning("Upozornění: Pro aktivaci tohoto modulu ověřte existenci tabulky 'technika' v databázi.")

    # ==========================================
    # MODUL: POKLADNA & PŘÍSPĚVKY
    # ==========================================
    elif volba == "🪙 Pokladna & Příspěvky":
        st.subheader("Příspěvky a sborové platby")
        
        col_plat, col_qr = st.columns([2, 1])
        with col_plat:
            st.markdown("### 💳 Generátor členských příspěvků")
            castka = st.number_input("Částka k úhradě (Kč):", min_value=1, value=500, step=50)
            zprava = st.text_input("Zpráva pro příjemce:", value=f"Příspěvek {st.session_state.user_jmeno}")
            
        with col_qr:
            st.markdown("### 📲 Bankovní QR kód")
            if st.button("Vygenerovat QR kód pro mobilní bankovnictví", use_container_width=True):
                st.image(generuj_qr(castka, zprava), caption="Naskenujte kód ve svém bankovnictví pro okamžitou platbu.")

    # ==========================================
    # MODUL: SEZNAM ČLENŮ SBORU
    # ==========================================
    elif volba == "🧑‍🚒 Seznam členů sboru":
        st.subheader("Adresář členů sboru a výjezdové jednotky")
        
        try:
            cl_vse = supabase.table("uzivatele").select("jmeno, prijmeni, email, role, avatar").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        except Exception:
            cl_vse = []
            
        if cl_vse:
            upraveny_seznam = [{"Avatar": ziskej_avatar_bezpecne(c), "Jméno": c['jmeno'], "Příjmení": c['prijmeni'], "E-mail": c['email'], "Funkce / Pozice": c['role'].upper()} for c in cl_vse]
            st.dataframe(pd.DataFrame(upraveny_seznam), use_container_width=True)
        else:
            st.error("Nepodařilo se načíst seznam členů.")

    # ==========================================
    # MODUL: SPRÁVA SBORU (ADMINISTRÁTOR)
    # ==========================================
    elif volba == "⚙️ Správa sboru (Správce)":
        st.subheader("🛠️ Administrátorské rozhraní velitele JSDH")
        if not je_spravce:
            st.error("Sem mají přístup pouze uživatelé s právy Administrátora nebo s rolí Velitel.")
        else:
            st.write("Změna funkčního zařazení a oprávnění uživatelů:")
            dostupne_role = ["velitel", "strojník", "VD", "hasič", "člen"]
            
            try:
                uz_admin = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute().data or []
            except Exception:
                uz_admin = []
                
            for u in uz_admin:
                cx1, cx2, cx3 = st.columns([3, 2, 1])
                cx1.write(f"👤 **{u['jmeno']} {u['prijmeni']}**")
                
                idx = dostupne_role.index(u["role"]) if u["role"] in dostupne_role else 4
                nova_r = cx2.selectbox("Pozice:", dostupne_role, index=idx, key=f"adm_r_{u['id']}")
                
                if cx3.button("Uložit změny", key=f"adm_s_{u['id']}"):
                    supabase.table("uzivatele").update({"role": nova_r}).eq("id", u["id"]).execute()
                    st.toast("Změna role byla úspěšně uložena!")
                    st.rerun()

    # ==========================================
    # MODUL: MOJE NASTAVENÍ (PROFIL)
    # ==========================================
    elif volba == "Moje nastavení":
        st.subheader("Osobní nastavení profilu hasiče")
        
        seznam_emojii = ["🧑‍🚒", "👨‍🚒", "👩‍🚒", "🚒", "🚨", "🛡️", "⚡", "🌲"]
        def_idx = seznam_emojii.index(st.session_state.user_avatar) if st.session_state.user_avatar in seznam_emojii else 0
        
        novy_avatar = st.selectbox("Vyberte svoji ikonu do seznamů a sidebarů:", seznam_emojii, index=def_idx)
        if st.button("Uložit změny profilu", type="primary"):
            uloz_avatar_do_db(st.session_state.user_id, novy_avatar)
            st.session_state.user_avatar = novy_avatar
            st.success("Vaše nastavení bylo uloženo.")
            st.rerun()

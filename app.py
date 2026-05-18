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

# Opravené CSS styly s fixní barvou textu pro zamezení chyb v Dark Mode
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=300;400;500;600;700&display=swap');
    html, body, [data-testid="stSidebar"] { font-family: 'Inter', sans-serif; }
    
    /* Vynucení tmavého textu pro bílé karty */
    .card { background: #ffffff !important; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e0e0e0; margin-bottom: 20px; }
    .card h1, .card h2, .card h3, .card h4, .card p, .card span, .card small, .card b { color: #222222 !important; }
    
    /* Vynucení kontrastního textu pro poplachovou kartu */
    .poplach-card { background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%) !important; border-left: 6px solid #e53935 !important; border-radius: 12px; padding: 24px; margin-bottom: 25px; }
    .poplach-card h2 { color: #c62828 !important; margin: 10px 0 !important; font-weight: 700 !important; }
    .poplach-card p, .poplach-card b { color: #333333 !important; }
    .poplach-card small { color: #555555 !important; }
    
    .badge { padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: #ffffff !important; }
    .bg-danger { background-color: #e53935 !important; }
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

# Nastavení výchozích hodnot stavu aplikace
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

# Automatické přihlášení
if "user_id" in st.query_params and not st.session_state.logged_in:
    res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").eq("id", st.query_params["user_id"]).execute()
    if res.data: prihlas_uzivatele(res.data[0])

# Nativní nadpisy bez HTML - přizpůsobí se světlému i tmavému režimu automaticky
st.title("🚒 Hasičský Portál")
st.caption("Chytré řízení sboru a výjezdové jednotky")
st.write("")

# ==========================================
# 3. LOGIKA APLIKACE (ROZCESTNÍK)
# ==========================================

# --- VARIANTA A: UŽIVATEL NENÍ PŘIHLÁŠEN ---
if not st.session_state.logged_in:
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
            st.subheader("Registrace nového uživatele / sboru")
            sbory = supabase.table("sbory").select("*").execute().data or []
            sbor_dict = {s["nazev_sdh"]: s["id"] for s in sbory}
            
            typ_reg = st.radio("Zvolte typ registrace:", ["Existující sbor", "Nový sbor"])
            sdh_id, novy_sbor = None, ""
            
            if typ_reg == "Existující sbor" and sbor_dict:
                sdh_id = sbor_dict[st.selectbox("Vyberte sbor:", list(sbor_dict.keys()))]
            else:
                novy_sbor = st.text_input("Název nového sboru").strip()

            r_jmeno = st.text_input("Jméno")
            r_prijmeni = st.text_input("Příjmení")
            r_email = st.text_input("E-mail")
            r_heslo = st.text_input("Heslo", type="password")
            r_role = st.selectbox("Výchozí pozice v jednotce:", ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"])

            if st.button("Zaregistrovat", type="secondary") and r_email and r_heslo:
                if typ_reg == "Nový sbor" and novy_sbor:
                    sdh_id = supabase.table("sbory").insert({"nazev_sdh": novy_sbor}).execute().data[0]["id"]
                
                hashed = bcrypt.hashpw(r_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                supabase.table("uzivatele").insert({
                    "sdh_id": sdh_id, "jmeno": r_jmeno, "prijmeni": r_prijmeni, "email": r_email, "heslo_hash": hashed, "role": r_role
                }).execute()
                st.success("Úspěšně registrováno! Nyní se můžete přihlásit v první záložce.")

# --- VARIANTA B: UŽIVATEL JE PŘIHLÁŠEN ---
else:
    vlastnik = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at").limit(1).execute()
    je_spravce = bool(vlastnik.data and vlastnik.data[0]["id"] == st.session_state.user_id)

    # Profil v sidebaru s fixním tmavým písmem (#31333F) a světlým boxem, čitelný vždy
    st.sidebar.markdown(f"""
    <div style="display:flex; align-items:center; background:#f0f2f6; padding:12px; border-radius:10px; margin-bottom:15px; border:1px solid #dddddd;">
        <span style="font-size:32px; margin-right:12px;">{st.session_state.user_avatar}</span>
        <div><b style="color:#31333f;">{st.session_state.user_jmeno}</b><br><span style="font-size:0.8rem; color:#e53935; font-weight:600;">{st.session_state.user_role.upper()}</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.sidebar.button(f"🏢 {st.session_state.sdh_nazev}", use_container_width=True):
        st.session_state.stranka = "🧑‍🚒 Seznam členů sboru"
        st.rerun()
    if st.sidebar.button("⚙️ Moje nastavení", use_container_width=True):
        st.session_state.stranka = "Moje nastavení"
        st.rerun()
        
    st.sidebar.divider()
    
    menu = {
        "🚨 AKTIVNÍ SLUŽBA & VÝJEZDY": ["🚨 POPLACH & Výjezd", "📅 Plán akcí & Docházka", "📑 Kniha výjezdů & Export", "🗺️ Mapa vodních zdrojů"],
        "📦 VNITŘNÍ CHOD & MAJETEK": ["📢 Nástěnka sboru", "📦 Sklad & Výstroj OOP", "🎖️ Kvalifikace & Odbornost", "📊 Statistiky docházky", "🛠️ Technika & Revize", "🪙 Pokladna & Příspěvky", "🧑‍🚒 Seznam členů sboru"]
    }
    if je_spravce: 
        menu["🛠️ ADMINISTRACE SBORU"] = ["⚙️ Správa sboru (Správce)"]

    flat_menu = [item for sublist in menu.values() for item in sublist]
    if st.session_state.stranka not in flat_menu: 
        flat_menu.append(st.session_state.stranka)

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
    # 4. ZOBRAZENÍ JEDNOTLIVÝCH MODULŮ (OBSAH)
    # ==========================================

    # --- 1. POPLACH & VÝJEZD ---
    if volba == "🚨 POPLACH & Výjezd":
        st.subheader("Výjezdový monitor")
        if je_spravce:
            with st.expander("🚨 VYHLÁŠENÍ NOVÉHO POPLACHU JEDNOTCE"):
                p_udalost = st.text_input("Druh události (např. Požár nízké budovy)")
                p_misto = st.text_input("Místo události / Adresa")
                if st.button("ODSOUHLASIT A VYHLÁSIT", type="primary"):
                    supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                    supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": p_udalost, "misto": p_misto}).execute()
                    st.rerun()

        poplach = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
        
        if poplach.data:
            p = poplach.data[0]
            st.markdown(f"""
            <div class="poplach-card">
                <span class="badge bg-danger">⚠️ AKUTNÍ VÝJEZD JEDNOTKY</span>
                <h2>{p['udalost']}</h2>
                <p>📍 Místo: <b>{p['misto']}</b></p>
                <small>Čas vyhlášení: {p['created_at'][11:16]} ({p['created_at'][:10]})</small>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            def reaguj(stav, cas=None):
                supabase.table("poplach_reakce").upsert({"poplach_id": p["id"], "uzivatel_id": st.session_state.user_id, "stav": stav, "cas_prijezdu": cas}, on_conflict="poplach_id,uzivatel_id").execute()
                st.rerun()

            if c1.button("🟢 Jedu ihned (na zbrojnici)", use_container_width=True): reaguj("Jedu", "ihned")
            with c2:
                if st.button("🟡 Jedu se zpožděním", use_container_width=True): 
                    reaguj("Jedu", st.selectbox("Čas příjezdu:", ["5 min", "10 min", "15 min"]))
            if c3.button("🔴 Nedorazím / Mimo", use_container_width=True): reaguj("Nedorazím")

            st.divider()
            st.subheader("Aktuální stav připravenosti družstva")
            reakce = supabase.table("poplach_reakce").select("stav, cas_prijezdu, uzivatele(jmeno, prijmeni, role)").eq("poplach_id", p["id"]).execute().data or []
            
            rg1, rg2 = st.columns(2)
            with rg1:
                st.markdown("<div class='card'><h4>✅ Na cestě do zbrojnice</h4>", unsafe_allow_html=True)
                for r in [x for x in reakce if x["stav"] == "Jedu"]: 
                    st.write(f"🟢 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}** — {r['uzivatele']['role']} ({r['cas_prijezdu']})")
                st.markdown("</div>", unsafe_allow_html=True)
            with rg2:
                st.markdown("<div class='card'><h4>❌ Nedostupní členové</h4>", unsafe_allow_html=True)
                for r in [x for x in reakce if x["stav"] == "Nedorazím"]: 
                    st.write(f"🔴 **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}** — {r['uzivatele']['role']}")
                st.markdown("</div>", unsafe_allow_html=True)

            if je_spravce and st.button("❌ Odvolat / Ukončit aktivní poplach", use_container_width=True):
                supabase.table("poplachy").update({"aktivni": False}).eq("id", p["id"]).execute()
                st.rerun()
        else:
            st.success("🎉 Vše v pořádku. Jednotka nemá hlášený žádný aktivní poplach.")

    # --- 2. PLÁN AKCÍ & DOCHÁZKA ---
    elif volba == "📅 Plán akcí & Docházka":
        st.subheader("Plán sborových akcí a cvičení")
        akce = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        events = [{"title": a["nazev_akce"], "start": a["datum"], "end": a["datum"]} for a in akce]
        calendar(events=events, options={"locale": "cs"})
        
        st.divider()
        dnes = date.today().isoformat()
        t_budouci, t_minule = st.tabs(["📋 Nadcházející akce", "🗄️ Historie a archiv"])
        
        def vykresli_akce(seznam):
            for a in seznam:
                with st.expander(f"📅 {a['datum']} - {a['nazev_akce']} [{a['typ_akce']}]"):
                    st.write(f"ℹ️ {a.get('poznamka', 'Bez bližšího popisu.')}")
                    if st.button("Potvrdit účast", key=f"btn_{a['id']}"): 
                        st.toast("Účast na akci byla uložena!")
        
        with t_budouci: vykresli_akce([a for a in akce if a["datum"] >= dnes])
        with t_minule: vykresli_akce([a for a in akce if a["datum"] < dnes])

    # --- 3. KNIHA VÝJEZDŮ & EXPORT ---
    elif volba == "📑 Kniha výjezdů & Export":
        st.subheader("Oficiální kniha zásahů a výjezdů")
        zasahy = supabase.table("akce").select("datum, cas, nazev_akce, cislo_vyjezdu, pouzita_technika").eq("sdh_id", st.session_state.sdh_id).eq("typ_akce", "Zásah").execute().data
        if zasahy:
            df = pd.DataFrame(zasahy)
            st.dataframe(df, use_container_width=True)
            st.download_button("📥 Stáhnout data výjezdů (CSV)", df.to_csv(index=False), "kniha_zasahu.csv", "text/csv")
        else:
            st.info("Sbor prozatím nemá v digitální knize evidované žádné výjezdy k zásahům.")

    # --- 4. MAPA VODNÍCH ZDROJŮ ---
    elif volba == "🗺️ Mapa vodních zdrojů":
        st.subheader("Mapa hydrantů, čerpacích stanovišť a vodních zdrojů")
        if je_spravce:
            with st.expander("➕ Přidat nový lokalizovaný vodní zdroj"):
                v_nazev, v_typ = st.text_input("Název / Označení"), st.selectbox("Typ zdroje", ["Nadzemní hydrant", "Podzemní hydrant", "Požární nádrž", "Řeka/Potok"])
                v_lat, v_lon = st.number_input("Zeměpisná šířka (Lat)", format="%.5f"), st.number_input("Zeměpisná délka (Lon)", format="%.5f")
                if st.button("Uložit do mapy"):
                    supabase.table("vodni_zdroje").insert({"sdh_id": st.session_state.sdh_id, "nazev": v_nazev, "typ": v_typ, "latitude": v_lat, "longitude": v_lon}).execute()
                    st.rerun()

        zdroje = supabase.table("vodni_zdroje").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
        if zdroje:
            df_mapa = pd.DataFrame(zdroje)
            st.map(df_mapa)
            for z in zdroje: 
                st.write(f"📍 **{z['nazev']}** — *{z['typ']}* (Souřadnice: {z['latitude']}, {z['longitude']})")
        else:
            st.info("Zatím nebyly zaneseny žádné vodní zdroje.")

    # --- 5. NÁSTĚNKA SBORU ---
    elif volba == "📢 Nástěnka sboru":
        st.subheader("Interní sdělení a hlášení sboru")
        if je_spravce:
            with st.expander("📌 Publikovat zprávu na nástěnku"):
                n_nadpis, n_text = st.text_input("Nadpis zprávy"), st.text_area("Obsah sdělení")
                if st.button("Vyvěsit zprávu") and n_nadpis:
                    supabase.table("nastenka").insert({"sdh_id": st.session_state.sdh_id, "autor_jmeno": st.session_state.user_jmeno, "nadpis": n_nadpis, "text": n_text, "dulezite": False}).execute()
                    st.rerun()

        zpravy = supabase.table("nastenka").select("*").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=True).execute().data or []
        for z in zpravy:
            st.markdown(f"""
            <div class='card'>
                <h3 style='margin-top:0;'>{z['nadpis']}</h3>
                <p>{z['text']}</p>
                <small>Zveřejnil: <b>{z['autor_jmeno']}</b> ({z['created_at'][:10]})</small>
            </div>
            """, unsafe_allow_html=True)

    # --- 6. SKLAD & VÝSTROJ OOP ---
    elif volba == "📦 Sklad & Výstroj OOP":
        st.subheader("Evidence osobních ochranných prostředků a výstroje")
        cleni = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        slovnik_clenu = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cleni}

        tm, ts = st.tabs(["🎒 Moje přidělená výstroj", "🔧 Centrální sklad sboru"])
        with tm:
            moje = supabase.table("sklad").select("*").eq("prideleno_uzivatel_id", st.session_state.user_id).execute().data or []
            if moje:
                for item in moje: st.info(f"🧥 **{item['nazev']}** (Specifikace/Velikost: {item['velikost']})")
            else:
                st.write("Nemáte aktuálně elektronicky přiřazenou žádnou konkrétní výstroj.")
        
        with ts:
            if je_spravce:
                with st.expander("➕ Naskladnit novou položku majetku"):
                    mat, vel = st.text_input("Název věci (např. Zásahový kabát Fire3)"), st.text_input("Velikost / ID")
                    kdo = st.selectbox("Přiřadit rovnou členovi:", ["Ponechat na skladě"] + list(slovnik_clenu.keys()))
                    if st.button("Potvrdit uložení"):
                        uz_id = slovnik_clenu.get(kdo) if kdo != "Ponechat na skladě" else None
                        supabase.table("sklad").insert({"sdh_id": st.session_state.sdh_id, "nazev": mat, "velikost": vel, "prideleno_uzivatel_id": uz_id}).execute()
                        st.rerun()

            sklad_vse = supabase.table("sklad").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).execute().data or []
            for i in sklad_vse:
                vlastnik = f"🧑‍🚒 Držitel: {i['uzivatele']['jmeno']} {i['uzivatele']['prijmeni']}" if i.get("uzivatele") else "📦 Volně skladem"
                st.write(f"🔹 **{i['nazev']}** ({i['velikost']}) ➡️ {vlastnik}")

    # --- 7. KVALIFIKACE & ODBORNOST ---
    elif volba == "🎖️ Kvalifikace & Odbornost":
        st.subheader("Platnost licencí, kurzů a odborností")
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute()
        slovnik_hasicu = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cl_res.data} if cl_res.data else {}
        
        if je_spravce:
            with st.expander("➕ Zapsat nově získané osvědčení / školení"):
                k_hasic = st.selectbox("Hasič:", list(slovnik_hasicu.keys()))
                k_typ = st.text_input("Odbornost (např. NDT dýchací technika, VMP, Pilař, Zdravotník)")
                k_platnost = st.date_input("Konec platnosti (recertifikace):")
                
                if st.button("Uložit osvědčení", type="primary"):
                    supabase.table("kvalifikace").insert({
                        "sdh_id": st.session_state.sdh_id, "uzivatel_id": slovnik_hasicu[k_hasic], "typ": k_typ, "platnost_do": k_platnost.isoformat()
                    }).execute()
                    st.success("Zapsáno."); st.rerun()

        st.markdown("<br><h4>📋 Přehled odborností v jednotce</h4>", unsafe_allow_html=True)
        kvalifikace_res = supabase.table("kvalifikace").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).order("platnost_do").execute()
        
        if kvalifikace_res.data:
            dnes = date.today().isoformat()
            for kv in kvalifikace_res.data:
                je_propadla = kv["platnost_do"] < dnes
                barva = "#d32f2f" if je_propadla else "#2e7d32"
                status = "🔴 Vypršela platnost" if je_propadla else "🟢 Platné osvědčení"
                st.markdown(f"""
                <div class='card' style='border-left: 5px solid {barva} !important;'>
                    <h3>{kv['uzivatele']['jmeno']} {kv['uzivatele']['prijmeni']}</h3>
                    <p>Odbornost: <b>{kv['typ']}</b></p>
                    <small style='color:{barva} !important; font-weight:600;'>{status} (do: {kv['platnost_do']})</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Dosud nebyly zadány žádné kvalifikace.")

    # --- 8. STATISTIKY DOCHÁZKY ---
    elif volba == "📊 Statistiky docházky":
        st.subheader("Statistiky a analýza aktivity")
        st.info("Zde se zobrazuje celkové vytížení sboru a procentuální účast členů na zásazích.")
        reakce_vse = supabase.table("poplach_reakce").select("stav, uzivatele(jmeno, prijmeni)").execute().data or []
        if reakce_vse:
            df_reakce = pd.DataFrame([{"Jméno": f"{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}", "Stav": r['stav']} for r in reakce_vse])
            st.dataframe(df_reakce.value_counts().unstack().fillna(0), use_container_width=True)
        else:
            st.write("Žrádná data pro generování grafů a statistik docházky nejsou k dispozici.")

    # --- 9. TECHNIKA & REVIZE ---
    elif volba == "🛠️ Technika & Revize":
        st.subheader("Správa techniky, vozového parku a revizí strojů")
        if je_spravce:
            with st.expander("➕ Přidat nové vozidlo / agregát"):
                t_nazev = st.text_input("Název techniky (např. CAS 20 Scania)")
                t_spz = st.text_input("Státní poznávací značka / Evidenční číslo")
                t_stk = st.date_input("Platnost STK / Revize čerpadla do:")
                if st.button("Zavést techniku do systému"):
                    supabase.table("technika").insert({"sdh_id": st.session_state.sdh_id, "nazev": t_nazev, "spz": t_spz, "revize_do": t_stk.isoformat()}).execute()
                    st.rerun()

        try:
            tech_data = supabase.table("technika").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
            if tech_data:
                st.dataframe(pd.DataFrame(tech_data), use_container_width=True)
            else:
                st.info("V databázi sboru zatím není evidována žádná zásahová technika.")
        except Exception:
            st.warning("Upozornění: Pro plnou funkčnost tohoto modulu vytvořte v Supabase tabulku 'technika'.")

    # --- 10. POKLADNA & PŘÍSPĚVKY ---
    elif volba == "🪙 Pokladna & Příspěvky":
        st.subheader("Sborová pokladna a výběr členských příspěvků")
        
        c_platby, c_qr = st.columns([2, 1])
        with c_platby:
            st.markdown("### 💳 Informace pro platbu příspěvku")
            castka = st.number_input("Částka k úhradě (Kč)", min_value=1, value=500, step=50)
            zprava = st.text_input("Účel platby / Poznámka", value=f"Prispevek {st.session_state.user_jmeno}")
            
        with c_qr:
            st.markdown("### 📲 QR Platba")
            if st.button("Vygenerovat platební QR kód", use_container_width=True):
                url_qr = generuj_qr(castka, zprava)
                st.image(url_qr, caption="Naskenujte kód mobilním bankovnictvím")

    # --- 11. SEZNAM ČLENŮ SBORU ---
    elif volba == "🧑‍🚒 Seznam členů sboru":
        st.subheader("Adresář a přehled členů sboru")
        cl_vse = supabase.table("uzivatele").select("jmeno, prijmeni, email, role, created_at").eq("sdh_id", st.session_state.sdh_id).execute().data
        if cl_vse:
            df_cleni = pd.DataFrame(cl_vse)
            df_cleni.columns = ["Jméno", "Příjmení", "E-mail", "Funkce/Role", "Datum registrace"]
            st.dataframe(df_cleni, use_container_width=True)
        else:
            st.error("Chyba při načítání uživatelských dat.")

    # --- 12. SPRÁVA SBORU (ADMIN) ---
    elif volba == "⚙️ Správa sboru (Správce)":
        st.subheader("🛠️ Administrátorská konzole sboru")
        if not je_spravce:
            st.error("Do této sekce mají přístup výhradně oprávnění správci sboru.")
        else:
            st.write("Zde můžete spravovat uživatelské účty a přidělovat funkce členům jednotky.")
            vsechny_role = ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen", "velitel"]
            
            uz_admin = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute().data or []
            for u in uz_admin:
                col_jmeno, col_role, col_akce = st.columns([3, 2, 1])
                col_jmeno.write(f"👤 **{u['jmeno']} {u['prijmeni']}**")
                
                index_role = vsechny_role.index(u["role"]) if u["role"] in vsechny_role else 5
                nova_role = col_role.selectbox("Změna role:", vsechny_role, index=index_role, key=f"sel_{u['id']}")
                
                if col_akce.button("Uložit", key=f"save_{u['id']}"):
                    supabase.table("uzivatele").update({"role": nova_role}).eq("id", u["id"]).execute()
                    st.toast("Funkce úspěšně aktualizována!")
                    st.rerun()

    # --- 13. MOJE NASTAVENÍ (PROFIL) ---
    elif volba == "Moje nastavení":
        st.subheader("Uživatelské nastavení profilu")
        st.write("Zde si můžete upravit svůj osobní profil v aplikaci.")
        
        avatary_list = ["🧑‍🚒", "👨‍🚒", "👩‍🚒", "🚒", "🚨", "🛡️", "🦊", "🐻"]
        idx_av = avatary_list.index(st.session_state.user_avatar) if st.session_state.user_avatar in avatary_list else 0
        
        vybrany_avatar = st.selectbox("Zvolte svoji ikonku (Avatar):", avatary_list, index=idx_av)
        if st.button("Uložit nastavení profilu", type="primary"):
            uloz_avatar(st.session_state.user_id, vybrany_avatar)
            st.session_state.user_avatar = vybrany_avatar
            st.success("Profilová ikona byla úspěšně změněna!")
            st.rerun()

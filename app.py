import streamlit as st
import pandas as pd
import bcrypt
from datetime import date
from supabase import create_client, Client
from streamlit_calendar import calendar

# ==========================================
# 1. KONFIGURACE & INICIALIZACE SYSTÉMU
# ==========================================
st.set_page_config(
    page_title="Výjezdový portál JSDH", 
    page_icon="🚒", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Čistý profesionální vzhled bez zbytečností
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&display=swap');
    html, body, [data-testid="stSidebar"] { font-family: 'Inter', sans-serif; }
    .stButton>button { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Chyba připojení k Supabase: {e}")
    st.stop()

# ==========================================
# 2. SESTAVENÍ RELACE (SESSION STATE)
# ==========================================
session_defaults = {
    "logged_in": False, "user_id": None, "user_jmeno": "", "user_role": "člen",
    "sdh_id": None, "sdh_nazev": "", "stranka": "🚨 POPLACH & Výjezd"
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
        "stranka": "🚨 POPLACH & Výjezd"
    })
    if zustat_prihlasen: 
        st.query_params["user_id"] = str(user["id"])
    st.rerun()

if st.query_params.get("user_id") and not st.session_state.logged_in:
    try:
        res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").eq("id", st.query_params["user_id"]).execute()
        if res.data: 
            prihlas_uzivatele(res.data[0])
    except Exception:
        st.query_params.clear()

st.title("🚒 Výjezdový portál JSDH")
st.write("")

# ==========================================
# 3. PŘIHLÁŠENÍ A REGISTRACE
# ==========================================
if not st.session_state.logged_in:
    t1, t2 = st.tabs(["🔒 Vstup do systému", "📝 Registrace člena / sboru"])
    with t1:
        with st.container(border=True):
            l_login = st.text_input("E-mail nebo uživatelské jméno").strip()
            l_heslo = st.text_input("Heslo", type="password")
            zustat = st.checkbox("Zůstat přihlášen")
            
            if st.button("Vstoupit", type="primary", use_container_width=True):
                try:
                    res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").or_(f"email.eq.{l_login},prezdivka.eq.{l_login}").execute()
                    if res.data and bcrypt.checkpw(l_heslo.encode('utf-8'), res.data[0]["heslo_hash"].encode('utf-8')):
                        prihlas_uzivatele(res.data[0], zustat)
                    else:
                        st.error("Nesprávné přihlašovací údaje.")
                except Exception as e:
                    st.error(f"Chyba databáze: {e}")

    with t2:
        with st.container(border=True):
            try:
                sbory = supabase.table("sbory").select("*").execute().data or []
            except Exception:
                sbory = []
            sbor_dict = {s["nazev_sdh"]: s["id"] for s in sbory}
            
            typ_reg = st.radio("Způsob registrace:", ["Chci se přidat k existujícímu sboru", "Založit nový sbor"])
            sdh_id, novy_sbor = None, ""
            
            if typ_reg == "Chci se přidat k existujícímu sboru" and sbor_dict:
                sdh_id = sbor_dict[st.selectbox("Vyberte sbor:", list(sbor_dict.keys()))]
            else:
                novy_sbor = st.text_input("Přesný název nového sboru (např. JSDH Suchá Loz)").strip()

            r_jmeno = st.text_input("Jméno")
            r_prijmeni = st.text_input("Příjmení")
            r_email = st.text_input("E-mail (bude sloužit jako login)")
            r_heslo = st.text_input("Heslo", type="password")
            r_role = st.selectbox("Hlavní výjezdová funkce:", ["velitel", "strojník", "VD", "hasič", "člen"])

            if st.button("Dokončit registraci", use_container_width=True):
                if r_email and r_heslo and r_jmeno and r_prijmeni:
                    try:
                        if typ_reg == "Založit nový sbor" and novy_sbor:
                            ins_sbor = supabase.table("sbory").insert({"nazev_sdh": novy_sbor}).execute()
                            if ins_sbor.data: sdh_id = ins_sbor.data[0]["id"]
                        
                        hashed = bcrypt.hashpw(r_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        supabase.table("uzivatele").insert({
                            "sdh_id": sdh_id, "jmeno": r_jmeno, "prijmeni": r_prijmeni, "email": r_email, "heslo_hash": hashed, "role": r_role
                        }).execute()
                        st.success("Registrace hotova! Přepněte se na přihlášení.")
                    except Exception as e:
                        st.error(f"Registrace selhala: {e}")

# ==========================================
# 4. VNITŘNÍ PROSTŘEDÍ (PŘIHLÁŠEN)
# ==========================================
else:
    je_velitel = (st.session_state.user_role == "velitel")

    with st.sidebar.container(border=True):
        st.markdown(f"### 🧑‍🚒 {st.session_state.user_jmeno}")
        st.markdown(f"Funkce: `{st.session_state.user_role.upper()}`")
        st.caption(f"Jednotka: {st.session_state.sdh_nazev}")
    
    # Redukované menu - pouze 4 položky včetně administrace
    menu = ["🚨 POPLACH & Výjezd", "📅 Plán akcí & Docházka", "🎖️ Kvalifikace & Odbornost"]
    if je_velitel:
        menu.append("⚙️ Správa jednotky (Velitel)")
        
    volba = st.sidebar.radio("Navigace", menu, key="stranka")

    st.sidebar.divider()
    if st.sidebar.button("Odhlásit se", use_container_width=True, type="primary"):
        for k, v in session_defaults.items(): st.session_state[k] = v
        st.query_params.clear()
        st.rerun()

    # ==========================================
    # MODUL: POPLACH & VÝJEZD (MONITOR)
    # ==========================================
    if volba == "🚨 POPLACH & Výjezd":
        st.subheader("Výjezdový operační monitor")
        
        if je_velitel:
            with st.expander("🚨 VYHLÁSIT RUČNÍ POPLACH JEDNOTCE"):
                p_udalost = st.text_input("Typ zásahu (např. Požár - Nízké budovy)")
                p_misto = st.text_input("Místo události / GPS")
                if st.button("SPUSTIT POPLACH", type="primary", use_container_width=True):
                    if p_udalost and p_misto:
                        try:
                            supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                            supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": p_udalost, "misto": p_misto, "aktivni": True}).execute()
                            st.rerun()
                        except Exception as e: st.error(f"Chyba: {e}")

        try:
            poplach = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
        except Exception: poplach = None
        
        if poplach and poplach.data:
            p = poplach.data[0]
            st.markdown(f"""
            <div style="background-color: #b71c1c; color: white; border-radius: 8px; padding: 25px; margin-bottom: 20px;">
                <span style="background-color: white; color: #b71c1c; padding: 2px 10px; border-radius: 10px; font-size: 0.8rem; font-weight: bold; text-transform: uppercase;">⚠️ AKUTNÍ POPLACH</span>
                <h1 style="color: white !important; margin: 10px 0 5px 0 !important; font-weight: 800;">{p['udalost']}</h1>
                <p style="color: white !important; font-size: 1.2rem; margin: 0;">📍 Místo: <b>{p['misto']}</b></p>
                <div style="margin-top: 10px; opacity: 0.8; font-size: 0.85rem;">Čas vyhlášení: {p['created_at'][11:16]}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Tlačítka rychlé odezvy
            c1, c2, c3 = st.columns(3)
            def reaguj(stav, cas):
                try:
                    supabase.table("poplach_reakce").upsert({
                        "poplach_id": p["id"], "uzivatel_id": st.session_state.user_id, "stav": stav, "cas_prijezdu": cas
                    }, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
                except Exception as e: st.error(f"Chyba: {e}")

            with c1:
                if st.button("🟢 JEDU (Do 5 minut)", use_container_width=True): reaguj("Jedu", "Do 5 min")
            with c2:
                if st.button("🟡 JEDU (Do 10 minut)", use_container_width=True): reaguj("Jedu", "Do 10 min")
            with c3:
                if st.button("🔴 NEDORAZÍM", use_container_width=True): reaguj("Nedorazím", None)

            st.divider()
            
            # Načtení reakcí pro sčítání sil
            try:
                reakce = supabase.table("poplach_reakce").select("stav, cas_prijezdu, uzivatele(jmeno, prijmeni, role)").eq("poplach_id", p["id"]).execute().data or []
            except Exception: reakce = []

            # Taktické sčítání sil na cestě (Klíčové pro velitele)
            jedu_seznam = [r for r in reakce if r.get("stav") == "Jedu"]
            
            st.subheader("📊 Přehled sil a prostředků na cestě")
            if jedu_seznam:
                v_pocet = sum(1 for r in jedu_seznam if r["uzivatele"].get("role") == "velitel")
                s_pocet = sum(1 for r in jedu_seznam if r["uzivatele"].get("role") == "strojník")
                vd_pocet = sum(1 for r in jedu_seznam if r["uzivatele"].get("role") == "VD")
                h_pocet = sum(1 for r in jedu_seznam if r["uzivatele"].get("role") in ["hasič", "člen"])
                
                # Rychlé indikátory akceschopnosti vozidla
                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.metric("Velitelé", f"{v_pocet} / 1")
                sc2.metric("Strojníci", f"{s_pocet} / 1")
                sc3.metric("Velitelé družstva (VD)", vd_pocet)
                sc4.metric("Hasiči", h_pocet)
            
            # Jmenné seznamy
            rg1, rg2 = st.columns(2)
            with rg1:
                with st.container(border=True):
                    st.markdown("#### ✅ Členové na cestě do zbrojnice")
                    if jedu_seznam:
                        for r in jedu_seznam:
                            u = r["uzivatele"][0] if isinstance(r["uzivatele"], list) else r["uzivatele"]
                            st.write(f"🔹 **{u.get('jmeno')} {u.get('prijmeni')}** — `{u.get('role').upper()}` ({r.get('cas_prijezdu')})")
                    else: st.caption("Zatím nikdo nepotvrdil výjezd.")
            with rg2:
                with st.container(border=True):
                    st.markdown("#### ❌ Omluvení / Nedostupní")
                    mimo_cleny = [r for r in reakce if r.get("stav") == "Nedorazím"]
                    if mimo_cleny:
                        for r in mimo_cleny:
                            u = r["uzivatele"][0] if isinstance(r["uzivatele"], list) else r["uzivatele"]
                            st.write(f"🔸 **{u.get('jmeno')} {u.get('prijmeni')}** — `{u.get('role').upper()}`")
                    else: st.caption("Nikdo se neomluvil.")

            if je_velitel:
                st.write("")
                if st.button("❌ Ukončit výjezdový režim / Odvolat poplach", use_container_width=True):
                    try:
                        supabase.table("poplachy").update({"aktivni": False}).eq("id", p["id"]).execute()
                        st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")
        else:
            st.success("🎉 Jednotka je v klidovém stavu. Není aktivní žádný výjezd.")

    # ==========================================
    # MODUL: PLÁN AKCÍ & DOCHÁZKA
    # ==========================================
    elif volba == "📅 Plán akcí & Docházka":
        st.subheader("Plánování akcí, cvičení a školení")
        
        if je_velitel:
            with st.expander("➕ VYTVOŘIT NOVOU AKCI JEDNOTKY"):
                with st.form("nova_akce"):
                    f_nazev = st.text_input("Název akce / Téma školení")
                    f_typ = st.selectbox("Typ akce", ["Cvičení", "Školení", "Schůze", "Brigáda", "Zásah"])
                    f_datum = st.date_input("Datum", value=date.today())
                    f_cas = st.text_input("Čas", value="18:00")
                    f_not = st.text_area("Poznámka / Výstroj")
                    
                    if st.form_submit_button("Uložit do kalendáře"):
                        if f_nazev:
                            try:
                                supabase.table("akce").insert({
                                    "sdh_id": st.session_state.sdh_id, "nazev_akce": f_nazev, "typ_akce": f_typ,
                                    "datum": f_datum.isoformat(), "cas": f_cas, "poznamka": f_not
                                }).execute()
                                st.rerun()
                            except Exception as e: st.error(f"Chyba: {e}")

        try:
            akce = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        except Exception: akce = []

        # Interaktivní kalendář akcí
        events = [{"title": f"[{a['typ_akce']}] {a['nazev_akce']}", "start": a["datum"]} for a in akce]
        calendar(events=events, options={"locale": "cs"}, key="hasici_calendar")
        
        st.divider()
        st.subheader("Zápis a přehled účasti")
        
        dnes = date.today().isoformat()
        nadchazejici = [a for a in akce if a["datum"] >= dnes]
        
        if nadchazejici:
            for a in nadchazejici:
                with st.container(border=True):
                    st.markdown(f"#### 📅 {a['datum']} v {a['cas']} — **{a['nazev_akce']}** `[{a['typ_akce']}]`")
                    if a.get("poznamka"): st.caption(a["poznamka"])
                    
                    if st.button("Potvrdit moji účast (Budu přítomen)", key=f"att_{a['id']}", type="secondary"):
                        try:
                            supabase.table("dochazka").upsert({
                                "akce_id": a["id"], "uzivatel_id": st.session_state.user_id, "status": "Přítomen"
                            }, on_conflict="akce_id,uzivatel_id").execute()
                            st.toast("Účast byla zapsána.", icon="✅")
                        except Exception as e: st.error(f"Chyba zápisu: {e}")
        else:
            st.caption("Žádné nadcházející akce nejsou naplánovány.")

    # ==========================================
    # MODUL: KVALIFIKACE & ODBORNOST (ZÁSADNÍ)
    # ==========================================
    elif volba == "🎖️ Kvalifikace & Odbornost":
        st.subheader("Hlídání platnosti odborných způsobilostí hasičů")
        
        try:
            cleni = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute().data or []
            kvalifikace = supabase.table("kvalifikace").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).order("platnost_do").execute().data or []
        except Exception: 
            cleni, kvalifikace = [], []
            
        slovnik_clenu = {f"{u['jmeno']} {u['prijmeni']}": u["id"] for u in cleni}

        if je_velitel and slovnik_clenu:
            with st.expander("➕ ZAPSAT NOVÝ CERTIFIKÁT / ŠKOLENÍ"):
                k_hasic = st.selectbox("Člen jednotky:", list(slovnik_clenu.keys()))
                k_typ = st.selectbox("Odbornost / Kurzy:", ["Nositel dýchací techniky (NDT)", "Strojník JSDH", "Velitel družstva", "Pilař (M motorové pily)", "Řidičák sk. C", "Zdravotník"])
                k_platnost = st.date_input("Platnost osvědčení do:")
                
                if st.button("Uložit do registru"):
                    try:
                        supabase.table("kvalifikace").insert({
                            "sdh_id": st.session_state.sdh_id, "uzivatel_id": slovnik_clenu[k_hasic], "typ": k_typ, "platnost_do": k_platnost.isoformat()
                        }).execute()
                        st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")

        if kvalifikace:
            dnesni_den = date.today().isoformat()
            
            # Přehledná tabulka pro kontrolu propadajících školení
            data_kv = []
            for kv in kvalifikace:
                u = kv["uzivatele"][0] if isinstance(kv["uzivatele"], list) else kv["uzivatele"]
                stav = "🔴 PROPADLÉ" if kv["platnost_do"] < dnesni_den else "🟢 PLATNÉ"
                data_kv.append({
                    "Hasič": f"{u.get('jmeno')} {u.get('prijmeni')}",
                    "Odbornost": kv["typ"],
                    "Konec platnosti": kv["platnost_do"],
                    "Stav": stav
                })
            
            df_kv = pd.DataFrame(data_kv)
            st.dataframe(df_kv, use_container_width=True, hide_index=True)
        else:
            st.info("V jednotce zatím nejsou zapsány žádné kvalifikace.")

    # ==========================================
    # MODUL: SPRÁVA JEDNOTKY (POUZE VELITEL)
    # ==========================================
    elif volba == "⚙️ Správa jednotky (Velitel)" and je_velitel:
        st.subheader("🛠️ Administrace oprávnění a organizačních rolí")
        
        try:
            uz_admin = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        except Exception: uz_admin = []
            
        st.write("Změna funkčního zařazení hasičů ve výjezdovém portálu:")
        dostupne_role = ["velitel", "strojník", "VD", "hasič", "člen"]
        
        for u in uz_admin:
            cx1, cx2, cx3 = st.columns([3, 2, 1])
            cx1.write(f"👤 **{u['jmeno']} {u['prijmeni']}**")
            
            idx = dostupne_role.index(u["role"]) if u["role"] in dostupne_role else 4
            nova_r = cx2.selectbox("Výjezdová pozice:", dostupne_role, index=idx, key=f"adm_r_{u['id']}")
            
            if cx3.button("Uložit", key=f"adm_s_{u['id']}", use_container_width=True):
                try:
                    supabase.table("uzivatele").update({"role": nova_r}).eq("id", u["id"]).execute()
                    st.toast("Role změněna.", icon="💾")
                except Exception as e: st.error(f"Chyba: {e}")

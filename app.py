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
    page_title="Manažer Požárního Sportu", 
    page_icon="🏃‍♂️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700;800&display=swap');
    html, body, [data-testid="stSidebar"] { font-family: 'Inter', sans-serif; }
    .stButton>button { font-weight: 700; border-radius: 6px; }
    h1, h2, h3 { font-weight: 800 !important; }
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
# 2. SESSION STATE & AUTENTIZACE
# ==========================================
session_defaults = {
    "logged_in": False, "user_id": None, "user_jmeno": "",
    "sdh_id": None, "sdh_nazev": "", "stranka": "🏆 Výsledky & Tréninky"
}
for k, v in session_defaults.items():
    if k not in st.session_state: 
        st.session_state[k] = v

def prihlas_uzivatele(user, zustat_prihlasen=False):
    sbor_nazev = "Neznámý klub/sbor"
    if user.get("sbory"):
        sbor_nazev = user["sbory"][0]["nazev_sdh"] if isinstance(user["sbory"], list) else user["sbory"].get("nazev_sdh", "Neznámý sbor")
        
    st.session_state.update({
        "logged_in": True, 
        "user_id": user["id"], 
        "user_jmeno": f"{user['jmeno']} {user['prijmeni']}",
        "sdh_id": user["sdh_id"], 
        "sdh_nazev": sbor_nazev,
        "stranka": "🏆 Výsledky & Tréninky"
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

st.title("⚡ SportManažer SDH")
st.caption("Otevřený systém pro analýzu časů, správu nářadí a soupisky týmu")
st.write("")

# ==========================================
# 3. PŘIHLÁŠENÍ A REGISTRACE TÝMU
# ==========================================
if not st.session_state.logged_in:
    t1, t2 = st.tabs(["🔒 Vstup pro sportovce", "📝 Registrace závodníka / týmu"])
    with t1:
        with st.container(border=True):
            l_login = st.text_input("E-mail nebo uživatelské jméno").strip()
            l_heslo = st.text_input("Heslo", type="password")
            zustat = st.checkbox("Zůstat přihlášen na tomto zařízení")
            
            if st.button("Vstoupit do šatny", type="primary", use_container_width=True):
                try:
                    res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").or_(f"email.eq.{l_login},prezdivka.eq.{l_login}").execute()
                    if res.data and bcrypt.checkpw(l_heslo.encode('utf-8'), res.data[0]["heslo_hash"].encode('utf-8')):
                        prihlas_uzivatele(res.data[0], zustat)
                    else:
                        st.error("Nesprávné přihlašovací údaje.")
                except Exception as e:
                    st.error(f"Chyba spojení s databází: {e}")

    with t2:
        with st.container(border=True):
            try:
                sbory = supabase.table("sbory").select("*").execute().data or []
            except Exception:
                sbory = []
            sbor_dict = {s["nazev_sdh"]: s["id"] for s in sbory}
            
            typ_reg = st.radio("Registrace:", ["Chci se přidat k existujícímu soutěžnímu týmu", "Založit nový sportovní tým/sbor"])
            sdh_id, novy_sbor = None, ""
            
            if typ_reg == "Chci se přidat k existujícímu soutěžnímu týmu" and sbor_dict:
                sdh_id = sbor_dict[st.selectbox("Vyberte tým:", list(sbor_dict.keys()))]
            else:
                novy_sbor = st.text_input("Přesný název týmu (např. SDH Metylovice - muži)").strip()

            r_jmeno = st.text_input("Jméno")
            r_prijmeni = st.text_input("Příjmení")
            r_email = st.text_input("E-mail (slouží jako přihlašovací jméno)")
            r_heslo = st.text_input("Heslo", type="password")

            if st.button("Dokončit registraci sportovce", use_container_width=True):
                if r_email and r_heslo and r_jmeno and r_prijmeni:
                    try:
                        if typ_reg == "Založit nový sportovní tým/sbor" and novy_sbor:
                            ins_sbor = supabase.table("sbory").insert({"nazev_sdh": novy_sbor}).execute()
                            if ins_sbor.data: sdh_id = ins_sbor.data[0]["id"]
                        
                        hashed = bcrypt.hashpw(r_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        supabase.table("uzivatele").insert({
                            "sdh_id": sdh_id, "jmeno": r_jmeno, "prijmeni": r_prijmeni, "email": r_email, "heslo_hash": hashed, "role": "správce"
                        }).execute()
                        st.success("Registrace úspěšná! Přepněte se na záložku přihlášení.")
                    except Exception as e:
                        st.error(f"Chyba při registraci: {e}")

# ==========================================
# 4. VNITŘNÍ PROSTŘEDÍ (PŘIHLÁŠENÝ TÝM)
# ==========================================
else:
    with st.sidebar.container(border=True):
        st.markdown(f"### 🏃‍♂️ {st.session_state.user_jmeno}")
        st.caption(f"Klub: {st.session_state.sdh_nazev}")
        st.badge(text="Režim: Správce týmu", color="green")
    
    menu = ["🏆 Výsledky & Tréninky", "🏃 Soupiska & Posty", "⚡ Sportovní nářadí & Mašina"]
    volba = st.sidebar.radio("Sportovní menu", menu, key="stranka")

    st.sidebar.divider()
    if st.sidebar.button("Odhlásit se z kabiny", use_container_width=True, type="primary"):
        for k, v in session_defaults.items(): st.session_state[k] = v
        st.query_params.clear()
        st.rerun()

    # ==========================================
    # MODUL: VÝSLEDKY & TRÉNINKY (Kdokoli může zapisovat)
    # ==========================================
    if volba == "🏆 Výsledky & Tréninky":
        st.subheader("Tréninkový deník a stopky útoků")
        
        with st.expander("⏱️ ZAPSAT NOVÝ POKUS (ZÁVOD / TRÉNINK)", expanded=True):
            with st.form("novy_pokus_form"):
                f_typ = st.selectbox("Typ pokusu", ["Trénink", "Závod - Extraliga", "Závod - Okresní liga", "Pohárová soutěž"])
                f_soutez = st.text_input("Název závodu / lokalita", value="Domácí tréninkové hřiště")
                
                cc1, cc2, cc3 = st.columns(3)
                f_voda = cc1.number_input("Čas vody / koše (s)", min_value=0.0, max_value=60.0, value=9.50, step=0.01, format="%.2f")
                f_levy = cc2.number_input("Levý proud (s)", min_value=0.0, max_value=60.0, value=14.20, step=0.01, format="%.2f")
                f_pravy = cc3.number_input("Pravý proud (s)", min_value=0.0, max_value=60.0, value=14.50, step=0.01, format="%.2f")
                
                f_np = st.checkbox("NP - Neplatný pokus (Diskvalifikace / Nedokončeno)")
                f_not = st.text_input("Poznámka k pokusu (např. prostřik vpravo, pomalá voda)")
                
                if st.form_submit_button("Uložit pokus do statistik"):
                    try:
                        vysledny = max(f_levy, f_pravy) if not f_np else 0.0
                        
                        supabase.table("sportovni_pokusy").insert({
                            "sbor_id": st.session_state.sdh_id, "typ_udalosti": f_typ, "nazev_souteze": f_soutez,
                            "cas_voda": f_voda, "cas_levy_proud": f_levy, "cas_pravy_proud": f_pravy,
                            "vysledny_cas": vysledny, "diskvalifikace": f_np, "poznamka": f_not
                        }).execute()
                        st.success("Pokus úspěšně zapsán do Supabase!")
                        st.rerun()
                    except Exception as e: st.error(f"Chyba zápisu: {e}")

        try:
            pokusy = supabase.table("sportovni_pokusy").select("*").eq("sbor_id", st.session_state.sdh_id).order("created_at", desc=True).execute().data or []
        except Exception: pokusy = []

        if pokusy:
            df = pd.DataFrame(pokusy)
            platne_pokusy = df[df["diskvalifikace"] == False]
            if not platne_pokusy.empty:
                nej_cas = platne_pokusy["vysledny_cas"].min()
                st.metric(label="🏆 Nejlepší čas týmu", value=f"{nej_cas:.2f} s")
            
            st.write("### 📋 Historie odběhaných pokusů")
            zobrazeni_data = []
            for p in pokusy:
                prostrik = abs(p["cas_levy_proud"] - p["cas_pravy_proud"])
                vysledek = "NP (Neplatný)" if p["diskvalifikace"] else f"{p['vysledny_cas']:.2f} s"
                zobrazeni_data.append({
                    "Datum": p["created_at"][:10],
                    "Typ": p["typ_udalosti"],
                    "Místo / Závod": p["nazev_souteze"],
                    "Čas vody": f"{p['cas_voda']:.2f} s",
                    "Levý proud": f"{p['cas_levy_proud']:.2f} s",
                    "Pravý proud": f"{p['cas_pravy_proud']:.2f} s",
                    "Prostřik": f"{prostrik:.2f} s",
                    "VÝSLEDNÝ ČAS": vysledek,
                    "Poznámka": p["poznamka"]
                })
            st.dataframe(pd.DataFrame(zobrazeni_data), use_container_width=True, hide_index=True)
        else:
            st.info("Zatím nebyly zapsány žádné pokusy.")

    # ==========================================
    # MODUL: SOUPISKA & POSTY (Kdokoli může upravovat)
    # ==========================================
    elif volba == "🏃 Soupiska & Posty":
        st.subheader("Rozdělení postů na požární útok")
        
        try:
            zavodnici = supabase.table("uzivatele").select("id, jmeno, prijmeni").eq("sdh_id", st.session_state.sdh_id).execute().data or []
            sestava = supabase.table("sestava_tymu").select("*").execute().data or []
        except Exception: zavodnici, sestava = [], []
        
        slovnik_zavodniku = {f"{z['jmeno']} {z['prijmeni']}": z["id"] for z in zavodnici}
        sestava_dict = {s["uzivatel_id"]: s for s in sestava}

        if slovnik_zavodniku:
            with st.expander("🛠️ PŘIŘADIT NEBO ZMĚNIT POST ZÁVODNÍKA", expanded=True):
                k_atlet = st.selectbox("Vyberte závodníka:", list(slovnik_zavodniku.keys()))
                k_post = st.selectbox("Primární post na útoku:", ["Koš", "Savice", "Stroj", "Béčka", "Rozdělovač", "Proud"])
                k_strana = st.selectbox("Strana (pouze pro proudaře):", ["Levá", "Pravá", "Nerozhoduje"])
                k_zaloha = st.text_input("Záložní post:", value="Savice")
                
                if st.button("Uložit nastavení do soupisky"):
                    try:
                        u_id = slovnik_zavodniku[k_atlet]
                        supabase.table("sestava_tymu").upsert({
                            "uzivatel_id": u_id, "hlavni_post": k_post, "strana": k_strana, "zalozni_post": k_zaloha
                        }, on_conflict="uzivatel_id").execute()
                        st.success("Post uložen!")
                        st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")

        st.write("### 🎽 Aktuální rozřazení týmu do pozic")
        if zavodnici:
            tabulka_sestavy = []
            for z in zavodnici:
                s_info = sestava_dict.get(z["id"], {})
                tabulka_sestavy.append({
                    "Jméno závodníka": f"{z['jmeno']} {z['prijmeni']}",
                    "Hlavní pozice": s_info.get("hlavni_post", "❌ Nepřiřazeno"),
                    "Strana": s_info.get("strana", "—"),
                    "Záložní post": s_info.get("zalozni_post", "—")
                })
            st.dataframe(pd.DataFrame(tabulka_sestavy), use_container_width=True, hide_index=True)

    # ==========================================
    # MODUL: SPORTOVNÍ NÁŘADÍ (Kdokoli může přidávat)
    # ==========================================
    elif volba == "⚡ Sportovní nářadí & Mašina":
        st.subheader("Technický stav sportovního materiálu (Nářadí)")
        
        with st.expander("➕ ZAŘADIT DO EVIDENCE NOVÉ NÁŘADÍ", expanded=True):
            n_nazev = st.text_input("Název materiálu (např. Hadice C52 - Sport Slim)")
            n_typ = st.selectbox("Kategorie", ["Mašina PS 12", "Hadice B", "Hadice C", "Savice", "Proudnice", "Koš", "Rozdělovač"])
            n_stav = st.selectbox("Stav nářadí", ["Nové / Špičkový stav (Závodní)", "Opotřebené (Pouze trénink)", "Poškozené / V opravě"])
            n_param = st.text_input("Specifické parametry")
            
            if st.button("Uložit materiál"):
                if n_nazev:
                    try:
                        supabase.table("sportovni_material").insert({
                            "sdh_id": st.session_state.sdh_id, "nazev": n_nazev, "kategorie": n_typ, "stav": n_stav, "parametry": n_param
                        }).execute()
                        st.success("Nářadí zařazeno!")
                        st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")

        try:
            material = supabase.table("sportovni_material").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data or []
        except Exception: material = []

        if material:
            df_mat = pd.DataFrame(material)[["kategorie", "nazev", "parametry", "stav"]]
            df_mat.columns = ["Kategorie", "Název nářadí", "Parametry / Rozměry", "Technický stav"]
            st.dataframe(df_mat, use_container_width=True, hide_index=True)

import streamlit as st
from supabase import create_client, Client
import bcrypt
import datetime

# 1. Propojení se Supabase pomocí Secrets
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# Inicializace session state (paměti aplikace)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_jmeno = ""
    st.session_state.user_role = "člen"
    st.session_state.sdh_id = None
    st.session_state.sdh_nazev = ""

st.title("🚒 Portál SDH")
st.write("Informační systém pro dobrovolné hasiče")

# --- ODHLÁŠENÍ ---
if st.session_state.logged_in:
    st.sidebar.markdown(f"**Přihlášen:** {st.session_state.user_jmeno}")
    st.sidebar.markdown(f"**Sbor:** {st.session_state.sdh_nazev}")
    st.sidebar.markdown(f"**Role:** {st.session_state.user_role}")
    if st.sidebar.button("Odhlásit se"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.sdh_id = None
        st.rerun()

# --- SEKCE PRO NEPŘIHLÁŠENÉ (PŘIHLÁŠENÍ / REGISTRACE) ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔒 Přihlášení", "📝 Registrace nového člena / sboru"])
    
    with tab1:
        st.subheader("Přihlášení k portálu")
        login_email = st.text_input("E-mail", key="login_email").strip()
        login_heslo = st.text_input("Heslo", type="password", key="login_password")
        
        if st.button("Přihlásit se", type="primary"):
            if login_email and login_heslo:
                # Najít uživatele v DB
                res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").eq("email", login_email).execute()
                if res.data:
                    user = res.data[0]
                    # Ověření hesla
                    if bcrypt.checkpw(login_heslo.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                        st.session_state.logged_in = True
                        st.session_state.user_id = user["id"]
                        st.session_state.user_jmeno = f"{user['jmeno']} {user['prijmeni']}"
                        st.session_state.user_role = user["role"]
                        st.session_state.sdh_id = user["sdh_id"]
                        st.session_state.sdh_nazev = user["sbory"]["nazev_sdh"]
                        st.success("Úspěšně přihlášen!")
                        st.rerun()
                    else:
                        st.error("Nesprávné heslo.")
                else:
                    st.error("Uživatel s tímto e-mailem neexistuje.")
            else:
                st.warning("Vyplňte prosím všechna pole.")

    with tab2:
        st.subheader("Registrace")
        
        # Výběr sboru z DB nebo vytvoření nového
        sbory_res = supabase.table("sbory").select("*").execute()
        seznam_sboru = {s["nazev_sdh"]: s["id"] for s in sbory_res.data} if sbory_res.data else {}
        
        volba_sboru = st.radio("Vyberte možnost:", ["Přidat se k existujícímu sboru", "Zaregistrovat úplně nový sbor"])
        
        vybrany_sdh_id = None
        novy_sbor_nazev = ""
        
        if volba_sboru == "Přidat se k existujícímu sboru":
            if seznam_sboru:
                vybrany_sbor_nazev = st.selectbox("Vyberte váš sbor (SDH):", list(seznam_sboru.keys()))
                vybrany_sdh_id = seznam_sboru[vybrany_sbor_nazev]
            else:
                st.info("Zatím není registrován žádný sbor. Zaregistrujte prosím nový sbor.")
        else:
            novy_sbor_nazev = st.text_input("Název nového sboru (např. SDH Lhota)").strip()
            
        reg_jmeno = st.text_input("Jméno")
        reg_prijmeni = st.text_input("Příjmení")
        reg_email = st.text_input("E-mail (bude sloužit jako přihlašovací jméno)")
        reg_heslo = st.text_input("Heslo pro přihlášení", type="password")
        
        # Pokud zakládá nový sbor, bude automaticky 'velitel' (administrátor), jinak 'člen'
        navrhovana_role = "velitel" if volba_sboru == "Zaregistrovat úplně nový sbor" else "člen"
        
        if st.button("Dokončit registraci"):
            if reg_jmeno and reg_prijmeni and reg_email and reg_heslo and (vybrany_sdh_id or novy_sbor_nazev):
                try:
                    # 1. Pokud zakládá nový sbor, vytvoříme ho v DB
                    if volba_sboru == "Zaregistrovat úplně nový sbor":
                        sbor_ins = supabase.table("sbory").insert({"nazev_sdh": novy_sbor_nazev}).execute()
                        
                        # Pojistka pro správné načtení ID nového sboru
                        if sbor_ins.data:
                            vybrany_sdh_id = sbor_ins.data[0]["id"]
                        else:
                            sbor_find = supabase.table("sbory").select("id").eq("nazev_sdh", novy_sbor_nazev).execute()
                            vybrany_sdh_id = sbor_find.data[0]["id"]
                    
                    # 2. Zašifrování hesla
                    hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    
                    # 3. Vytvoření uživatele
                    uzivatel_data = {
                        "sdh_id": vybrany_sdh_id,
                        "jmeno": reg_jmeno,
                        "prijmeni": reg_prijmeni,
                        "email": reg_email,
                        "heslo_hash": hashed,
                        "role": navrhovana_role
                    }
                    supabase.table("uzivatele").insert(uzivatel_data).execute()
                    st.success("Registrace proběhla úspěšně! Nyní se můžete přihlásit v prvním tabu.")
                except Exception as e:
                    st.error(f"Chyba při registraci (např. e-mail nebo název sboru již existuje). Detaily: {e}")
            else:
                st.warning("Prosím vyplňte všechny údaje.")

# --- SEKCE PRO PŘIHLÁŠENÉ UŽIVATELE ---
else:
    st.info(f"Vítej v portálu pro **{st.session_state.sdh_nazev}**!")
    
    menu = ["Plán akcí & Docházka", "Seznam členů sboru"]
    if st.session_state.user_role == "velitel":
        menu.append("🛠️ Správa sboru (Velitel)")
        
    volba = st.sidebar.selectbox("Kam chceš jít?", menu)
    
    # --- 1. PLÁN AKCÍ & DOCHÁZKA ---
    if volba == "Plán akcí & Docházka":
        st.header("📅 Plán činností a docházka")
        
        # Načtení akcí pro tento sbor
        akce_res = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).order("datum").execute()
        
        if not akce_res.data:
            st.write("Zatím nejsou naplánované žádné akce.")
        else:
            for akce in akce_res.data:
                with st.expander(f"{akce['datum']} - {akce['nazev_akce']} ({akce['typ_akce']})"):
                    # Zjištění aktuální docházky uživatele pro tuto akci
                    doch_res = supabase.table("dochazka").select("status").eq("akce_id", akce["id"]).eq("uzivatel_id", st.session_state.user_id).execute()
                    aktualni_status = doch_res.data[0]["status"] if doch_res.data else "Nezadáno"
                    
                    st.write(f"Moje aktuální účast: **{aktualni_status}**")
                    
                    # Tlačítka pro změnu docházky
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Jdu 👍", key=f"ano_{akce['id']}"):
                            supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Jdu"}, on_conflict="akce_id,uzivatel_id").execute()
                            st.rerun()
                    with col2:
                        if st.button("Nejdu 👎", key=f"ne_{akce['id']}"):
                            supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nejdu"}, on_conflict="akce_id,uzivatel_id").execute()
                            st.rerun()
                    with col3:
                        if st.button("Nevím 🤷", key=f"nevim_{akce['id']}"):
                            supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nevím"}, on_conflict="akce_id,uzivatel_id").execute()
                            st.rerun()
                    
                    # Přehled docházky pro velitele a ostatní
                    st.write("---")
                    st.write("**Přehled ostatních:**")
                    vsechna_dochazka = supabase.table("dochazka").select("status, uzivatele(jmeno, prijmeni)").eq("akce_id", akce["id"]).execute()
                    if vsechna_dochazka.data:
                        for d in vsechna_dochazka.data:
                            st.write(f"- {d['uzivatele']['jmeno']} {d['uzivatele']['prijmeni']}: {d['status']}")
                    else:
                        st.caption("Zatím nikdo nevyplnil docházku.")

    # --- 2. SEZNAM ČLENŮ ---
    elif volba == "Seznam členů sboru":
        st.header("🧑‍🚒 Členové sboru")
        clenove_res = supabase.table("uzivatele").select("jmeno, prijmeni, email, role").eq("sdh_id", st.session_state.sdh_id).execute()
        if clenove_res.data:
            for c in clenove_res.data:
                st.write(f"• **{c['jmeno']} {c['prijmeni']}** - {c['role']} ({c['email']})")

    # --- 3. SPRÁVA SBORU (PRO VELITELE) ---
    elif volba == "🛠️ Správa sboru (Velitel)":
        st.header("🛠️ Administrace sboru (Pouze velitel)")
        
        st.subheader("➕ Přidat novou akci")
        nova_akce_nazev = st.text_input("Název akce (např. Výcvik s dýchací technikou)")
        nova_akce_datum = st.date_input("Datum akce", datetime.date.today())
        nova_akce_typ = st.selectbox("Typ akce", ["Zásah", "Cvičení", "Brigáda", "Schůze", "Soutěž", "Jiné"])
        
        if st.button("Vytvořit akci a zapsat do plánu"):
            if nova_akce_nazev:
                akce_data = {
                    "sdh_id": st.session_state.sdh_id,
                    "datum": str(nova_akce_datum),
                    "nazev_akce": nova_akce_nazev,
                    "typ_akce": nova_akce_typ
                }
                supabase.table("akce").insert(akce_data).execute()
                st.success("Akce byla úspěšně přidána!")
                st.rerun()
            else:
                st.warning("Vyplňte název akce.")

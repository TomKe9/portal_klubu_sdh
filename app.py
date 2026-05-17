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

# Pomocné funkce pro trvalé přihlášení
def nacti_trvale_prihlaseni():
    if "user_id" in st.query_params and not st.session_state.get("logged_in"):
        u_id = st.query_params["user_id"]
        res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").eq("id", u_id).execute()
        if res.data:
            user = res.data[0]
            st.session_state.logged_in = True
            st.session_state.user_id = user["id"]
            st.session_state.user_jmeno = f"{user['jmeno']} {user['prijmeni']}"
            st.session_state.user_role = user["role"]
            st.session_state.sdh_id = user["sdh_id"]
            st.session_state.sdh_nazev = user["sbory"]["nazev_sdh"]

# Inicializace session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_jmeno = ""
    st.session_state.user_role = "člen"
    st.session_state.sdh_id = None
    st.session_state.sdh_nazev = ""

nacti_trvale_prihlaseni()

st.title("🚒 Portál SDH")
st.write("Informační systém pro dobrovolné hasiče")

# --- ODHLÁŠENÍ ---
if st.session_state.logged_in:
    st.sidebar.markdown(f"**Přihlášen:** {st.session_state.user_jmeno}")
    st.sidebar.markdown(f"**Sbor:** {st.session_state.sdh_nazev}")
    st.sidebar.markdown(f"**Pozice/Role:** {st.session_state.user_role}")
    if st.sidebar.button("Odhlásit se"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.sdh_id = None
        if "user_id" in st.query_params:
            del st.query_params["user_id"]
        st.rerun()

# --- SEKCE PRO NEPŘIHLÁŠENÉ (PŘIHLÁŠENÍ / REGISTRACE) ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔒 Přihlášení", "📝 Registrace nového člena / sboru"])
    
    with tab1:
        st.subheader("Přihlášení k portálu")
        login_input = st.text_input("E-mail nebo Přezdívka", key="login_input").strip()
        login_heslo = st.text_input("Heslo", type="password", key="login_password")
        zustat_prihlasen = st.checkbox("Zůstat přihlášen na tomto zařízení")
        
        if st.button("Přihlásit se", type="primary"):
            if login_input and login_heslo:
                # Přihlášení funguje jak přes e-mail, tak přes zadanou přezdívku
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
                        
                        if zustat_prihlasen:
                            st.query_params["user_id"] = str(user["id"])
                            
                        st.success("Úspěšně přihlášen!")
                        st.rerun()
                    else:
                        st.error("Nesprávné heslo.")
                else:
                    st.error("Uživatel s tímto údajem neexistuje.")
            else:
                st.warning("Vyplňte prosím všechna pole.")

    with tab2:
        st.subheader("Registrace")
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
        reg_email = st.text_input("E-mail")
        reg_heslo = st.text_input("Heslo pro přihlášení", type="password")
        
        # Registrace je čistá, přezdívka a pozice se zadávají až uvnitř systému
        if volba_sboru == "Zaregistrovat úplně nový sbor":
            st.info("Jako zakladatel sboru budete automaticky nastaven jako **Správce**.")
            vybrana_role = "Správce"
        else:
            vybrana_role = st.selectbox("Vyberte vaši hlavní pozici ve sboru:", 
                                        ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"])
        
        if st.button("Dokončit registraci"):
            if reg_jmeno and reg_prijmeni and reg_email and reg_heslo and (vybrany_sdh_id or novy_sbor_nazev):
                try:
                    if volba_sboru == "Zaregistrovat úplně nový sbor":
                        sbor_ins = supabase.table("sbory").insert({"nazev_sdh": novy_sbor_nazev}).execute()
                        if sbor_ins.data:
                            vybrany_sdh_id = sbor_ins.data[0]["id"]
                        else:
                            sbor_find = supabase.table("sbory").select("id").eq("nazev_sdh", novy_sbor_nazev).execute()
                            vybrany_sdh_id = sbor_find.data[0]["id"]
                    
                    hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    
                    uzivatel_data = {
                        "sdh_id": vybrany_sdh_id,
                        "jmeno": reg_jmeno,
                        "prijmeni": reg_prijmeni,
                        "email": reg_email,
                        "heslo_hash": hashed,
                        "role": vybrana_role,
                        "prezdivka": None  # Přezdívka je při registraci prázdná
                    }
                    supabase.table("uzivatele").insert(uzivatel_data).execute()
                    st.success("Registrace proběhla úspěšně! Nyní se můžete přihlásit.")
                except Exception as e:
                    st.error(f"Chyba při registraci. Detaily: {e}")
            else:
                st.warning("Prosím vyplňte všechny údaje.")

# --- SEKCE PRO PŘIHLÁŠENÉ UŽIVATELE ---
else:
    st.info(f"Vítej v portálu pro **{st.session_state.sdh_nazev}**!")
    
    menu = ["Plán akcí & Docházka", "Seznam členů sboru"]
    
    # Rozlišení menu pro Správce a řadové členy
    if st.session_state.user_role == "Správce":
        menu.append("🛠️ Správa sboru (Správce)")
    else:
        menu.append("⚙️ Moje nastavení")
        
    volba = st.sidebar.selectbox("Kam chceš jít?", menu)
    
    # --- 1. PLÁN AKCÍ & DOCHÁZKA ---
    if volba == "Plán akcí & Docházka":
        st.header("📅 Plán činností a docházka")
        
        akce_res = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).order("datum").execute()
        
        if not akce_res.data:
            st.write("Zatím nejsou naplánované žádné akce.")
        else:
            for akce in akce_res.data:
                cas_info = f" v {akce['cas']}" if akce.get('cas') else ""
                with st.expander(f"📅 {akce['datum']}{cas_info} - {akce['nazev_akce']} ({akce['typ_akce']})"):
                    
                    if akce.get('poznamka'):
                        st.markdown(f"ℹ️ **Poznámka k akci:**\n> {akce['poznamka']}")
                    
                    doch_res = supabase.table("dochazka").select("status").eq("akce_id", akce["id"]).eq("uzivatel_id", st.session_state.user_id).execute()
                    aktualni_status = doch_res.data[0]["status"] if doch_res.data else "Nezadáno"
                    st.write(f"Moje aktuální účast: **{aktualni_status}**")
                    
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
                    
                    if st.session_state.user_role == "Správce":
                        st.write("---")
                        if st.button("Smazat tuto akci ❌", key=f"del_{akce['id']}", type="secondary"):
                            supabase.table("dochazka").delete().eq("akce_id", akce["id"]).execute()
                            supabase.table("akce").delete().eq("id", akce["id"]).execute()
                            st.success("Akce byla smazána.")
                            st.rerun()
                    
                    st.write("---")
                    st.write("**Přehled ostatních:**")
                    vsechna_dochazka = supabase.table("dochazka").select("status, uzivatele(jmeno, prijmeni, role)").eq("akce_id", akce["id"]).execute()
                    if vsechna_dochazka.data:
                        for d in vsechna_dochazka.data:
                            st.write(f"- {d['uzivatele']['jmeno']} {d['uzivatele']['prijmeni']} ({d['uzivatele']['role']}): {d['status']}")
                    else:
                        st.caption("Zatím nikdo nevyplnil docházku.")

    # --- 2. SEZNAM ČLENŮ ---
    elif volba == "Seznam členů sboru":
        st.header("🧑‍🚒 Členové sboru")
        clenove_res = supabase.table("uzivatele").select("jmeno, prijmeni, email, prezdivka, role").eq("sdh_id", st.session_state.sdh_id).execute()
        if clenove_res.data:
            for c in clenove_res.data:
                prez_info = f" ({c['prezdivka']})" if c.get('prezdivka') else " (přezdívka nenastavena)"
                st.write(f"• **{c['jmeno']} {c['prijmeni']}**{prez_info} — `{c['role']}` (Kontakt: {c['email']})")

    # --- 3. MOJE NASTAVENÍ (PRO ŘADOVÉ ČLENY) ---
    elif volba == "⚙️ Moje nastavení":
        st.header("⚙️ Moje osobní nastavení")
        st.write("Zde si můžete nastavit svou přezdívku pro snadnější přihlašování.")
        
        # Načteme aktuální přezdívku uživatele
        u_aktualni = supabase.table("uzivatele").select("prezdivka").eq("id", st.session_state.user_id).execute()
        strav_prezdivka = u_aktualni.data[0]["prezdivka"] if u_aktualni.data and u_aktualni.data[0]["prezdivka"] else ""
        
        nova_prez = st.text_input("Moje přezdívka (namísto emailu při loginu):", value=strav_prezdivka).strip()
        
        if st.button("Uložit nastavení přezdívky"):
            if nova_prez == "":
                supabase.table("uzivatele").update({"prezdivka": None}).eq("id", st.session_state.user_id).execute()
                st.success("Přezdívka byla odebrána.")
                st.rerun()
            else:
                try:
                    supabase.table("uzivatele").update({"prezdivka": nova_prez}).eq("id", st.session_state.user_id).execute()
                    st.success(f"Přezdívka '{nova_prez}' byla úspěšně uložena! Příště ji můžete použít k přihlášení.")
                    st.rerun()
                except Exception as e:
                    st.error("Tato přezdívka je již obsazená někým jiným. Zvolte prosím jinou.")

    # --- 4. SPRÁVA SBORU (PRO SPRÁVCE) ---
    elif volba == "🛠️ Správa sboru (Správce)":
        st.header("🛠️ Administrace sboru (Pouze Správce)")
        
        tab_akce, tab_clenove, tab_moje = st.tabs(["➕ Přidat akci", "⚙️ Správa členů a pozic", "👤 Moje vlastní přezdívka"])
        
        with tab_akce:
            st.subheader("Přidat novou akci")
            nova_akce_nazev = st.text_input("Název akce (např. Trénink na soutěž)")
            c1, c2 = st.columns(2)
            with c1:
                nova_akce_datum = st.date_input("Datum akce", datetime.date.today())
            with c2:
                nova_akce_cas = st.text_input("Čas akce", placeholder="18:00")
            nova_akce_typ = st.selectbox("Typ akce", ["Zásah", "Cvičení", "Brigáda", "Schůze", "Soutěž", "Jiné"])
            nova_akce_pozn = st.text_area("Poznámka k akci")
            
            if st.button("Vytvořit akci a zapsat do plánu", type="primary"):
                if nova_akce_nazev:
                    akce_data = {
                        "sdh_id": st.session_state.sdh_id,
                        "datum": str(nova_akce_datum),
                        "cas": nova_akce_cas,
                        "nazev_akce": nova_akce_nazev,
                        "typ_akce": nova_akce_typ,
                        "poznamka": nova_akce_pozn
                    }
                    supabase.table("akce").insert(akce_data).execute()
                    st.success("Akce byla úspěšně přidána!")
                    st.rerun()
                else:
                    st.warning("Vyplňte název akce.")
                    
        with tab_clenove:
            st.subheader("Změna pozic členů sboru")
            cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute()
            
            if cl_res.data:
                slovnik_clenu = {f"{u['jmeno']} {u['prijmeni']} (aktuálně: {u['role']})": u for u in cl_res.data}
                vybrany_cl_text = st.selectbox("Vyberte člena pro změnu pozice:", list(slovnik_clenu.keys()))
                vybrany_uzivatel = slovnik_clenu[vybrany_cl_text]
                
                nova_pozice = st.selectbox("Přiřadit novou pozici:", 
                                           ["Správce", "strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"])
                
                if st.button("Uložit novou pozici"):
                    supabase.table("uzivatele").update({"role": nova_pozice}).eq("id", vybrany_uzivatel["id"]).execute()
                    st.success(f"Pozice uživatele byla úspěšně změněna na {nova_pozice}!")
                    if vybrany_uzivatel["id"] == st.session_state.user_id:
                        st.session_state.user_role = nova_pozice
                    st.rerun()
                    
        with tab_moje:
            st.subheader("Nastavení přezdívky pro Správce")
            u_aktualni = supabase.table("uzivatele").select("prezdivka").eq("id", st.session_state.user_id).execute()
            strav_prezdivka = u_aktualni.data[0]["prezdivka"] if u_aktualni.data and u_aktualni.data[0]["prezdivka"] else ""
            
            nova_prez_spr = st.text_input("Zadej svou přezdívku (pro přihlášení místo emailu):", value=strav_prezdivka, key="spr_prez").strip()
            if st.button("Uložit přezdívku správce"):
                if nova_prez_spr == "":
                    supabase.table("uzivatele").update({"prezdivka": None}).eq("id", st.session_state.user_id).execute()
                    st.success("Přezdívka byla odebrána.")
                    st.rerun()
                else:
                    try:
                        supabase.table("uzivatele").update({"prezdivka": nova_prez_spr}).eq("id", st.session_state.user_id).execute()
                        st.success(f"Přezdívka '{nova_prez_spr}' uložena!")
                        st.rerun()
                    except Exception as e:
                        st.error("Tato přezdívka už v systému existuje. Zvolte prosím jinou.")

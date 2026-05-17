import streamlit as st
from supabase import create_client, Client
import bcrypt
import datetime
import base64
from PIL import Image
import io
import json
import os
from streamlit_calendar import calendar

# Nastavení stránky na široké zobrazení, aby se tam statistiky a tabulky krásně vešly
st.set_page_config(page_title="Portál SDH", page_icon="🚒", layout="wide")

# Propojení se Supabase
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- SOUKROMÉ ÚLOŽIŠTĚ PROFILOVEK ---
SOUBOR_AVATARU = "profilovky_data.json"

def nacti_vsechny_avatary():
    if os.path.exists(SOUBOR_AVATARU):
        try:
            with open(SOUBOR_AVATARU, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
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
    if not avatar_data:
        return "🧑‍🚒"
    if str(avatar_data).startswith("data:image"):
        return f"""<img src="{avatar_data}" style="border-radius: 50%; width: 35px; height: 35px; object-fit: cover; vertical-align: middle; margin-right: 8px;">"""
    return f"""<span style="font-size: 24px; vertical-align: middle; margin-right: 8px;">{avatar_data}</span>"""


# Inicializace session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_jmeno = ""
    st.session_state.user_role = "člen"
    st.session_state.sdh_id = None
    st.session_state.sdh_nazev = ""
    st.session_state.user_avatar = "🧑‍🚒"
    st.session_state.stranka = "Plán akcí & Docházka"

# Pomocné funkce pro trvalé přihlášení
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
                st.session_state.stranka = "Plán akcí & Docházka"
        except Exception:
            pass

nacti_trvale_prihlaseni()

st.title("🚒 Portál SDH")
st.caption("Profesionální informační systém pro dobrovolné hasiče")

# --- STRUKTURA PRO PŘIHLÁŠENÉ UŽIVATELE (BOČNÍ PANEL) ---
if st.session_state.logged_in:
    
    je_spravce = False
    vlastnik_res = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=False).limit(1).execute()
    if vlastnik_res.data and vlastnik_res.data[0]["id"] == st.session_state.user_id:
        je_spravce = True

    # 1. TLAČÍTKO "MOJE NASTAVENÍ"
    if st.sidebar.button("⚙️ Moje nastavení", use_container_width=True):
        st.session_state.stranka = "Moje nastavení"
        st.rerun()
        
    st.sidebar.write("---")
    st.session_state.user_avatar = ziskej_avatar_uzivatele(st.session_state.user_id)
    
    # 2. VIZITKA
    av_html = zobraz_profilovku(st.session_state.user_avatar)
    st.sidebar.markdown(f"""<div style="display: flex; align-items: center;">{av_html}<h3 style="margin: 0; display: inline-block;">{st.session_state.user_jmeno}</h3></div>""", unsafe_allow_html=True)
    
    if st.sidebar.button(f"🏢 {st.session_state.sdh_nazev}", help="Zobrazit členy sboru", key="link_sbor"):
        st.session_state.stranka = "Seznam členů sboru"
        st.rerun()
    
    zobrazeni_role = st.session_state.user_role
    if je_spravce:
        zobrazeni_role += " (Správce)"
    st.sidebar.caption(f"Pozice: {zobrazeni_role}")
    
    st.sidebar.write("---")
    
    # 3. ROZŠÍŘENÉ ROZBALOVACÍ MENU
    menu_moznosti = ["Plán akcí & Docházka", "📊 Statistiky docházky", "🛠️ Technika & Revize", "Seznam členů sboru"]
    if je_spravce:
        menu_moznosti.append("⚙️ Správa sboru (Správce)")
        
    vsechny_moznosti_menu = menu_moznosti.copy()
    if st.session_state.stranka == "Moje nastavení" and "Moje nastavení" not in vsechny_moznosti_menu:
        vsechny_moznosti_menu.append("Moje nastavení")
        
    index_vypoctu = vsechny_moznosti_menu.index(st.session_state.stranka) if st.session_state.stranka in vsechny_moznosti_menu else 0
    volba_menu = st.sidebar.selectbox("Kam chcete jít?", vsechny_moznosti_menu, index=index_vypoctu)
    
    if st.session_state.stranka != volba_menu:
        st.session_state.stranka = volba_menu
        st.rerun()

    volba = st.session_state.stranka
    
    st.sidebar.write("---")
    if st.sidebar.button("Odhlásit se", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.sdh_id = None
        st.session_state.stranka = "Plán akcí & Docházka"
        if "user_id" in st.query_params:
            del st.query_params["user_id"]
        st.rerun()

# --- SEKCE PRO NEPŘIHLÁŠENÉ ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔒 Přihlášení", "📝 Registrace nového člena / sboru"])
    
    with tab1:
        st.subheader("Přihlášení k portálu")
        login_input = st.text_input("E-mail nebo Přezdívka", key="login_input").strip()
        login_heslo = st.text_input("Heslo", type="password", key="login_password")
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
                        st.session_state.stranka = "Plán akcí & Docházka"
                        
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
                
        st.info("💡 Zapomněli jste heslo? Požádejte velitele/správce vašeho sboru, může vám ho vyresetovat přímo v administraci systému.")

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
        
        pozice_na_utoku = ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"]
        vybrana_role = st.selectbox("Vyberte vaši hlavní pozici ve sboru:", pozice_na_utoku)
        
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
                        "prezdivka": None
                    }
                    supabase.table("uzivatele").insert(uzivatel_data).execute()
                    st.success("Registrace proběhla úspěšně! Nyní se můžete přihlásit.")
                except Exception as e:
                    st.error(f"Chyba při registraci. Detaily: {e}")
            else:
                st.warning("Prosím vyplňte všechny údaje.")

# --- OBSAH STRÁNEK PRO PŘIHLÁŠENÉ ---
elif st.session_state.logged_in:
    
    # --- 1. PLÁN AKCÍ & DOCHÁZKA ---
    if volba == "Plán akcí & Docházka":
        st.header("📅 Plán činností a docházka")
        
        st.markdown("#### 🔍 Filtrovat zobrazené typy akcí")
        typy_k_vyberu = ["Zásah", "Cvičení", "Soutěž", "Brigáda", "Schůze", "Jiné"]
        vybrane_typy = st.multiselect("Zobrazit pouze:", typy_k_vyberu, default=typy_k_vyberu)
        
        akce_res = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).order("datum").execute()
        
        vsechny_akce = akce_res.data if akce_res.data else []
        filtrovane_akce = [a for a in vsechny_akce if a["typ_akce"] in vybrane_typy]
        
        st.subheader("🗓️ Kalendářní přehled")
        kalendar_udalosti = []
        barvy_akci = {"Zásah": "#d32f2f", "Cvičení": "#1976d2", "Soutěž": "#f57c00", "Brigáda": "#388e3c", "Schůze": "#7b1fa2", "Jiné": "#455a64"}
        
        for akce in filtrovane_akce:
            barva = barvy_akci.get(akce["typ_akce"], "#1976d2")
            kalendar_udalosti.append({
                "title": f"{akce['nazev_akce']} ({akce['cas'] if akce.get('cas') else ''})",
                "start": akce["datum"],
                "end": akce["datum"],
                "backgroundColor": barva,
                "borderColor": barva,
                "allDay": True
            })
            
        kalendar_options = {
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listMonth"},
            "initialView": "dayGridMonth", "locale": "cs", "firstDay": 1
        }
        calendar(events=kalendar_udalosti, options=kalendar_options, key="sdh_full_calendar")
        
        st.write("---")
        
        dnes = datetime.date.today().isoformat()
        nadcházejici = [a for a in filtrovane_akce if a["datum"] >= dnes]
        archiv_akci = [a for a in filtrovane_akce if a["datum"] < dnes]
        
        tab_budouci, tab_historie = st.tabs([f"📋 Nadcházející akce ({len(nadcházejici)})", f"🗄️ Archiv minulých akcí ({len(archiv_akci)})"])
        
        def vykresli_seznam_akci(seznam, je_historie=False):
            if not seznam:
                st.write("Žádné akce v této kategorii.")
                return
            for akce in seznam:
                cas_info = f" v {akce['cas']}" if akce.get('cas') else ""
                ikonka = "🚨" if akce["typ_akce"] == "Zásah" else "📅"
                
                with st.expander(f"{ikonka} {akce['datum']}{cas_info} - {akce['nazev_akce']} ({akce['typ_akce']})"):
                    if akce["typ_akce"] == "Zásah" and akce.get("cislo_vyjezdu"):
                        st.error(f"🔢 **Číslo výjezdu:** {akce['cislo_vyjezdu']} | **Technika:** {akce.get('pouzita_technika','')} | **Motohodiny/Km:** {akce.get('motohodiny_uziti','')}")
                    
                    if akce.get('poznamka'):
                        st.markdown(f"ℹ️ **Poznámka k akci:**\n> {akce['poznamka']}")
                    
                    doch_res = supabase.table("dochazka").select("status").eq("akce_id", akce["id"]).eq("uzivatel_id", st.session_state.user_id).execute()
                    aktualni_status = doch_res.data[0]["status"] if doch_res.data else "Nezadáno"
                    st.write(f"Moje účast: **{aktualni_status}**")
                    
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
                    
                    if je_spravce:
                        st.write("---")
                        if st.button("Smazat akci ❌", key=f"del_{akce['id']}", type="secondary"):
                            supabase.table("dochazka").delete().eq("akce_id", akce["id"]).execute()
                            supabase.table("akce").delete().eq("id", akce["id"]).execute()
                            st.success("Smazáno.")
                            st.rerun()
                    
                    st.write("---")
                    st.write("**Přehled ostatních:**")
                    vsechna_dochazka = supabase.table("dochazka").select("status, uzivatele(id, jmeno, prijmeni, role)").eq("akce_id", akce["id"]).execute()
                    if vsechna_dochazka.data:
                        for d in vsechna_dochazka.data:
                            cl_id = d['uzivatele']['id']
                            av_mini = zobraz_profilovku(ziskej_avatar_uzivatele(cl_id))
                            
                            html_dochazka = f"""
                            <div style="display: flex; align-items: center; margin-bottom: 6px;">
                                {av_mini}
                                <span>{d['uzivatele']['jmeno']} {d['uzivatele']['prijmeni']} ({d['uzivatele']['role']}): <b>{d['status']}</b></span>
                            </div>
                            """
                            st.markdown(html_dochazka, unsafe_allow_html=True)
                    else:
                        st.caption("Zatím nikdo nevyplnil.")

        with tab_budouci:
            vykresli_seznam_akci(nadcházejici, je_historie=False)
        with tab_historie:
            vykresli_seznam_akci(archiv_akci, je_historie=True)

    # --- 2. STATISTIKY DOCHÁZKY ---
    elif volba == "📊 Statistiky docházky":
        st.header("📊 Statistiky a docházková úspěšnost")
        
        cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute()
        celkovy_pocet_akci_res = supabase.table("akce").select("id", count="exact").eq("sdh_id", st.session_state.sdh_id).execute()
        celkem_akci = celkovy_pocet_akci_res.count if celkovy_pocet_akci_res.count else 0
        
        if celkem_akci == 0:
            st.info("Zatím nelze spočítat statistiky, sbor nemá vytvořené žádné akce.")
        elif cl_res.data:
            st.write(f"Celkem evidovaných akcí v systému: **{celkem_akci}**")
            st.write("Tabulka úspěšnosti členů (Zadali status 'Jdu'):")
            
            stats_list = []
            for clen in cl_res.data:
                u_doch = supabase.table("dochazka").select("status").eq("uzivatel_id", clen["id"]).eq("status", "Jdu").execute()
                pocet_jdu = len(u_doch.data) if u_doch.data else 0
                procento = round((pocet_jdu / celkem_akci) * 100, 1)
                
                stats_list.append({
                    "Hasič": f"{clen['jmeno']} {clen['prijmeni']}",
                    "Pozice": clen["role"],
                    "Účastí": f"{pocet_jdu} z {celkem_akci}",
                    "Procentuálně": f"{procento} %",
                    "Hodnota_Raw": procento
                })
            
            stats_list = sorted(stats_list, key=lambda x: x["Hodnota_Raw"], reverse=True)
            
            for idx, s in enumerate(stats_list):
                medaile = "🥇 " if idx == 0 else "🥈 " if idx == 1 else "🥉 " if idx == 2 else "🚒 "
                st.markdown(f"**{medaile} {s['Hasič']}** ({s['Pozice']}) — Účast na **{s['Procentuálně']}** akcí (`{s['Účastí']}`)")
                st.progress(min(int(s["Hodnota_Raw"]), 100))

    # --- 3. TECHNIKA & REVIZE ---
    elif volba == "🛠️ Technika & Revize":
        st.header("🛠️ Evidence techniky a hlídač revizí / STK")
        
        if je_spravce:
            with st.expander("➕ Přidat nový kus techniky / vybavení"):
                t_nazev = st.text_input("Název (např. CAS 20 Scania, Pila Stihl MS 261, Dýchací přístroj Saturn)")
                t_typ = st.selectbox("Typ techniky", ["Vozidlo", "Výzbroj", "Výstroj", "Jiné"])
                t_revize = st.date_input("Termín příští STK / revize", datetime.date.today() + datetime.timedelta(days=365))
                t_stav = st.selectbox("Aktuální stav", ["V pořádku", "V opravě", "Mimo provoz"])
                t_pozn = st.text_input("Poznámka")
                
                if st.button("Uložit do inventáře"):
                    if t_nazev:
                        supabase.table("technika").insert({
                            "sdh_id": st.session_state.sdh_id, "nazev": t_nazev, "typ": t_typ,
                            "stk_revize": str(t_revize), "stav": t_stav, "poznamka": t_pozn
                        }).execute()
                        st.success("Technika úspěšně uložena.")
                        st.rerun()
                        
        st.write("---")
        tech_res = supabase.table("technika").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
        data_techniky = tech_res.data if tech_res.data else []
        
        if not data_techniky:
            st.info("Zatím není zaevidována žádná technika.")
        else:
            dnes_date = datetime.date.today()
            for t in data_techniky:
                stav_barva = "🟢" if t["stav"] == "V pořádku" else "🟡" if t["stav"] == "V opravě" else "🔴"
                
                revize_info = "Není zadáno"
                upozorneni_revize = ""
                if t.get("stk_revize"):
                    r_date = datetime.datetime.strptime(t["stk_revize"], "%Y-%m-%d").date()
                    revize_info = r_date.strftime("%d.%m.%Y")
                    if r_date < dnes_date:
                        upozorneni_revize = "⚠️ **PROPADLÁ REVIZE / STK!**"
                
                col_t1, col_t2 = st.columns([3, 1])
                with col_t1:
                    st.markdown(f"### {stav_barva} {t['nazev']} `[{t['typ']}]`")
                    if t['poznamka']: st.caption(f"Poznámka: {t['poznamka']}")
                with col_t2:
                    st.write(f"STK/Revize do: **{revize_info}**")
                    if upozorneni_revize: st.error(upozorneni_revize)
                    
                    if je_spravce:
                        if st.button("Smazat 🗑️", key=f"del_t_{t['id']}"):
                            supabase.table("technika").delete().eq("id", t['id']).execute()
                            st.rerun()
                st.write("---")

    # --- 4. SEZNAM ČLENŮ ---
    elif volba == "Seznam členů sboru":
        st.header("🧑‍🚒 Členové sboru")
        clenove_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, prezdivka, role").eq("sdh_id", st.session_state.sdh_id).execute()
        if clenove_res.data:
            for c in clenove_res.data:
                prez_info = f" ({c['prezdivka']})" if c.get('prezdivka') else ""
                cl_av = ziskej_avatar_uzivatele(c["id"])
                av_mini = zobraz_profilovku(cl_av)
                
                html_clen = f"""
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    {av_mini}
                    <span><b>{c['jmeno']} {c['prijmeni']}</b>{prez_info} — <code>{c['role']}</code></span>
                </div>
                """
                st.markdown(html_clen, unsafe_allow_html=True)

    # --- 5. MOJE NASTAVENÍ ---
    elif volba == "Moje nastavení":
        st.header("⚙️ Moje osobní nastavení")
        u_aktualni = supabase.table("uzivatele").select("prezdivka, role, email").eq("id", st.session_state.user_id).execute()
        strav_avatar = ziskej_avatar_uzivatele(st.session_state.user_id)
        strav_prezdivka = u_aktualni.data[0]["prezdivka"] if u_aktualni.data and u_aktualni.data[0]["prezdivka"] else ""
        strav_role = u_aktualni.data[0]["role"] if u_aktualni.data else "člen"
        strav_email = u_aktualni.data[0]["email"] if u_aktualni.data else ""
        
        st.subheader("🖼️ Moje profilovka")
        typ_avataru = st.radio("Vyber si typ profilovky:", ["Chci použít Emoji text", "Chci nahrát vlastní fotku / obrázek"])
        vysledny_avatar = strav_avatar
        
        if typ_avataru == "Chci použít Emoji text":
            vysledny_avatar = st.text_input("Zadej libovolné emoji:", value=strav_avatar if not str(strav_avatar).startswith("data:image") else "🧑‍🚒", max_chars=5)
        else:
            nahrany_soubor = st.file_uploader("Nahraj fotku:", type=["png", "jpg", "jpeg"])
            if nahrany_soubor is not None:
                img = Image.open(nahrany_soubor).convert("RGB")
                img.thumbnail((120, 120))
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                vysledny_avatar = f"data:image/png;base64,{img_str}"
                st.image(img, width=70)
        
        nova_prez = st.text_input("Moje přezdívka:", value=strav_prezdivka).strip()
        novy_email = st.text_input("Můj kontaktní E-mail:", value=strav_email).strip()
        seznam_pozic = ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"]
        nova_role = st.selectbox("Moje hlavní pozice na útoku:", seznam_pozic, index=seznam_pozic.index(strav_role) if strav_role in seznam_pozic else 7)
        
        if st.button("Uložit všechny změny", type="primary", use_container_width=True):
            if novy_email:
                try:
                    supabase.table("uzivatele").update({"role": nova_role, "email": novy_email, "prezdivka": nova_prez if nova_prez != "" else None}).eq("id", st.session_state.user_id).execute()
                    uloz_avatar_uzivatele(st.session_state.user_id, vysledny_avatar)
                    st.session_state.user_role = nova_role
                    st.session_state.user_avatar = vysledny_avatar
                    st.success("Profil uložen!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Změny nelze uložit. Přezdívka nebo E-mail jsou již pravděpodobně v systému obsazené jiným členem. Detaily: {e}")

    # --- 6. SPRÁVA SBORU (ADMINISTRACE) ---
    elif volba == "⚙️ Správa sboru (Správce)":
        st.header("🛠️ Administrace sboru (Pouze Správce)")
        tab_akce, tab_clenove, tab_hesla = st.tabs(["➕ Přidat akci / Výjezd", "⚙️ Správa členů", "🔐 Reset hesel"])
        
        with tab_akce:
            st.subheader("Přidat novou akci nebo ostrý zásah")
            nova_akce_nazev = st.text_input("Název akce (např. Požár lesa, Prověřovací cvičení, Soutěž O pohár starosty)")
            nova_akce_typ = st.selectbox("Typ akce", ["Zásah", "Cvičení", "Brigáda", "Schůze", "Soutěž", "Jiné"])
            
            c_v, p_t, m_h = "", "", ""
            if nova_akce_typ == "Zásah":
                st.error("🚨 VYPLŇUJETE EXTRA ÚDAJE PRO KNIHU VÝJEZDŮ")
                col_z1, col_z2, col_z3 = st.columns(3)
                with col_z1: c_v = st.text_input("Číslo výjezdu (KOPIS)")
                with col_z2: p_t = st.text_input("Použitá technika (např. CAS 20, DA)")
                with col_z3: m_h = st.text_input("Motohodiny / Km")
                
            c1, c2 = st.columns(2)
            with c1: nova_akce_datum = st.date_input("Datum akce", datetime.date.today())
            with c2: nova_akce_cas = st.text_input("Čas akce", placeholder="18:00")
            nova_akce_pozn = st.text_area("Poznámka / Popis akce")
            
            if st.button("Vytvořit akci a zapsat do plánu", type="primary"):
                if nova_akce_nazev:
                    akce_data = {
                        "sdh_id": st.session_state.sdh_id, "datum": str(nova_akce_datum), "cas": nova_akce_cas,
                        "nazev_akce": nova_akce_nazev, "typ_akce": nova_akce_typ, "poznamka": nova_akce_pozn,
                        "cislo_vyjezdu": c_v if c_v else None, "pouzita_technika": p_t if p_t else None, "motohodiny_uziti": m_h if m_h else None
                    }
                    supabase.table("akce").insert(akce_data).execute()
                    st.success("Akce úspěšně přidána!")
                    st.rerun()
                    
        with tab_clenove:
            st.subheader("Změna pozic členů")
            cl_res = supabase.table("uzivatele").select("id, jmeno, prijmeni, role").eq("sdh_id", st.session_state.sdh_id).execute()
            if cl_res.data:
                slovnik_clenu = {f"{u['jmeno']} {u['prijmeni']} ({u['role']})": u for u in cl_res.data}
                vybrany_cl_text = st.selectbox("Vyberte člena:", list(slovnik_clenu.keys()))
                vybrany_uzivatel = slovnik_clenu[vybrany_cl_text]
                nova_pozice_admin = st.selectbox("Nová pozice na útoku:", ["strojník", "levý proud", "pravý proud", "béčka", "spoj", "koš", "rozdělovač", "člen"])
                
                if st.button("Uložit pozici"):
                    supabase.table("uzivatele").update({"role": nova_pozice_admin}).eq("id", vybrany_uzivatel["id"]).execute()
                    st.success("Pozice změněna!")
                    st.rerun()
                    
        with tab_hesla:
            st.subheader("🔐 Nouzový reset hesla člena")
            st.caption("Pokud hasič zapomene heslo, jako správce mu zde můžete vygenerovat nové.")
            if cl_res.data:
                slovnik_hesla = {f"{u['jmeno']} {u['prijmeni']}": u for u in cl_res.data}
                user_pro_reset = st.selectbox("Vyberte člena pro reset:", list(slovnik_hesla.keys()))
                nove_heslo_vstup = st.text_input("Zadejte nové bezpečné heslo:", type="password")
                
                if st.button("Natvrdo změnit heslo uživateli"):
                    if nove_heslo_vstup:
                        hashed_nové = bcrypt.hashpw(nove_heslo_vstup.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        supabase.table("uzivatele").update({"heslo_hash": hashed_nové}).eq("id", slovnik_hesla[user_pro_reset]["id"]).execute()
                        st.success(f"Heslo pro uživatele {user_pro_reset} bylo úspěšně přepsáno!")
                    else:
                        st.warning("Zadejte prosím nějaké heslo.")

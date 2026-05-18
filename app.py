import streamlit as st
from supabase import create_client, Client
import bcrypt
import datetime
import json
import os
import re
import urllib.parse
from streamlit_calendar import calendar

# ==========================================
# CRITICAL INFRASTRUCTURE
# RESQ_PORTAL
# ==========================================

st.set_page_config(page_title="RESQ Portal", page_icon="🚨", layout="wide")

# Inicializace session state
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

SOUBOR_AVATARU = "profilovky_data.json"

def nacti_vsechny_avatary():
    if os.path.exists(SOUBOR_AVATARU):
        try:
            with open(SOUBOR_AVATARU, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def ziskej_avatar_uzivatele(user_id):
    avatary = nacti_vsechny_avatary()
    return avatary.get(str(user_id), "🧑‍🚒")

def uloz_avatar_uzivatele(user_id, avatar_data):
    data = nacti_vsechny_avatary()
    data[str(user_id)] = avatar_data
    with open(SOUBOR_AVATARU, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

def generuj_qr_kod_url(iban, castka, zprava):
    cistý_iban = re.sub(r'\s+', '', iban)
    zprava_url = urllib.parse.quote(zprava[:20])
    return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={cistý_iban[2:]}&bankCode={cistý_iban[2:6]}&amount={castka}&currency=CZK&message={zprava_url}"

st.title("RESQ Portal")

# PŘIHLAŠOVÁNÍ A REGISTRACE
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Přihlášení", "Registrace"])
    
    with tab1:
        login_input = st.text_input("E-mail nebo Přezdívka").strip()
        login_heslo = st.text_input("Heslo", type="password")
        
        if st.button("Přihlásit se", type="primary"):
            if login_input and login_heslo:
                try:
                    res = supabase.table("uzivatele").select("*").eq("email", login_input).execute()
                    if not res.data:
                        try:
                            res = supabase.table("uzivatele").select("*").eq("prezdivka", login_input).execute()
                        except Exception:
                            res.data = []

                    if res.data:
                        user = res.data[0]
                        if bcrypt.checkpw(login_heslo.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                            sdh_nazev_db = "Neznámý sbor"
                            sdh_iban_db = "CZ1234567890123456789012"
                            if user.get("sdh_id"):
                                sbor_res = supabase.table("sbory").select("*").eq("id", user["sdh_id"]).execute()
                                if sbor_res.data:
                                    sdh_nazev_db = sbor_res.data[0].get("nazev_sdh", sbor_res.data[0].get("nazev", "Sbor bez názvu"))
                                    sdh_iban_db = sbor_res.data[0].get("iban", "CZ1234567890123456789012")

                            st.session_state.logged_in = True
                            st.session_state.user_id = user["id"]
                            st.session_state.user_jmeno = f"{user['jmeno']} {user['prijmeni']}"
                            st.session_state.user_role = user["role"]
                            st.session_state.user_schvalen = user.get("schvalen", True)
                            st.session_state.sdh_id = user["sdh_id"]
                            st.session_state.sdh_nazev = sdh_nazev_db
                            st.session_state.sdh_iban = sdh_iban_db
                            st.session_state.user_avatar = ziskej_avatar_uzivatele(user["id"])
                            st.rerun()
                        else:
                            st.error("Nesprávné heslo.")
                    else:
                        st.error("Uživatel neexistuje.")
                except Exception as e:
                    st.error(f"Chyba spojení s databází: {e}")

    with tab2:
        try:
            sbory_res = supabase.table("sbory").select("*").execute()
            seznam_sboru = {s.get("nazev_sdh", s.get("nazev", "Sbor")): s["id"] for s in sbory_res.data} if sbory_res.data else {}
        except Exception:
            seznam_sboru = {}
            
        volba_sboru = st.radio("Sbor:", ["Přidat se k existujícímu sboru", "Zaregistrovat nový sbor"])
        
        vybrany_sdh_id = None
        if volba_sboru == "Přidat se k existujícímu sboru":
            if seznam_sboru:
                vybrany_sbor_nazev = st.selectbox("Vyberte sbor:", list(seznam_sboru.keys()))
                vybrany_sdh_id = seznam_sboru[vybrany_sbor_nazev]
        else:
            novy_sbor_nazev = st.text_input("Název nového sboru")
            novy_sbor_iban = st.text_input("IBAN sboru")
            
        reg_jmeno = st.text_input("Jméno")
        reg_prijmeni = st.text_input("Příjmení")
        reg_email = st.text_input("E-mail")
        reg_heslo = st.text_input("Heslo", type="password")
        vybrana_role = st.selectbox("Role:", ["velitel", "strojník", "hasič", "člen"])
        
        if st.button("Registrovat se"):
            if reg_jmeno and reg_prijmeni and reg_email and reg_heslo and (vybrany_sdh_id or novy_sbor_nazev):
                try:
                    if volba_sboru == "Zaregistrovat nový sbor":
                        try:
                            sbor_ins = supabase.table("sbory").insert({"nazev_sdh": novy_sbor_nazev, "iban": novy_sbor_iban}).execute()
                        except Exception:
                            sbor_ins = supabase.table("sbory").insert({"nazev": novy_sbor_nazev, "iban": novy_sbor_iban}).execute()
                        vybrany_sdh_id = sbor_ins.data[0]["id"]
                    
                    hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    je_prvni = len(supabase.table("uzivatele").select("id").eq("sdh_id", vybrany_sdh_id).execute().data) == 0
                    
                    supabase.table("uzivatele").insert({
                        "sdh_id": vybrany_sdh_id,
                        "jmeno": reg_jmeno,
                        "prijmeni": reg_prijmeni,
                        "email": reg_email,
                        "heslo_hash": hashed,
                        "role": vybrana_role,
                        "schvalen": je_prvni
                    }).execute()
                    st.success("Registrace úspěšná. Počkejte na schválení velitelem.")
                except Exception as e:
                    st.error(f"Chyba při registraci: {e}")

# ČEKÁNÍ NA SCHVÁLENÍ
elif st.session_state.logged_in and not st.session_state.user_schvalen:
    st.warning(f"Váš účet čeká na schválení velitelem sboru {st.session_state.sdh_nazev}.")
    if st.button("Odhlásit se"):
        st.session_state.logged_in = False
        st.rerun()

# PO PŘIHLÁŠENÍ
else:
    je_spravce = False
    try:
        vlastnik_res = supabase.table("uzivatele").select("id").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=False).limit(1).execute()
        if (vlastnik_res.data and vlastnik_res.data[0]["id"] == st.session_state.user_id) or st.session_state.user_role == "velitel":
            je_spravce = True
    except Exception:
        if st.session_state.user_role == "velitel":
            je_spravce = True

    st.sidebar.write(f"Uživatel: {st.session_state.user_avatar} {st.session_state.user_jmeno}")
    st.sidebar.write(f"Role: {st.session_state.user_role}")
    st.sidebar.write(f"Sbor: {st.session_state.sdh_nazev}")
    st.sidebar.markdown("---")
    
    menu_polozky = [
        "🚨 Poplach & Výjezd", 
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
        
    volba = st.sidebar.radio("Menu", menu_polozky)

    # POPLACHY
    if volba == "🚨 Poplach & Výjezd":
        st.header("Poplachy")
        if je_spravce:
            with st.expander("Vyhlásit nový poplach"):
                pop_udalost = st.text_input("Událost (např. Požár)")
                pop_misto = st.text_input("Místo")
                if st.button("Vyhlásit poplach"):
                    if pop_udalost:
                        try:
                            supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", st.session_state.sdh_id).execute()
                            supabase.table("poplachy").insert({"sdh_id": st.session_state.sdh_id, "udalost": pop_udalost, "misto": pop_misto}).execute()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Chyba vyhlášení: {e}")

        try:
            pop_res = supabase.table("poplachy").select("*").eq("sdh_id", st.session_state.sdh_id).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
            aktivni_poplachy = pop_res.data
        except Exception:
            aktivni_poplachy = []
        
        if aktivni_poplachy:
            aktivni_poplach = aktivni_poplachy[0]
            st.error(f"⚠️ AKTIVNÍ POPLACH: {aktivni_poplach['udalost']} - Místo: {aktivni_poplach['misto']}")
            
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                if st.button("🟢 Jedu ihned", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": "ihned"}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p2:
                cas_min = st.selectbox("Dojezd:", ["5 min", "10 min", "15 min"])
                if st.button("🟡 Jedu s prodlevou", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Jedu na zbrojnici", "cas_prijezdu": cas_min}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c_p3:
                if st.button("🔴 Nemůžu", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": aktivni_poplach["id"], "uzivatel_id": st.session_state.user_id, "stav": "Nedorazím", "cas_prijezdu": None}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()

            try:
                reakce_res = supabase.table("poplach_reakce").select("stav, cas_prijezdu, uzivatele(jmeno, prijmeni, role)").eq("poplach_id", aktivni_poplach["id"]).execute()
                vsechny_reakce = reakce_res.data if reakce_res.data else []
            except Exception:
                vsechny_reakce = []

            if vsechny_reakce:
                st.subheader("Reakce členů:")
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    st.write("**Jedou:**")
                    for r in vsechny_reakce:
                        if r["stav"] == "Jedu na zbrojnici" and r.get("uzivatele"):
                            st.write(f"✅ {r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']} ({r['cas_prijezdu']})")
                with col_r2:
                    st.write("**Nejedou:**")
                    for r in vsechny_reakce:
                        if r["stav"] == "Nedorazím" and r.get("uzivatele"):
                            st.write(f"❌ {r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}")
            
            if je_spravce and st.button("Ukončit poplach"):
                supabase.table("poplachy").update({"aktivni": False}).eq("id", aktivni_poplach["id"]).execute()
                st.rerun()
        else:
            st.success("Žádný aktivní poplach.")

    # PLÁN AKCÍ
    elif volba == "📅 Plán akcí & Docházka":
        st.header("Plán akcí")
        try:
            akce_res = supabase.table("akce").select("*").eq("sdh_id", st.session_state.sdh_id).order("datum").execute()
            vsechny_akce = akce_res.data if akce_res.data else []
        except Exception:
            vsechny_akce = []
        
        kalendar_udalosti = []
        for akce in vsechny_akce:
            kalendar_udalosti.append({
                "id": str(akce["id"]),
                "title": akce["nazev_akce"],
                "start": akce["datum"],
                "end": akce["datum"],
                "allDay": True
            })
        
        calendar(events=kalendar_udalosti, options={"locale": "cs", "firstDay": 1}, key="portal_calendar")
        
        st.subheader("Docházka na nadcházející akce")
        for akce in vsechny_akce:
            if akce["datum"] >= datetime.date.today().isoformat():
                with st.expander(f"{akce['datum']} — {akce['nazev_akce']}"):
                    st.write(akce.get("poznamka", ""))
                    
                    stav_moje = "Nenahlášeno"
                    try:
                        doch_res = supabase.table("dochazka").select("status").eq("akce_id", akce["id"]).eq("uzivatel_id", st.session_state.user_id).execute()
                        if doch_res.data:
                            stav_moje = doch_res.data[0]["status"]
                    except Exception:
                        pass
                    
                    st.write(f"Moje docházka: **{stav_moje}**")
                    c1, c2 = st.columns(2)
                    if c1.button("Jdu 👍", key=f"j_{akce['id']}"):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Jdu"}, on_conflict="akce_id,uzivatel_id").execute()
                        st.rerun()
                    if c2.button("Nejdu 👎", key=f"n_{akce['id']}"):
                        supabase.table("dochazka").upsert({"akce_id": akce["id"], "uzivatel_id": st.session_state.user_id, "status": "Nejdu"}, on_conflict="akce_id,uzivatel_id").execute()
                        st.rerun()

    # POKLADNA
    elif volba == "🪙 Pokladna & Příspěvky":
        st.header("Pokladna")
        try:
            trans_res = supabase.table("pokladna").select("*").eq("sdh_id", st.session_state.sdh_id).execute()
            vsechny_trans = trans_res.data if trans_res.data else []
        except Exception:
            vsechny_trans = []
        
        prijmy = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Příjem")
        vydaje = sum(float(t["castka"]) for t in vsechny_trans if t["smer"] == "Výdaj")
        
        st.metric("Stav konta", f"{prijmy-vydaje:,.2f} Kč")
        
        st.subheader("Platba členského příspěvku")
        castka_p = st.number_input("Částka Kč:", value=500, step=100)
        msg = f"Prispevek {st.session_state.user_jmeno}"
        
        qr_url = generuj_qr_kod_url(st.session_state.sdh_iban, castka_p, msg)
        st.image(qr_url, caption="Naskenujte pro platbu v bance")
        st.code(f"Účet: {st.session_state.sdh_iban}\nZpráva: {msg}")

    # NÁSTĚNKA
    elif volba == "📢 Nástěnka sboru":
        st.header("Nástěnka")
        if je_spravce:
            with st.expander("Přidat příspěvek"):
                nadpis = st.text_input("Nadpis")
                text = st.text_area("Text")
                if st.button("Publikovat"):
                    supabase.table("nastenka").insert({"sdh_id": st.session_state.sdh_id, "autor_jmeno": st.session_state.user_jmeno, "nadpis": nadpis, "text": text, "dulezite": False}).execute()
                    st.rerun()
                    
        try:
            zpravy = supabase.table("nastenka").select("*").eq("sdh_id", st.session_state.sdh_id).order("created_at", desc=True).execute().data
        except Exception:
            zpravy = []
            
        for z in (zpravy if zpravy else []):
            st.subheader(z['nadpis'])
            st.write(z['text'])
            st.caption(f"Autor: {z['autor_jmeno']} | Datum: {z['created_at'][:10]}")
            st.markdown("---")

    # SKLAD
    elif volba == "📦 Sklad & Výstroj OOP":
        st.header("Sklad materiálu")
        try:
            vsechen_sklad = supabase.table("sklad").select("*, uzivatele(jmeno, prijmeni)").eq("sdh_id", st.session_state.sdh_id).execute().data
        except Exception:
            try:
                vsechen_sklad = supabase.table("sklad").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
            except Exception:
                vsechen_sklad = []
        
        if je_spravce:
            with st.expander("Přidat položku"):
                nazev_it = st.text_input("Název")
                vel_it = st.text_input("Velikost")
                if st.button("Uložit"):
                    supabase.table("sklad").insert({"sdh_id": st.session_state.sdh_id, "nazev": nazev_it, "velikost": vel_it, "stav": "V pořádku"}).execute()
                    st.rerun()

        for i in (vsechen_sklad if vsechen_sklad else []):
            stav = f"Vydáno: {i['uzivatele']['jmeno']} {i['uzivatele']['prijmeni']}" if i.get('uzivatele') else "Na skladě"
            st.write(f"📦 **{i['nazev']}** (Velikost: {i['velikost']}) - {stav}")

    # TECHNIKA
    elif volba == "🛠️ Technika & Revize":
        st.header("Technika a vozidla")
        try:
            tech = supabase.table("technika").select("*").eq("sdh_id", st.session_state.sdh_id).execute().data
        except Exception:
            tech = []
        
        if je_spravce:
            with st.expander("Přidat techniku"):
                t_nazev = st.text_input("Název")
                t_stk = st.date_input("STK / Revize do")
                if st.button("Uložit"):
                    supabase.table("technika").insert({"sdh_id": st.session_state.sdh_id, "nazev": t_nazev, "stk_revize": str(t_stk), "typ": "Vozidlo", "stav": "V pořádku"}).execute()
                    st.rerun()
                    
        for t in (tech if tech else []):
            st.write(f"🚒 **{t['nazev']}** - Platnost STK/Revize: {t['stk_revize']}")

    # SEZNAM ČLENŮ
    elif volba == "🧑‍🚒 Seznam členů":
        st.header("Seznam členů")
        try:
            clenove = supabase.table("uzivatele").select("jmeno, prijmeni, role, schvalen").eq("sdh_id", st.session_state.sdh_id).execute().data
        except Exception:
            clenove = []
            
        for c in (clenove if clenove else []):
            if c.get("schvalen", True):
                st.write(f"🧑‍🚒 {c['jmeno']} {c['prijmeni']} - Role: {c['role']}")

    # MOJE NASTAVENÍ
    elif volba == "⚙️ Moje nastavení":
        st.header("Moje nastavení")
        strav_avatar = ziskej_avatar_uzivatele(st.session_state.user_id)
        
        novy_em = st.text_input("Moje Emoji ikona:", value=strav_avatar if not str(strav_avatar).startswith("data:image") else "🧑‍🚒")
        if st.button("Uložit"):
            uloz_avatar_uzivatele(st.session_state.user_id, novy_em)
            st.session_state.user_avatar = novy_em
            st.success("Uloženo.")
            st.rerun()
        
        if st.button("Odhlásit se", type="primary"):
            st.session_state.logged_in = False
            st.rerun()

    # ADMINISTRACE VELITELE
    elif volba == "⚙️ Správa sboru (Velitel)" and je_spravce:
        st.header("Správa sboru")
        
        st.subheader("Členové čekající na schválení")
        try:
            neschvaleni = supabase.table("uzivatele").select("id, jmeno, prijmeni, email, role").eq("sdh_id", st.session_state.sdh_id).eq("schvalen", False).execute().data
        except Exception:
            neschvaleni = []
        
        if neschvaleni:
            for u in neschvaleni:
                st.write(f"👤 {u['jmeno']} {u['prijmeni']} ({u['email']}) - Role: {u['role']}")
                if st.button("Schválit", key=f"schv_{u['id']}"):
                    supabase.table("uzivatele").update({"schvalen": True}).eq("id", u["id"]).execute()
                    st.success("Schválen.")
                    st.rerun()
        else:
            st.info("Žádné nové žádosti.")
            
        st.subheader("Vytvořit novou akci")
        n_nazev = st.text_input("Název akce")
        n_typ = st.selectbox("Typ akce", ["Cvičení", "Schůze", "Soutěž", "Brigáda", "Zásah"])
        n_datum = st.date_input("Datum")
        n_poznamka = st.text_area("Poznámka")
        
        if st.button("Uložit akci"):
            if n_nazev:
                try:
                    supabase.table("akce").insert({
                        "sdh_id": st.session_state.sdh_id,
                        "datum": str(n_datum),
                        "nazev_akce": n_nazev,
                        "typ_akce": n_typ,
                        "poznamka": n_poznamka
                    }).execute()
                    st.success("Akce vytvořena.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Chyba: {e}")

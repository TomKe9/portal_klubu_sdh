import streamlit as st
from supabase import create_client, Client
import datetime
import pandas as pd

# 1. Inicializace a připojení k databázi
st.set_page_config(page_title="Hasiči - Portál", page_icon="🚒", layout="wide")

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase: Client = init_connection()

# Inicializace stavu přihlášení
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.stranka = "🚨 POPLACH"

# CSS pro zvýraznění poplachu a karet
st.markdown("""
<style>
    .poplach-box { background: #ffebee; border-left: 6px solid #e53935; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
    .karta { background: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ROZHRANÍ PRO NEPŘIHLÁŠENÉ (Přihlášení / Registrace)
# ==========================================
if not st.session_state.logged_in:
    st.subheader("🚒 Vstup do Hasičského Portálu")
    tab1, tab2 = st.tabs(["🔒 Přihlášení", "📝 Registrace člena"])
    
    with tab1:
        email = st.text_input("E-mail").strip()
        heslo = st.text_input("Heslo", type="password")
        if st.button("Přihlásit se", type="primary", use_container_width=True):
            res = supabase.table("uzivatele").select("*, sbory(nazev_sdh)").eq("email", email).execute()
            if res.data and res.data[0]["heslo_hash"] == heslo:  # Zjednodušené ověření
                st.session_state.logged_in = True
                st.session_state.user = res.data[0]
                st.rerun()
            else:
                st.error("Nesprávný e-mail nebo heslo.")
                
    with tab2:
        sbory_res = supabase.table("sbory").select("*").execute()
        seznam_sboru = {s["nazev_sdh"]: s["id"] for s in sbory_res.data} if sbory_res.data else {}
        
        if seznam_sboru:
            sbor_nazev = st.selectbox("Vyberte váš sbor (SDH):", list(seznam_sboru.keys()))
            reg_jmeno = st.text_input("Jméno")
            reg_prijmeni = st.text_input("Příjmení")
            reg_email = st.text_input("Registrační E-mail")
            reg_heslo = st.text_input("Zvolte heslo", type="password")
            reg_role = st.selectbox("Pozice ve sboru:", ["Velitel", "Strojník", "Hasič", "Člen"])
            
            if st.button("Zaregistrovat se"):
                if reg_jmeno and reg_prijmeni and reg_email and reg_heslo:
                    supabase.table("uzivatele").insert({
                        "sdh_id": seznam_sboru[sbor_nazev], "jmeno": reg_jmeno, "prijmeni": reg_prijmeni,
                        "email": reg_email, "heslo_hash": reg_heslo, "role": reg_role
                    }).execute()
                    st.success("Registrace hotova! Můžete se přihlásit.")

# ==========================================
# ROZHRANÍ PRO PŘIHLÁŠENÉ HASIČE
# ==========================================
else:
    u = st.session_state.user
    je_velitel = u["role"] in ["Velitel", "Starosta"]

    # Boční panel (Sidebar)
    st.sidebar.markdown(f"### 🧑‍🚒 {u['jmeno']} {u['prijmeni']}")
    st.sidebar.markdown(f"**Sbor:** {u['sbory']['nazev_sdh']} ({u['role']})")
    st.sidebar.markdown("---")
    
    volba = st.sidebar.radio("Menu", ["🚨 POPLACH", "📢 Nástěnka", "🧑‍🚒 Členové"])
    
    if st.sidebar.button("Odhlásit se", type="primary", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    # --- MODUL 1: POPLACH (To nejdůležitější pro JSDH) ---
    if volba == "🚨 POPLACH":
        st.subheader("Výjezdový monitor")
        
        # Velitelský panel pro vyhlášení poplachu
        if je_velitel:
            with st.expander("🚨 VYHLÁSIT NOVÝ POPLACH (Jen velitel)"):
                udalost = st.text_input("Typ události (např. Požár, Technická pomoc)")
                misto = st.text_input("Místo zásahu / Adresa")
                if st.button("ODESLAT POPLACH MEZI HASIČE", type="primary"):
                    supabase.table("poplachy").update({"aktivni": False}).eq("sdh_id", u["sdh_id"]).execute()
                    supabase.table("poplachy").insert({"sdh_id": u["sdh_id"], "udalost": udalost, "misto": misto, "aktivni": True}).execute()
                    st.rerun()

        # Zobrazení aktivního poplachu
        pop_res = supabase.table("poplachy").select("*").eq("sdh_id", u["sdh_id"]).eq("aktivni", True).order("created_at", desc=True).limit(1).execute()
        
        if pop_res.data:
            akt = pop_res.data[0]
            st.markdown(f"""
            <div class="poplach-box">
                <h2 style="color: #c62828; margin: 0;">🔥 POPLACH: {akt['udalost']}</h2>
                <h4 style="color: #333; margin: 5px 0 0 0;">📍 Místo: {akt['misto']}</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # Tlačítka rychlé odezvy
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🟢 JEDU IHNED", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": akt["id"], "uzivatel_id": u["id"], "stav": "Jedu", "cas": "IHNED"}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c2:
                if st.button("🟡 JEDU (do 10 min)", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": akt["id"], "uzivatel_id": u["id"], "stav": "Jedu", "cas": "Do 10 min"}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()
            with c3:
                if st.button("🔴 NEDORAZÍM", use_container_width=True):
                    supabase.table("poplach_reakce").upsert({"poplach_id": akt["id"], "uzivatel_id": u["id"], "stav": "Nedorazím", "cas": "-"}, on_conflict="poplach_id,uzivatel_id").execute()
                    st.rerun()

            # Výpis kdo jede a kdo ne
            st.markdown("### 📋 Kdo dorazí na zbrojnici:")
            reakce = supabase.table("poplach_reakce").select("stav, cas, uzivatele(jmeno, prijmeni)").eq("poplach_id", akt["id"]).execute()
            
            if reakce.data:
                for r in reakce.data:
                    stav_emoji = "🟢" if r["stav"] == "Jedu" else "🔴"
                    st.write(f"{stav_emoji} **{r['uzivatele']['jmeno']} {r['uzivatele']['prijmeni']}** — {r['stav']} ({r['cas']})")
            
            if je_velitel and st.button("❌ Ukončit / Odvolat poplach", type="secondary"):
                supabase.table("poplachy").update({"aktivni": False}).eq("id", akt["id"]).execute()
                st.rerun()
        else:
            st.success("🎉 Žádný aktivní poplach. Jednotka je v klidu.")

    # --- MODUL 2: NÁSTĚNKA (Zprávy a akce) ---
    elif volba == "📢 Nástěnka":
        st.subheader("Sborová nástěnka")
        
        if je_velitel:
            with st.expander("📌 Přidat nové oznámení"):
                nadpis = st.text_input("Nadpis zprávy")
                text = st.text_area("Obsah")
                if st.button("Publikovat"):
                    supabase.table("nastenka").insert({"sdh_id": u["sdh_id"], "autor_jmeno": f"{u['jmeno']} {u['prijmeni']}", "nadpis": nadpis, "text": text}).execute()
                    st.rerun()
                    
        zpravy = supabase.table("nastenka").select("*").eq("sdh_id", u["sdh_id"]).order("created_at", desc=True).execute()
        if zpravy.data:
            for z in zpravy.data:
                st.markdown(f"""
                <div class="karta">
                    <h3 style="margin:0 0 5px 0;">{z['nadpis']}</h3>
                    <p style="margin:0; color:#333;">{z['text']}</p>
                    <small style="color:#888;">Napsal: {z['autor_jmeno']}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Nástěnka je prázdná.")

    # --- MODUL 3: ČLENOVÉ (Kontakty) ---
    elif volba == "🧑‍🚒 Členové":
        st.subheader("Seznam členů sboru")
        cleny = supabase.table("uzivatele").select("jmeno, prijmeni, email, role").eq("sdh_id", u["sdh_id"]).execute()
        if cleny.data:
            df = pd.DataFrame(cleny.data)
            df.columns = ["Jméno", "Příjmení", "E-mail", "Funkce"]
            st.table(df)

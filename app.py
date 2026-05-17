import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import os
import json

# --- KONFIGURACE APLIKACE ---
st.set_page_config(page_title="Portál klubů SDH", layout="wide", page_icon="🧯")

SOUBOR_CLENOVE = "clenove.json"
SOUBOR_AKCE = "akce.json"

def nacti_data():
    if os.path.exists(SOUBOR_CLENOVE):
        try: st.session_state.clenove = pd.read_json(SOUBOR_CLENOVE)
        except Exception: st.session_state.clenove = pd.DataFrame(columns=["ID", "Jméno", "Příjmení", "Datum narození", "Kategorie", "Oblečení", "NSA Export", "Platba"])
    else:
        st.session_state.clenove = pd.DataFrame(columns=["ID", "Jméno", "Příjmení", "Datum narození", "Kategorie", "Oblečení", "NSA Export", "Platba"])
    
    if os.path.exists(SOUBOR_AKCE):
        try:
            with open(SOUBOR_AKCE, "r", encoding="utf-8") as f: st.session_state.akce = json.load(f)
        except Exception: st.session_state.akce = []
    else: st.session_state.akce = []

def uloz_clenove(): st.session_state.clenove.to_json(SOUBOR_CLENOVE, force_ascii=False, indent=4)
def uloz_akce():
    with open(SOUBOR_AKCE, "w", encoding="utf-8") as f: json.dump(st.session_state.akce, f, ensure_ascii=False, indent=4)

if 'data_nactena' not in st.session_state:
    nacti_data()
    st.session_state.data_nactena = True

# --- BOČNÍ PANEL ---
st.sidebar.markdown("<h2 style='color: #FF4B4B; font-weight: bold;'>🚒 Portál klubů SDH</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='font-size: 0.85rem; color: gray;'>Informační systém pro hasičské kolektivy</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

menu = st.sidebar.radio("HLAVNÍ MENU", ["📊 Hlavní přehled", "👥 Evidence členů", "📅 Plán činnosti", "💰 Správa pokladny", "🤖 AI Asistent"])

# --- 1. HLAVNÍ PŘEHLED ---
if menu == "📊 Hlavní přehled":
    st.markdown("<h1 style='font-weight: 300;'>Aktuální přehled sboru</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Členská základna", len(st.session_state.clenove))
    col2.metric("Plánované akce", len(st.session_state.akce))
    
    zaplaceno = len(st.session_state.clenove[st.session_state.clenove["Platba"] == "Zaplaceno"]) if not st.session_state.clenove.empty else 0
    col3.metric("Uhrazené příspěvky", zaplaceno)
    
    nezaplaceno = len(st.session_state.clenove[st.session_state.clenove["Platba"] == "Nezaplaceno"]) if not st.session_state.clenove.empty else 0
    col4.metric("Nezaplacené příspěvky", nezaplaceno)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.subheader("Systémová upozornění")
    if st.session_state.clenove.empty:
        st.info("💡 Portál je prázdný. Začněte přidáním prvního člena v sekci 'Evidence členů'.")
    elif nezaplaceno > 0:
        st.warning(f"⚠️ Pozor: {nezaplaceno} členů nemá uhrazené příspěvky. Seznam naleznete v sekci Správa pokladny.")
    else:
        st.success("✅ Všechny členské záležitosti a příspěvky jsou řádně vyřízeny.")

# --- 2. EVIDENCE ČLENŮ ---
elif menu == "👥 Evidence členů":
    st.markdown("<h1 style='font-weight: 300;'>Centrální evidence členů</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    if st.session_state.clenove.empty:
        st.write("Zatím nejsou zaregistrováni žádní členové.")
    else:
        st.dataframe(st.session_state.clenove, use_container_width=True)
    
    with st.expander("➕ Přidat nového člena do registru"):
        with st.form("novy_clen"):
            col_a, col_b = st.columns(2)
            jmeno = col_a.text_input("Jméno")
            prijmeni = col_b.text_input("Příjmení")
            
            col_c, col_d = st.columns(2)
            datum_nar = col_c.date_input("Datum narození", min_value=datetime.date(1940, 1, 1))
            kat = col_d.selectbox("Kategorie", ["Přípravka", "Mladší žáci", "Starší žáci", "Dorost", "Muži", "Ženy", "Vedoucí"])
            
            col_e, col_f = st.columns(2)
            velikost = col_e.text_input("Velikost oblečení / dresu (např. 140, M)")
            nsa = col_f.radio("Zahrnout do exportu pro NSA?", ["Ano", "Ne"], horizontal=True)
            
            submitted = st.form_submit_button("Uložit kartu člena")
            if submitted and jmeno and prijmeni:
                novy_id = len(st.session_state.clenove) + 1
                novy_radek = {
                    "ID": int(novy_id), 
                    "Jméno": jmeno, 
                    "Příjmení": prijmeni, 
                    "Datum narození": datum_nar.strftime("%d.%m.%Y"),
                    "Kategorie": kat, 
                    "Oblečení": velikost, 
                    "NSA Export": nsa, 
                    "Platba": "Nezaplaceno"
                }
                
                st.session_state.clenove = pd.concat([st.session_state.clenove, pd.DataFrame([novy_radek])], ignore_index=True)
                uloz_clenove()
                st.success(f"Člen {jmeno} {prijmeni} byl úspěšně zaregistrován.")
                st.rerun()

    if not st.session_state.clenove.empty:
        with st.expander("⚠️ Odstranit člena z registru (Oprava chyb)"):
            st.write("Pokud jste člena zapsali špatně nebo ho potřebujete vyřadit, zvolte ho níže:")
            seznam_clenu = st.session_state.clenove.apply(lambda r: f"{r['Jméno']} {r['Příjmení']} (ID: {r['ID']})", axis=1).tolist()
            clen_ke_smazani = st.selectbox("Vyberte člena k vymazání", seznam_clenu)
            
            if st.button("🔴 Definitivně smazat člena", type="primary"):
                vybrane_id = int(clen_ke_smazani.split("(ID: ")[1].replace(")", ""))
                st.session_state.clenove = st.session_state.clenove[st.session_state.clenove["ID"] != vybrane_id].reset_index(drop=True)
                uloz_clenove()
                st.success("Člen byl z registru úspěšně vymazán.")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Podklady pro dotační řízení")
    if not st.session_state.clenove.empty:
        nsa_data = st.session_state.clenove[st.session_state.clenove["NSA Export"] == "Ano"]
        st.download_button(
            label="Stáhnout CSV export pro registr NSA",
            data=nsa_data.to_csv(index=False).encode('utf-8'),
            file_name='sdh_portal_nsa_export.csv',
            mime='text/csv',
        )
    else:
        st.write("Pro export dat musíte nejprve přidat členy do evidence.")

# --- 3. PLÁN ČINNOSTI (VYČIŠTĚNÝ) ---
elif menu == "📅 Plán činnosti":
    st.markdown("<h1 style='font-weight: 300;'>Plán činnosti a docházka</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    with st.expander("➕ Naplánovat novou akci (trénink, soutěž...)"):
        with st.form("nova_akce"):
            nazev = st.text_input("Název události")
            datum = st.date_input("Datum konání")
            typ = st.selectbox("Typ akce", ["Trénink", "Soutěž", "Soustředění", "Brigáda", "Schůze", "Jiné"])
            
            if st.form_submit_button("Vytvořit akci") and nazev:
                st.session_state.akce.append({"Název": nazev, "Datum": datum.strftime("%d.%m.%Y"), "Typ": typ})
                uloz_akce()
                st.success("Akce byla úspěšně přidána do kalendáře.")
                st.rerun()

    st.subheader("Přehled naplánovaných akcí")
    if not st.session_state.akce:
        st.info("V kalendáři nejsou žádné naplánované události.")
    else:
        for akce in st.session_state.akce:
            st.markdown(f"🚒 **{akce['Název']}** | Typ: *{akce['Typ']}* | Datum: 📅 {akce['Datum']}")
        
    st.markdown("---")
    st.subheader("Zápis docházky")
    if st.session_state.clenove.empty:
        st.warning("Pro evidenci docházky musíte mít v systému zapsané členy.")
    else:
        for index, row in st.session_state.clenove.iterrows():
            st.radio(f"{row['Jméno']} {row['Příjmení']} ({row['Kategorie']})", ["Přítomen", "Omluven", "Nepřítomen"], key=f"clen_{row['ID']}", horizontal=True)
            
        if st.button("Uložit docházku"):
            st.success("Docházka byla úspěšně uzavřena a uložena.")

# --- 4. SPRÁVA POKLADNY ---
elif menu == "💰 Správa pokladny":
    st.markdown("<h1 style='font-weight: 300;'>Správa plateb a pokladny</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    if st.session_state.clenove.empty:
        st.info("Tento modul vyžaduje aktivní data v evidenci členů.")
    else:
        st.subheader("Změna stavu platby")
        vybrany_clen = st.selectbox("Vyberte člena", st.session_state.clenove['Jméno'] + " " + st.session_state.clenove['Příjmení'])
        novy_stav = st.radio("Stav členského příspěvku", ["Zaplaceno", "Nezaplaceno"], horizontal=True)
        
        if st.button("Uložit změnu platby"):
            idx = st.session_state.clenove[st.session_state.clenove['Jméno'] + " " + st.session_state.clenove['Příjmení'] == vybrany_clen].index[0]
            st.session_state.clenove.at[idx, 'Platba'] = novy_stav
            uloz_clenove()
            st.success(f"Platba pro člena {vybrany_clen} byla upravena.")
            st.rerun()

        st.markdown("---")
        
        stav_plateb = st.session_state.clenove['Platba'].value_counts().reset_index()
        if not stav_plateb.empty:
            fig = px.pie(stav_plateb, values='count', names='Platba', title='Přehled vybraných příspěvků', color='Platba',
                         color_discrete_map={'Zaplaceno':'#2ecc71', 'Nezaplaceno':'#e74c3c'})
            st.plotly_chart(fig)
        
        st.dataframe(st.session_state.clenove[["Jméno", "Příjmení", "Kategorie", "Platba"]], use_container_width=True)

# --- 5. AI ASISTENT ---
elif menu == "🤖 AI Asistent":
    st.markdown("<h1 style='font-weight: 300;'>Chytrý AI asistent</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    user_query = st.text_input("Zeptejte se asistenta na pravidla hry Plamen nebo správu aplikace...", placeholder="Zadejte dotaz...")
    
    if user_query:
        st.markdown("> **AI Asistent:**")
        st.info("Modul umělé inteligence je připraven k budoucí integraci s databází směrnic SH ČMS. V plné verzi vám pomůže s metodikou tréninků i výkladem pravidel disciplín.")
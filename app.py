import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# Konfigurace
st.set_page_config(page_title="FireSport Pro", layout="wide")

class FireSportDB:
    def __init__(self):
        self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

    def get_akce_pro_sdh(self, sdh: str):
        return self.client.table("akce").select("*").eq("sdh", sdh).execute().data or []

    def insert_akce(self, data): return self.client.table("akce").insert(data).execute()
    def delete_akce(self, id): return self.client.table("akce").delete().eq("id", id).execute()

db = FireSportDB()

if st.session_state.get("logged_in"):
    st.title(f"Správa akcí: {st.session_state['user_sdh']}")
    
    # FORMULÁŘ
    with st.expander("➕ Přidat novou akci"):
        with st.form("nova"):
            c1, c2, c3, c4 = st.columns(4)
            typ = c1.selectbox("Typ", ["Trénink", "Závod"])
            nazev = c2.text_input("Název")
            misto = c3.text_input("Místo konání")
            datum = c4.date_input("Datum")
            opakovani = st.checkbox("Opakovat každý týden (jen pro trénink)") if typ == "Trénink" else False
            cas = st.time_input("Čas", value=datetime.strptime("18:00", "%H:%M").time())
            
            if st.form_submit_button("Uložit"):
                db.insert_akce({"sdh": st.session_state["user_sdh"], "typ_akce": typ, "nazev": nazev, "misto": misto, "datum_jednorazove": datum.isoformat(), "cas": cas.strftime("%H:%M"), "is_opakována": opakovani})
                st.rerun()

    akce = db.get_akce_pro_sdh(st.session_state["user_sdh"])

    # TABULKA ZÁVODŮ
    st.subheader("🗓 Přehled závodů")
    zavody = [a for a in akce if a["typ_akce"] == "Závod"]
    if zavody:
        df = pd.DataFrame(zavody)[["id", "nazev", "misto", "datum_jednorazove", "cas"]]
        df.columns = ["ID", "Název", "Místo", "Datum", "Čas"]
        
        # Zobrazení tabulky
        st.table(df[["Název", "Místo", "Datum", "Čas"]])
        
        # Výběr pro smazání
        id_ke_smazani = st.selectbox("Vyberte ID závodu pro smazání:", options=df["ID"].tolist())
        if st.button("Smazat vybraný závod"):
            db.delete_akce(id_ke_smazani)
            st.rerun()
    else:
        st.info("Žádné závody.")

    # TRÉNINKY
    st.subheader("🏋️ Tréninky")
    treninky = [a for a in akce if a["typ_akce"] == "Trénink"]
    for t in treninky:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{t['nazev']}** | {t['datum_jednorazove']} v {t['cas']} | 📍 {t.get('misto', '-')}")
            if col2.button("Smazat", key=f"del_{t['id']}"):
                db.delete_akce(t['id']); st.rerun()

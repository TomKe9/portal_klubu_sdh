import streamlit as st
import bcrypt
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
import extra_streamlit_components as stx

# Konfigurace stránky
st.set_page_config(page_title="FireSport Pro | Informační systém", layout="wide")

# ==============================================================================
# DATOVÁ VRSTVA
# ==============================================================================
class FireSportDB:
    def __init__(self):
        self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

    def get_akce_pro_sdh(self, sdh: str):
        return self.client.table("akce").select("*").eq("sdh", sdh).execute().data or []

    def insert_akce(self, data): return self.client.table("akce").insert(data).execute()
    def delete_akce(self, id): return self.client.table("akce").delete().eq("id", id).execute()
    def uloz_dochazku(self, akce_id, uzivatel_id, status): 
        return self.client.table("dochazka").upsert({"akce_id": akce_id, "uzivatel_id": uzivatel_id, "status": status}, on_conflict="akce_id,uzivatel_id").execute()

# ==============================================================================
# HLAVNÍ APLIKACE
# ==============================================================================
db = FireSportDB()
if "logged_in" not in st.session_state: st.session_state.update({"logged_in": False})

if st.session_state.get("logged_in"):
    st.title(f"Správa akcí: {st.session_state['user_sdh']}")
    
    # FORMULÁŘ
    with st.expander("➕ Přidat novou akci", expanded=True):
        with st.form("nova"):
            c1, c2, c3 = st.columns(3)
            typ = c1.selectbox("Typ", ["Trénink", "Závod"])
            nazev = c2.text_input("Název")
            datum = c3.date_input("Datum")
            
            opakovani = False
            if typ == "Trénink":
                opakovani = st.checkbox("Opakovat každý týden")
            
            cas = st.time_input("Čas", value=datetime.strptime("18:00", "%H:%M").time())
            
            if st.form_submit_button("Uložit akci"):
                db.insert_akce({
                    "sdh": st.session_state["user_sdh"], "typ_akce": typ, "nazev": nazev, 
                    "datum_jednorazove": datum.isoformat(), "cas": cas.strftime("%H:%M"),
                    "is_opakována": opakovani
                })
                st.rerun()

    # ZÁVODY V TABULCE
    st.subheader("🗓 Přehled závodů")
    akce = db.get_akce_pro_sdh(st.session_state["user_sdh"])
    zavody = [a for a in akce if a["typ_akce"] == "Závod"]
    
    if zavody:
        df_zavody = pd.DataFrame(zavody)[["nazev", "datum_jednorazove", "cas"]]
        df_zavody.columns = ["Název závodu", "Datum", "Čas"]
        st.table(df_zavody)
    else:
        st.info("Žádné závody nejsou naplánovány.")

    # TRÉNINKY
    st.subheader("🏋️ Tréninky")
    treninky = [a for a in akce if a["typ_akce"] == "Trénink"]
    for t in treninky:
        opakovani_text = "(Každý týden)" if t.get("is_opakována") else ""
        with st.container(border=True):
            st.write(f"**{t['nazev']}** - {t['datum_jednorazove']} v {t['cas']} {opakovani_text}")
            if st.button("Smazat trénink", key=f"del_{t['id']}"): db.delete_akce(t['id']); st.rerun()

else:
    st.write("Prosím přihlaste se.")

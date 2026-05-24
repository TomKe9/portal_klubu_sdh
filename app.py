import streamlit as st
import bcrypt
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(page_title="FireSport Pro | Správa", layout="wide")

class FireSportDB:
    def __init__(self):
        self.client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

    def get_user_by_login(self, login: str):
        res = self.client.table("uzivatele").select("*").or_(f"email.ilike.{login.strip().lower()},prezdivka.ilike.{login.strip().lower()}").execute()
        return res.data[0] if res.data else None

    def get_akce_pro_sdh(self, sdh: str):
        data = self.client.table("akce").select("*").eq("sdh", sdh).execute().data or []
        if data:
            df = pd.DataFrame(data)
            # Zajištění, aby sloupce existovaly v paměti, pokud v DB chybí
            for col in ['cas_levy', 'cas_pravy', 'umisteni']:
                if col not in df.columns: df[col] = ""
            
            df['dt'] = pd.to_datetime(df['datum_jednorazove'] + ' ' + df['cas'])
            return df.sort_values('dt').drop(columns=['dt']).to_dict('records')
        return []

    def insert_akce(self, data): return self.client.table("akce").insert(data).execute()
    def update_akce(self, id, data): return self.client.table("akce").update(data).eq("id", id).execute()
    def delete_akce(self, id): return self.client.table("akce").delete().eq("id", id).execute()

db = FireSportDB()
if "logged_in" not in st.session_state: st.session_state.update({"logged_in": False})

# --- PŘIHLAŠOVÁNÍ ---
if not st.session_state["logged_in"]:
    st.title("🔐 Přihlášení")
    with st.form("login"):
        u = st.text_input("Login")
        p = st.text_input("Heslo", type="password")
        if st.form_submit_button("Přihlásit"):
            user = db.get_user_by_login(u)
            if user and bcrypt.checkpw(p.encode(), user["heslo_hash"].encode()):
                st.session_state.update({"logged_in": True, "user_sdh": user.get("sdh", "")})
                st.rerun()
else:
    # --- HLAVNÍ APLIKACE ---
    st.sidebar.button("Odhlásit se", on_click=lambda: st.session_state.clear())
    st.title(f"Správa: {st.session_state['user_sdh']}")

    # Formulář pro přidání
    with st.expander("➕ Přidat novou akci"):
        with st.form("nova_akce"):
            c1, c2, c3 = st.columns(3)
            typ = c1.selectbox("Typ", ["Trénink", "Závod"])
            nazev = c2.text_input("Název")
            misto = c3.text_input("Místo")
            datum = st.date_input("Datum")
            cas = st.time_input("Čas")
            if st.form_submit_button("Uložit"):
                db.insert_akce({"sdh": st.session_state["user_sdh"], "typ_akce": typ, "nazev": nazev, 
                                "misto": misto, "datum_jednorazove": datum.isoformat(), 
                                "cas": cas.strftime("%H:%M"), "cas_levy": "", "cas_pravy": "", "umisteni": ""})
                st.rerun()

    # Tabulka pro editaci
    akce_list = db.get_akce_pro_sdh(st.session_state["user_sdh"])
    zavody = [a for a in akce_list if a["typ_akce"] == "Závod"]
    
    if zavody:
        df = pd.DataFrame(zavody)
        df_edit = df[['id', 'nazev', 'misto', 'datum_jednorazove', 'cas_levy', 'cas_pravy', 'umisteni']]
        df_edit.columns = ["ID", "Název", "Místo", "Datum", "Čas Levý", "Čas Pravý", "Umístění"]
        
        edited_df = st.data_editor(df_edit, hide_index=True, column_config={"ID": None})
        
        if st.button("Uložit výsledky (časy/NP)"):
            for _, row in edited_df.iterrows():
                db.update_akce(row["ID"], {
                    "cas_levy": str(row["Čas Levý"]), 
                    "cas_pravy": str(row["Čas Pravý"]), 
                    "umisteni": str(row["Umístění"])
                })
            st.success("Uloženo!")
            st.rerun()
    else:
        st.info("Žádné závody k zobrazení.")

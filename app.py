import streamlit as st
import bcrypt
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# Nastavení stránky
st.set_page_config(page_title="FireSport Pro | Správa", layout="wide")

# ==============================================================================
# DATOVÁ VRSTVA
# ==============================================================================
class FireSportDB:
    def __init__(self):
        self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

    def get_user_by_login(self, login: str):
        res = self.client.table("uzivatele").select("*").or_(f"email.ilike.{login.strip().lower()},prezdivka.ilike.{login.strip().lower()}").execute()
        return res.data[0] if res.data else None

    def get_akce_pro_sdh(self, sdh: str):
        data = self.client.table("akce").select("*").eq("sdh", sdh).execute().data or []
        if data:
            df = pd.DataFrame(data)
            # Zajištění existence sloupců v paměti (pro zobrazení)
            for col in ['cas_levy', 'cas_pravy', 'umisteni']:
                if col not in df.columns: df[col] = ""
            df['dt'] = pd.to_datetime(df['datum_jednorazove'] + ' ' + df['cas'])
            return df.sort_values('dt').drop(columns=['dt']).to_dict('records')
        return []

    def insert_akce(self, data): return self.client.table("akce").insert(data).execute()
    
    def update_akce_vysledky(self, id, data):
        # Diagnostický blok: Pokud se zápis nepovede, vypíše chybu
        try:
            return self.client.table("akce").update(data).eq("id", id).execute()
        except Exception as e:
            st.error(f"Databáze odmítla zápis: {e}. Zkontroluj Policies v Supabase (Authentication -> Policies)!")
            return None

    def delete_akce(self, id): return self.client.table("akce").delete().eq("id", id).execute()

db = FireSportDB()
if "logged_in" not in st.session_state: st.session_state.update({"logged_in": False})

# ==============================================================================
# APLIKACE
# ==============================================================================
if not st.session_state["logged_in"]:
    st.title("🔐 Přihlášení do FireSport Pro")
    with st.form("login"):
        u = st.text_input("Přezdívka / E-mail")
        p = st.text_input("Heslo", type="password")
        if st.form_submit_button("Přihlásit"):
            user = db.get_user_by_login(u)
            if user and bcrypt.checkpw(p.encode(), user["heslo_hash"].encode()):
                st.session_state.update({"logged_in": True, "user_id": user["id"], "user_sdh": user.get("sdh", "")})
                st.rerun()
else:
    st.sidebar.title(f"Sbor: {st.session_state['user_sdh']}")
    if st.sidebar.button("Odhlásit se"): st.session_state.clear(); st.rerun()

    # FORMULÁŘ PRO NOVOU AKCI
    with st.expander("➕ Přidat novou akci"):
        with st.form("nova_akce"):
            c1, c2, c3 = st.columns(3)
            typ = c1.selectbox("Typ", ["Trénink", "Závod"])
            nazev = c2.text_input("Název")
            misto = c3.text_input("Místo konání")
            datum = st.date_input("Datum")
            cas = st.time_input("Čas")
            opak = st.checkbox("Opakovat každý týden (jen trénink)") if typ == "Trénink" else False
            if st.form_submit_button("Uložit"):
                db.insert_akce({
                    "sdh": st.session_state["user_sdh"], "typ_akce": typ, "nazev": nazev, 
                    "misto": misto, "datum_jednorazove": datum.isoformat(), 
                    "cas": cas.strftime("%H:%M"), "is_opakována": opak,
                    "cas_levy": "", "cas_pravy": "", "umisteni": "" 
                })
                st.rerun()

    akce_list = db.get_akce_pro_sdh(st.session_state["user_sdh"])

    # TABULKA ZÁVODŮ
    st.subheader("🗓 Přehled závodů a výsledky")
    zavody = [a for a in akce_list if a["typ_akce"] == "Závod"]
    if zavody:
        df = pd.DataFrame(zavody)
        df_edit = df[['id', 'nazev', 'misto', 'datum_jednorazove', 'cas_levy', 'cas_pravy', 'umisteni']]
        df_edit.columns = ["ID", "Název", "Místo", "Datum", "Čas Levý", "Čas Pravý", "Umístění"]
        
        edited_df = st.data_editor(df_edit, hide_index=True, column_config={"ID": None})
        
        if st.button("Uložit změny v závodech"):
            for _, row in edited_df.iterrows():
                db.update_akce_vysledky(row["ID"], {
                    "cas_levy": str(row["Čas Levý"]), 
                    "cas_pravy": str(row["Čas Pravý"]), 
                    "umisteni": str(row["Umístění"])
                })
            st.success("Změny uloženy!")
            st.rerun()
            
        vyber_smazat = st.selectbox("Vyberte závod ke smazání:", options=df["id"].tolist(), format_func=lambda x: df[df["id"]==x]["nazev"].values[0])
        if st.button("Smazat vybraný závod"):
            db.delete_akce(vyber_smazat); st.rerun()
    else:
        st.info("Žádné závody nejsou naplánovány.")

    # TRÉNINKY
    st.subheader("🏋️ Tréninky")
    for t in [a for a in akce_list if a["typ_akce"] == "Trénink"]:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            op = "(Každý týden)" if t.get("is_opakována") else ""
            c1.write(f"**{t['nazev']}** | {t['datum_jednorazove']} v {t['cas']} | 📍 {t.get('misto', '-')} {op}")
            if c2.button("Smazat", key=f"t_{t['id']}"): db.delete_akce(t['id']); st.rerun()

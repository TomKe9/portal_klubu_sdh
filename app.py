import streamlit as st
import bcrypt
import pandas as pd
from datetime import datetime
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

    def get_user_by_login(self, login: str):
        res = self.client.table("uzivatele").select("*").or_(f"email.ilike.{login.strip().lower()},prezdivka.ilike.{login.strip().lower()}").execute()
        return res.data[0] if res.data else None

    def get_akce_pro_sdh(self, sdh: str):
        return self.client.table("akce").select("*").eq("sdh", sdh).execute().data or []

    def insert_akce(self, data): return self.client.table("akce").insert(data).execute()
    def delete_akce(self, id): return self.client.table("akce").delete().eq("id", id).execute()
    def update_user_sdh(self, id, sdh): return self.client.table("uzivatele").update({"sdh": sdh}).eq("id", id).execute()

db = FireSportDB()
cookie_manager = stx.CookieManager()

# Inicializace session
if "logged_in" not in st.session_state: st.session_state.update({"logged_in": False})

# --- PŘIHLAŠOVACÍ OBRAZOVKA ---
if not st.session_state["logged_in"]:
    st.title("🔐 Přihlášení do FireSport Pro")
    with st.form("login_form"):
        user_input = st.text_input("E-mail nebo přezdívka")
        pass_input = st.text_input("Heslo", type="password")
        if st.form_submit_button("Přihlásit"):
            user = db.get_user_by_login(user_input)
            if user and bcrypt.checkpw(pass_input.encode(), user["heslo_hash"].encode()):
                st.session_state.update({"logged_in": True, "user_id": user["id"], "user_name": f"{user['jmeno']} {user['prijmeni']}", "user_sdh": user.get("sdh", "")})
                st.rerun()
            else:
                st.error("Neplatné údaje.")

# --- HLAVNÍ APLIKACE ---
else:
    st.title(f"Správa akcí: {st.session_state['user_sdh']}")
    if st.sidebar.button("Odhlásit se"):
        st.session_state.clear()
        st.rerun()

    # FORMULÁŘ PRO PŘIDÁNÍ AKCE
    with st.expander("➕ Přidat novou akci"):
        with st.form("nova_akce"):
            c1, c2, c3, c4 = st.columns(4)
            typ = c1.selectbox("Typ", ["Trénink", "Závod"])
            nazev = c2.text_input("Název")
            misto = c3.text_input("Místo konání")
            datum = c4.date_input("Datum")
            opakovani = st.checkbox("Opakovat každý týden (jen trénink)") if typ == "Trénink" else False
            cas = st.time_input("Čas", value=datetime.strptime("18:00", "%H:%M").time())
            
            if st.form_submit_button("Uložit akci"):
                db.insert_akce({
                    "sdh": st.session_state["user_sdh"], "typ_akce": typ, "nazev": nazev, 
                    "misto": misto, "datum_jednorazove": datum.isoformat(), 
                    "cas": cas.strftime("%H:%M"), "is_opakována": opakovani
                })
                st.rerun()

    akce = db.get_akce_pro_sdh(st.session_state["user_sdh"])

    # TABULKA ZÁVODŮ
    st.subheader("🗓 Přehled závodů")
    zavody = [a for a in akce if a["typ_akce"] == "Závod"]
    if zavody:
        df = pd.DataFrame(zavody)[["id", "nazev", "misto", "datum_jednorazove", "cas"]]
        df.columns = ["ID", "Název", "Místo", "Datum", "Čas"]
        st.table(df[["Název", "Místo", "Datum", "Čas"]])
        
        # Mazání závodů
        id_smazat = st.selectbox("Vyberte ID závodu pro smazání:", options=df["ID"].tolist(), key="del_zav")
        if st.button("Smazat vybraný závod"):
            db.delete_akce(id_smazat)
            st.rerun()
    else:
        st.info("Žádné závody nejsou naplánovány.")

    # TRÉNINKY
    st.subheader("🏋️ Tréninky")
    treninky = [a for a in akce if a["typ_akce"] == "Trénink"]
    for t in treninky:
        op_text = "(Každý týden)" if t.get("is_opakována") else ""
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{t['nazev']}** | {t['datum_jednorazove']} v {t['cas']} | 📍 {t.get('misto', '-')} {op_text}")
            if c2.button("Smazat", key=f"del_{t['id']}"):
                db.delete_akce(t['id'])
                st.rerun()

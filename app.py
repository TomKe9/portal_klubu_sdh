import streamlit as st
import bcrypt
import time
from typing import Dict, Any, Optional
from supabase import create_client, Client
import extra_streamlit_components as stx

# Nastavení konfigurace stránky
st.set_page_config(page_title="🔥 FireSport Pro | Login Test", page_icon="⚡")

# ==============================================================================
# DATOVÁ VRSTVA (POUZE UŽIVATELÉ)
# ==============================================================================
class FireSportDB:
    def __init__(self):
        try:
            self.client: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except Exception as e:
            st.error(f"🔴 Chyba inicializace Supabase (Zkontroluj st.secrets): {e}")
            st.stop()

    def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        try:
            clean_login = login.strip().lower()
            if not clean_login:
                return None
                
            # Vyhledáme uživatele buď podle e-mailu nebo podle přezdívky (case-insensitive)
            res = self.client.table("uzivatele")\
                .select("*")\
                .or_(f"email.ilike.{clean_login},prezdivka.ilike.{clean_login}")\
                .execute()
            return res.data[0] if res.data else None
        except Exception as e:
            st.error(f"❌ Chyba při hledání uživatele v DB: {e}")
            return None

    def register_user(self, u_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            res = self.client.table("uzivatele").insert(u_data).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            st.error(f"❌ Zápis uživatele do databáze selhal: {e}")
            return None

# ==============================================================================
# APLIKAČNÍ LOGIKA & AUTOMATICKÉ PŘIHLÁŠENÍ
# ==============================================================================
db = FireSportDB()
cookie_manager = stx.CookieManager()

# Inicializace stavu aplikace (Session State)
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_name" not in st.session_state:
    st.session_state["user_name"] = ""

# --- KONTROLA COOKIES PRO AUTOMATICKÉ PŘIHLÁŠENÍ ---
if not st.session_state["logged_in"]:
    saved_login = cookie_manager.get(cookie="firesport_login_remember")
    if saved_login:
        user = db.get_user_by_login(saved_login)
        if user:
            st.session_state["logged_in"] = True
            st.session_state["user_name"] = f"{user['jmeno']} {user['prijmeni']}"
            st.rerun()

# --- OBRAZOVKA PO PŘIHLÁŠENÍ ---
if st.session_state["logged_in"]:
    st.title(f"🎉 Úspěšně přihlášen: {st.session_state['user_name']}")
    st.success("Skvělé! Autentizace i pamatování uživatele funguje.")
    st.info("Pamatování tě udrží přihlášeného po dobu 30 dnů, nebo dokud neklikneš na tlačítko níže.")
    
    if st.button("Odhlásit se a smazat paměť"):
        # Smažeme cookie z prohlížeče
        cookie_manager.delete("firesport_login_remember")
        # Vyčistíme stav aplikace
        st.session_state["logged_in"] = False
        st.session_state["user_name"] = ""
        st.rerun()

# --- AUTENTIZAČNÍ OBRAZOVKA (PŘIHLÁŠENÍ / REGISTRACE) ---
else:
    st.title("🔥 FireSport Pro — Ověření spojení")
    
    tab_login, tab_reg = st.tabs(["🔒 Přihlášení", "📝 Registrace nového účtu"])
    
    with tab_login:
        with st.form("login_form"):
            login_input = st.text_input("E-mail nebo Přezdívka").strip()
            heslo_input = st.text_input("Heslo", type="password")
            remember_me = st.checkbox("Zůstat přihlášený (na 30 dní)", value=True)
            submit_login = st.form_submit_button("Přihlásit se", type="primary")
            
        if submit_login:
            if not login_input or not heslo_input:
                st.warning("⚠️ Vyplňte obě pole.")
            else:
                user = db.get_user_by_login(login_input)
                if user:
                    # Ověření hesla pomocí bcrypt
                    if bcrypt.checkpw(heslo_input.encode('utf-8'), user["heslo_hash"].encode('utf-8')):
                        st.session_state["logged_in"] = True
                        st.session_state["user_name"] = f"{user['jmeno']} {user['prijmeni']}"
                        
                        # Pokud je zaškrtnuto "Zůstat přihlášený", uložíme login do cookies na 30 dní (v sekundách)
                        if remember_me:
                            cookie_manager.set("firesport_login_remember", login_input, max_age=2592000)
                        
                        st.success("Ověření úspěšné, načítám...")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Nesprávné heslo.")
                else:
                    st.error("❌ Účet s tímto e-mailem nebo přezdívkou neexistuje.")

    with tab_reg:
        st.subheader("Vytvořit nový testovací účet")
        with st.form("reg_form"):
            reg_jmeno = st.text_input("Jméno").strip()
            reg_prijmeni = st.text_input("Příjmení").strip()
            reg_prezdivka = st.text_input("Přezdívka (volitelné)").strip().lower()
            reg_email = st.text_input("E-mail (bude sloužit jako login)").strip().lower()
            reg_heslo = st.text_input("Heslo", type="password")
            submit_reg = st.form_submit_button("Zaregistrovat se")
            
        if submit_reg:
            if not reg_jmeno or not reg_prijmeni or not reg_email or not reg_heslo:
                st.warning("⚠️ Vyplňte všechna povinná pole (Jméno, Příjmení, E-mail, Heslo).")
            else:
                # Zahashování hesla
                hashed = bcrypt.hashpw(reg_heslo.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                payload = {
                    "jmeno": reg_jmeno,
                    "prijmeni": reg_prijmeni,
                    "email": reg_email,
                    "prezdivka": reg_prezdivka if reg_prezdivka else None,
                    "heslo_hash": hashed
                }
                
                novy_uzivatel = db.register_user(payload)
                if novy_uzivatel:
                    st.success("🎉 Registrace proběhla úspěšně! Nyní se přepni na záložku Přihlášení.")

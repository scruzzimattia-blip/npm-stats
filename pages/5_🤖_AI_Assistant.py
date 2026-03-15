import streamlit as st
from src.ui_utils import init_page, render_common_sidebar
from src.utils.ai_assistant import AIAssistant
from src.config import app_config

def main():
    init_page("KI Assistent", "🤖")
    st.title("🤖 NPM KI Assistent")
    st.markdown("""
    Willkommen beim interaktiven Sicherheits-Assistenten. Du kannst Fragen zu deinem Traffic, 
    Sperrlisten oder verdächtigen Aktivitäten stellen.
    """)
    
    # Check for API Key
    if not app_config.openrouter_api_key:
        st.warning("⚠️ OpenRouter API Key ist nicht konfiguriert. Bitte in den Einstellungen hinterlegen.")
        st.stop()

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Pre-defined prompt trigger
    if "auto_prompt" in st.session_state and st.session_state.auto_prompt:
        prompt = st.session_state.auto_prompt
        del st.session_state.auto_prompt
        
        # Add to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Trigger processing loop by displaying and then getting response
        # (This is handled by the regular chat logic below since prompt is now set)
    else:
        prompt = st.chat_input("Frage den Assistenten...")

    # Sidebar actions
    with st.sidebar:
        st.divider()
        st.subheader("⚡ KI Schnell-Aktionen")
        
        if st.button("📊 Letzte 24h analysieren", use_container_width=True):
            st.session_state.auto_prompt = "Führe eine detaillierte Sicherheitsanalyse des Traffics der letzten 24 Stunden durch. Identifiziere die Top 3 Bedrohungen."
            st.rerun()
            
        if st.button("📄 Abuse Report erstellen", use_container_width=True):
            st.session_state.auto_prompt = "Erstelle einen formellen Abuse-Report Entwurf für die aggressivste IP der letzten Stunde, inklusive technischer Details für den Provider."
            st.rerun()
            
        if st.button("🛡️ Firewall-Check", use_container_width=True):
            st.session_state.auto_prompt = "Prüfe meine aktuellen Sperrlisten und Schwellwerte. Gibt es Optimierungspotenzial basierend auf den heutigen Angriffsmustern?"
            st.rerun()

        st.divider()
        if st.button("🗑️ Chat-Verlauf löschen", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat logic
    if prompt:
        # Display user message (if not already displayed by history loop)
        # Note: Streamlit chat input doesn't clear until rerun, so we need careful logic
        # but since we append to messages and rerun, it works.
        if not st.session_state.messages or st.session_state.messages[-1]["content"] != prompt:
            with st.chat_message("user"):
                st.markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("KI denkt nach..."):
                assistant = AIAssistant()
                response = assistant.ask(prompt, st.session_state.messages[:-1])
                st.markdown(response)
        
        # Add to history
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

if __name__ == "__main__":
    main()

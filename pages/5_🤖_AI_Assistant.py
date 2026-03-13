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

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Frage den Assistenten..."):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Add to history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("KI denkt nach..."):
                assistant = AIAssistant()
                response = assistant.ask(prompt, st.session_state.messages[:-1])
                st.markdown(response)
        
        # Add to history
        st.session_state.messages.append({"role": "assistant", "content": response})

    # Sidebar actions
    with st.sidebar:
        st.divider()
        if st.button("🗑️ Chat-Verlauf löschen", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        
        st.subheader("💡 Beispiel-Fragen")
        examples = [
            "Gibt es heute auffällige Scan-Muster?",
            "Wer ist die aggressivste IP der letzten Stunde?",
            "Warum wurde die letzte IP gesperrt?",
            "Zusammenfassung der Bedrohungslage heute."
        ]
        for ex in examples:
            if st.button(ex, use_container_width=True):
                # Trigger chat via state would be nice, but for now just info
                st.info(f"Kopiere dies in den Chat: '{ex}'")

if __name__ == "__main__":
    main()

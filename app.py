import streamlit as st
from cmugpt_assistant import CMUGPTAssistant


st.title("CMUGPT Chat Assistant")



# Initialize CMUGPTAssistant in session state
if 'assistant' not in st.session_state:
    st.session_state['assistant'] = CMUGPTAssistant()
    st.session_state['messages'] = []
    st.session_state['functions_called'] = []



# Display the conversation
for message in st.session_state['messages']:
    if message['role'] == 'user':
        with st.chat_message('user'):
            st.write(message['content'])
    elif message['role'] == 'assistant':
        with st.chat_message('assistant'):
            st.write(message['content'])

# Chat input
prompt = st.chat_input("Ask me anything about Carnegie Mellon University")

if prompt:
    # Add user's message to session state
    st.session_state['messages'].append({"role": "user", "content": prompt})

    # Display user's message
    with st.chat_message('user'):
        st.write(prompt)

    # Process user input
    assistant_response = st.session_state['assistant'].process_user_input(prompt)

    # Add assistant's message to session state
    st.session_state['messages'].append({"role": "assistant", "content": assistant_response})

    # Display assistant's message
    with st.chat_message('assistant'):
        st.write(assistant_response)

    # Get functions called
    functions_called = st.session_state['assistant'].get_functions_called()

    # Update functions_called in session state
    st.session_state['functions_called'] = functions_called
    st.rerun()

if st.session_state['assistant'].show_eats:
    st.write("CMU EATS")
    st.components.v1.iframe("https://cmueats.com", height=700, scrolling=True)
    st.components.v1.iframe("https://cmucourses.com", height=700, scrolling=True)
    if st.button("Close", type="primary"):
        st.session_state['assistant'].show_eats = False
        st.rerun()

# Display functions called in the sidebar
st.sidebar.title("Functions Called")
for func in st.session_state['functions_called']:
    st.sidebar.subheader(f"Function: {func['function_name']}")
    st.sidebar.write(f"**Arguments:** {func['arguments']}")
    st.sidebar.write(f"**Result:** {func['result']}")
    st.sidebar.write("---")

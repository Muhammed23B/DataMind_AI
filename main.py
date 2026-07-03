import streamlit as st
from langchain_helper import get_few_shot_db_chain

st.title("AtliQ T Shirts: Database Q&A 👕")

question = st.text_input("Question: ")

if question:
    response = get_few_shot_db_chain(question)

    st.markdown(
        """
        <h2 style='text-align: center;'>Answer</h2>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <h1 style='text-align: center; font-size: 55px; font-weight: bold;'>
            {response}
        </h1>
        """,
        unsafe_allow_html=True
    )


import streamlit as st
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def new():
    st.title("MotionLearn")
    st.divider()

    if st.button("Get Started"):
        st.switch_page("pages/Upload.py")


if __name__ == "__main__":
    asyncio.run(new())
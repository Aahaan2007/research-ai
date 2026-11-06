import streamlit as st
import streamlit.components.v1 as components

import research_agent as ra

st.set_page_config(page_title="Speech Research Agent", page_icon="🎤", layout="centered")
st.title("🎤 Speech Research Agent")
st.caption("Type a topic. Get a cited research doc and a speech draft in your voice.")

topic = st.text_input("Topic", placeholder="e.g. money laundering loopholes in banking")
angle = st.text_input("Angle or stance (optional)", placeholder="e.g. emerging economies")

col1, col2 = st.columns(2)
audience = col1.text_input("Greeting audience", value="Delegates and the EB")
model = col2.selectbox("Model", ["llama3.2:3b", "qwen3:4b"])

tone = st.radio(
    "Tone",
    ["serious", "light"],
    horizontal=True,
    help="Light allows one pun. Serious allows none.",
)

if st.button("Research", type="primary", disabled=not topic.strip()):
    ra.MODEL = model
    status = st.status("Working. This takes a few minutes.", expanded=True)

    try:
        path, link, doc = ra.run(topic.strip(), angle.strip(), audience.strip(), tone, log=status.write)
    except Exception as e:
        status.update(label="Something went wrong", state="error")
        st.error(f"{type(e).__name__}: {e}")
        st.stop()

    if doc is None:
        status.update(label="Not enough sources found", state="error")
        st.warning("Try a broader topic, or run it again.")
    else:
        status.update(label="Done", state="complete", expanded=False)
        if link:
            st.link_button("Open Google Doc", link, type="primary")
        else:
            st.info(f"No Google Doc made (no credentials.json). Local copy saved at {path}")
        st.subheader("Preview")
        # The preview frame is transparent, so give it its own light page.
        # (Only for the preview; the Google Doc upload is unaffected.)
        preview = doc.replace(
            "<body>",
            '<body style="background:#ffffff;color:#1a1a1a;font-family:Georgia,serif;'
            'line-height:1.55;padding:20px 28px;">',
            1,
        )
        components.html(preview, height=700, scrolling=True)
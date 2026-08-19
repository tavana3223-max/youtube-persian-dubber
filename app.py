import streamlit as st
import time
import asyncio
import html
import re
import os
import base64
from youtube_transcript_api import YouTubeTranscriptApi
from deep_translator import GoogleTranslator
import edge_tts

# تنظیمات اولیه صفحه
st.set_page_config(page_title="دوبله و دانلود MP3 ویدیوهای یوتیوب", layout="wide")
st.title("🎙️ سیستم دوبله صوتی هوشمند به فارسی")

video_url = st.text_input("🔗 لینک ویدیو یوتیوب را وارد کنید:", placeholder="https://www.youtube.com/watch?v=...")

# مدیریت وضعیت‌های برنامه (Session State)
if "is_playing" not in st.session_state:
    st.session_state.is_playing = False
if "current_index" not in st.session_state:
    st.session_state.current_index = 0

def extract_youtube_id(url):
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return None

def clean_text(text):
    text = html.unescape(text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    return text.strip()

def translate_to_persian(text):
    if not text:
        return ""
    try:
        return GoogleTranslator(source='auto', target='fa').translate(text)
    except Exception:
        return text

async def generate_single_audio(text, output_path):
    if not text:
        return False
    try:
        communicate = edge_tts.Communicate(text, "fa-IR-FaridNeural")
        await communicate.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False

def play_audio_base64(file_path):
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        with open(file_path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            md = f"""
                <audio autoplay="true" style="width: 100%;">
                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                </audio>
                """
            st.markdown(md, unsafe_allow_html=True)

def merge_audio_files_raw(audio_paths, output_filename="full_dubbed_audio.mp3"):
    with open(output_filename, "wb") as outfile:
        for path in audio_paths:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path, "rb") as infile:
                    outfile.write(infile.read())
    return output_filename

def get_subtitles_safely(v_id):
    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, 'fetch'):
            return api.fetch(v_id, languages=['en', 'de', 'fa'])
    except Exception:
        pass

    try:
        if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
            t_list = YouTubeTranscriptApi.list_transcripts(v_id)
        elif hasattr(YouTubeTranscriptApi, 'list'):
            t_list = YouTubeTranscriptApi.list(v_id)
        else:
            t_list = YouTubeTranscriptApi().list(v_id)
            
        try:
            return t_list.find_transcript(['en', 'de']).fetch()
        except Exception:
            return t_list.find_generated_transcript(['en', 'de']).fetch()
    except Exception:
        pass

    try:
        return YouTubeTranscriptApi.get_transcript(v_id, languages=['en', 'de', 'fa'])
    except Exception as e:
        st.error(f"امکان استخراج زیرنویس وجود ندارد: {e}")
        return None

# اجرای اصلی برنامه
if video_url:
    col1, col2 = st.columns([1.8, 1.2])
    
    with col1:
        st.subheader("📺 ویدیو")
        st.video(video_url)
        
    with col2:
        v_id = extract_youtube_id(video_url)
        tab1, tab2 = st.tabs(["▶️ پخش زنده و کنترل", "📥 ساخت و دانلود مستقیم MP3"])
        
        with tab1:
            st.write("کنترل همزمان دوبله:")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("▶️ شروع / ادامه دوبله", type="primary", use_container_width=True):
                    st.session_state.is_playing = True
            with c2:
                if st.button("⏸️ توقف (Pause)", type="secondary", use_container_width=True):
                    st.session_state.is_playing = False
            
            if st.session_state.is_playing and v_id:
                subtitles = get_subtitles_safely(v_id)
                if subtitles:
                    if not os.path.exists("audio_cache"):
                        os.makedirs("audio_cache")
                    
                    trans_box = st.empty()
                    status_box = st.empty()
                    
                    # ادامه از آخرین جمله‌ای که متوقف شده بود
                    for idx in range(st.session_state.current_index, len(subtitles)):
                        if not st.session_state.is_playing:
                            st.warning("پخش دوبله متوقف شد.")
                            break
                            
                        item = subtitles[idx]
                        st.session_state.current_index = idx
                        
                        if isinstance(item, dict):
                            raw_text = item.get('text', '')
                            duration = item.get('duration', 2)
                        else:
                            raw_text = getattr(item, 'text', str(item))
                            duration = getattr(item, 'duration', 2)
                        
                        orig_text = clean_text(raw_text)
                        if not orig_text:
                            continue
                        
                        fa_text = translate_to_persian(orig_text)
                        if not fa_text:
                            continue
                            
                        audio_file = f"audio_cache/speech_{idx}.mp3"
                        success = asyncio.run(generate_single_audio(fa_text, audio_file))
                        
                        trans_box.markdown(f"**اصلی:** {orig_text}\n\n**فارسی:** {fa_text}")
                        status_box.caption(f"جمله {idx + 1} از {len(subtitles)}")
                        
                        if success:
                            play_audio_base64(audio_file)
                        
                        time.sleep(duration)
        
        with tab2:
            st.write("ساخت کامل فایل MP3 کل فیلم:")
            download_build_btn = st.button("⚡ ساخت یک‌جای فایل صوتی MP3", type="secondary")
            
            if download_build_btn and v_id:
                subtitles = get_subtitles_safely(v_id)
                if subtitles:
                    if not os.path.exists("audio_cache"):
                        os.makedirs("audio_cache")
                    
                    progress_bar = st.progress(0)
                    dl_status = st.empty()
                    audio_paths = []
                    total = len(subtitles)
                    
                    for idx, item in enumerate(subtitles):
                        progress_bar.progress((idx + 1) / total)
                        dl_status.text(f"در حال ساخت صدا: {idx + 1} از {total}")
                        
                        if isinstance(item, dict):
                            raw_text = item.get('text', '')
                        else:
                            raw_text = getattr(item, 'text', str(item))
                        
                        orig_text = clean_text(raw_text)
                        if not orig_text:
                            continue
                            
                        fa_text = translate_to_persian(orig_text)
                        if not fa_text:
                            continue
                            
                        audio_file = f"audio_cache/dl_speech_{idx}.mp3"
                        success = asyncio.run(generate_single_audio(fa_text, audio_file))
                        if success:
                            audio_paths.append(audio_file)
                    
                    dl_status.success("✅ ساخت فایل کامل شد!")
                    full_mp3 = merge_audio_files_raw(audio_paths, "full_persian_dub.mp3")
                    
                    if os.path.exists(full_mp3):
                        with open(full_mp3, "rb") as f:
                            st.download_button(
                                label="📥 دریافت فایل کامل MP3 دوبله",
                                data=f,
                                file_name="full_persian_dub.mp3",
                                mime="audio/mp3"
                            )
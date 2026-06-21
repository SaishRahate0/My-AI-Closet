import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
from rembg import remove
from PIL import Image
import io
import uuid
import urllib.parse
import random

# 🚨 THIS MUST BE THE FIRST STREAMLIT COMMAND 🚨
st.set_page_config(page_title="My AI Cloud Closet", layout="wide", initial_sidebar_state="expanded")

# --- 1. CONFIGURATION ---
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# Initialize Connections
genai.configure(api_key=GEMINI_API_KEY)

pro_model = genai.GenerativeModel('gemini-2.5-pro')
flash_model = genai.GenerativeModel('gemini-1.5-flash-001')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.sidebar.title("⚡ AI Closet")
menu_selection = st.sidebar.radio("Navigation", ["👗 My Closet", "✨ Daily Stylist", "🔥 Pro Mode", "⚙️ Profile"])

if menu_selection == "👗 My Closet":
    st.title("Add to Your Wardrobe")
    
    uploaded_file = st.file_uploader("Upload a clothing item", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Original Image")
            original_image = Image.open(uploaded_file)
            st.image(original_image, width="stretch")
            
        with col2:
            st.subheader("Essembl-Style Floating Item")
            if st.button("Process & Save"):
                with st.spinner("Processing image & analyzing..."):
                    # 1. Remove Background
                    clean_image = remove(original_image)
                    st.image(clean_image, width="stretch")
                    
                    img_byte_arr = io.BytesIO()
                    clean_image.save(img_byte_arr, format='PNG')
                    img_bytes = img_byte_arr.getvalue()
                    
                    file_name = f"{uuid.uuid4()}.png"
                    
                    # 2. Upload to Storage Bucket
                    supabase.storage.from_("clothes_images").upload(file_name, img_bytes)
                    image_url = supabase.storage.from_("clothes_images").get_public_url(file_name)
                    
                    # 3. Bulletproof AI Analysis (Graceful Degradation)
                    details = ["Item", "Unknown Color", "Casual", "All-Season"] # Fallback defaults
                    
                    try:
                        # Dynamically find an available vision model authorized for your key
                        working_model_name = 'gemini-pro-vision' 
                        for m in genai.list_models():
                            if 'vision' in m.name or 'flash' in m.name:
                                working_model_name = m.name
                                break
                                
                        vision_model = genai.GenerativeModel(working_model_name)
                        vision_model = genai.GenerativeModel(working_model_name)
                        
                        # --- THE ORIGIN SCANNER PROMPT ---
                        prompt = """Look at this clothing item. Be extremely specific. 
                        If you recognize any brand logos, sports teams (like Real Madrid), patterns, or specific origins, include them in the category name!
                        Reply ONLY with a comma-separated list: 
                        1. Specific Category (e.g., Real Madrid Jersey, Nike Air Max, Vintage Denim Jacket)
                        2. Color 
                        3. Formality (casual or formal) 
                        4. Season (summer, winter, spring, all-season)
                        No other text."""
                        
                        # API Fix: Convert transparent PNG to solid RGB 
                        safe_image_for_api = clean_image.convert('RGB')
                        
                        analysis = vision_model.generate_content([prompt, safe_image_for_api])
                        
                        if ',' in analysis.text:
                            details = analysis.text.strip().split(',')
                            st.toast("AI successfully tagged your clothes!")
                            
                    except Exception as e:
                        st.warning("AI tagging skipped due to API limits. Saved with default tags.")
                    
                    # 4. Save to Database Table
                    try:
                        supabase.table("closet").insert({
                            "clothing_type": details[0].strip(),
                            "color": details[1].strip(),
                            "formality": details[2].strip(),
                            "season": details[3].strip(),
                            "image_url": image_url
                        }).execute()
                        st.success("Successfully saved to your cloud wardrobe!")
                        st.rerun() # Refresh the screen instantly to show the sprite
                    except Exception as db_error:
                        print(f"THE REAL ERROR IS: {db_error}") # <--- ADD THIS LINE
                        st.error("Database Error! Check your terminal for the exact reason.")

    st.markdown("---")
    st.subheader("Your Current Wardrobe")
    
    # 5. Display existing clothes (Tiny Icon Grid)
    try:
        response = supabase.table("closet").select("*").execute()
        clothes = response.data
        
        if not clothes:
            st.write("No clothes saved yet!")
        else:
            # A dictionary to assign emojis to clothing types
            emoji_map = {"t-shirt": "👕", "shirt": "👔", "jeans": "👖", "pants": "👖", "shorts": "🩳", "shoes": "👟", "jacket": "🧥", "accessory": "💍", "chain": "⛓️", "jersey": "🎽", "hoodie": "🧥"}
            
            # Using 8 columns makes them tiny like app icons!
            cols = st.columns(8) 
            for index, item in enumerate(clothes):
                with cols[index % 8]:
                    c_type = item.get('clothing_type', '').lower()
                    
                    # Search for the right emoji, default to a hanger if unknown
                    icon = "🧥" 
                    for key in emoji_map:
                        if key in c_type:
                            icon = emoji_map[key]
                            break
                            
                    # Streamlit natively allows you to click images to expand them!
                    # Streamlit natively allows you to click images to expand them!
                    st.image(item.get('image_url', ''), width="stretch")
                    st.caption(f"{icon} {item.get('color', '').title()} {c_type.title()}")
                    
                    # --- NEW: Delete & Archive Buttons ---
                    # We put them side-by-side using tiny columns so it stays neat
                    btn_col1, btn_col2 = st.columns(2)
                    
                    with btn_col1:
                        # Streamlit requires a unique key for buttons in a loop
                        if st.button("❌", key=f"del_{index}", help="Permanently Delete"):
                            supabase.table("closet").delete().eq("image_url", item.get('image_url')).execute()
                            st.rerun()
                            
                    with btn_col2:
                        if st.button("📦", key=f"arc_{index}", help="Archive Item"):
                            st.toast("To fully archive, we will need to add an 'is_archived' column in Supabase later. Use Delete for now!", icon="🚧")
                    
    except Exception as e:
        st.error("Database error while loading wardrobe grid.")

# --- 4. DAILY STYLIST (✨ Daily Stylist) ---
elif menu_selection == "✨ Daily Stylist":
    st.title("Your Personal AI Stylist")
    
    # 1. Quick check to make sure a profile exists
    if 'profiles' not in st.session_state:
        st.warning("⚠️ Go to the Profile tab first to set up your details!")
        st.stop()
        
    # Let the user choose who they are styling today (You or a Guest)
    active_profile = st.selectbox("Who are we styling?", list(st.session_state['profiles'].keys()))
    user = st.session_state['profiles'][active_profile]
    
    st.markdown(f"**Current Vibe:** {user.get('vibe', 'Casual')} | **Face Shape:** {user.get('face_shape', 'Unknown')}")
    
    col1, col2 = st.columns(2)
    with col1:
        occasion = st.selectbox("Occasion", ["Casual", "Party", "Smart Casual", "Formal"])
    with col2:
        season = st.selectbox("Season", ["Summer", "Winter", "Spring/Fall"])

    if st.button("Generate My Outfit"):
        with st.spinner(f"Digging through the closet for {active_profile}..."):
            
            # Fetch all clothes from Supabase
            try:
                response = supabase.table("closet").select("*").execute()
                my_clothes = response.data
            except Exception as e:
                st.error("Make sure your database table 'closet' is set up!")
                my_clothes = []
            
            if not my_clothes:
                st.info("Your closet is empty! Go upload some clothes first.")
            else:
                # -----------------------------------------
                # HERE IS YOUR CUSTOM PROMPT IN ACTION
                # -----------------------------------------
                stylist_prompt = f"""
                Here is the closet inventory: {my_clothes}. 
                The user is a {user.get('gender', 'Male')} with a {user.get('skin_tone', 'Warm')} skin tone and a {user.get('face_shape', 'Unknown')} face shape. 
                The goal vibe today is: {user.get('vibe', 'Casual')}.
                The occasion is {occasion} in the {season}.

                1. Pick exactly one top and one bottom from the inventory that matches this vibe and occasion.
                2. Based on the face shape and the outfit vibe, write 1-2 sentences suggesting a hairstyle or grooming tip or accesory advice (e.g., 'With this streetwear fit and your oval face shape, a taper fade or textured fringe would look great.').
                """
                
                # Ask Gemini 2.5 Pro for the recommendation
                # --- BULLETPROOF TEXT GENERATION ---
                # --- BULLETPROOF TEXT GENERATION ---
                # --- BULLETPROOF TEXT GENERATION ---
                try:
                    # Dynamically find the best text model your key supports
                    working_text_model = 'gemini-pro' # Safe universal default
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods and 'vision' not in m.name:
                            working_text_model = m.name # Grabs whatever text model works
                            break
                                
                    text_model = genai.GenerativeModel(working_text_model)
                    outfit_choice = text_model.generate_content(stylist_prompt).text
                    
                except Exception as e:
                    # DYNAMIC FALLBACK
                    if my_clothes:
                        latest_item = my_clothes[-1] 
                        item_name = f"{latest_item.get('color', '').lower()} {latest_item.get('clothing_type', '').lower()}"
                        outfit_choice = f"The AI Stylist is taking a quick coffee break. Give it a minute, but in the meantime, you should definitely rock that {item_name} you just uploaded!"
                    else:
                        outfit_choice = "The AI Stylist is taking a quick coffee break. Check back in a minute!"
                
                st.subheader("🔥 Your Recommended Fit")
                st.write(outfit_choice)
                
                # --- VISUAL OUTFIT BOARD (FLAT LAY) ---
                st.markdown("---")
                st.subheader("👕 The Fit Vision")
                
                # Create a layout to show the matching clothes
                display_cols = st.columns(4)
                col_idx = 0
                
                # Python scans Gemini's text to see which clothes it picked!
                for item in my_clothes:
                    item_name = f"{item.get('color', '').lower()} {item.get('clothing_type', '').lower()}"
                    
                    # If the name of the clothing item is in the AI's response, display its image
                    if item_name in outfit_choice.lower():
                        with display_cols[col_idx % 4]:
                            st.image(item.get('image_url', ''), width="stretch")
                            st.caption(item_name.title())
                        col_idx += 1
                        
                if col_idx == 0:
                    st.caption("*(Upload more clothes to see the visual outfit board!)*")
                
                # Bonus: Add a regenerate button right below it
                st.markdown("---")
                if st.button("Swap Outfit 🔄"):
                    st.rerun()
# --- 5. PRO STYLIST MODE (🔥 Pro Mode) ---
elif menu_selection == "🔥 Pro Mode":
    st.title("🔥 High-Fashion Pro Stylist")
    st.markdown("Give the AI complete creative freedom to build a layered, accessorized fit.")
    
    if 'profiles' not in st.session_state:
        st.warning("⚠️ Go to the Profile tab first to set up your details!")
        st.stop()
        
    active_profile = st.selectbox("Who are we styling?", list(st.session_state['profiles'].keys()))
    user = st.session_state['profiles'][active_profile]
    
    # FREE TEXT VIBE INPUT
    custom_vibe = st.text_area("What is the exact vibe, occasion, or aesthetic?", 
                               placeholder="e.g., 'Late night drive with friends feeling edgy', 'Old Money aesthetic'")
    
    if st.button("🔥 Create Fire Fit"):
        if not custom_vibe:
            st.warning("Please type a vibe or aesthetic first!")
        else:
            with st.spinner(f"Channeling high-end designer logic for {active_profile}..."):
                # Fetch Clothes
                try:
                    response = supabase.table("closet").select("*").execute()
                    my_clothes = response.data
                except Exception as e:
                    my_clothes = []
                    
                if not my_clothes:
                    st.info("Your closet is empty! Go upload some clothes first.")
                else:
                    # PROMPT ENGINEERING: Forcing 2-3 paragraphs and explicit items
                    pro_prompt = f"""
                    Act as a high-end fashion stylist. 
                    Client's closet: {my_clothes}. 
                    Client details: {user.get('gender', 'Male')}, {user.get('skin_tone', 'Warm')} skin, {user.get('face_shape', 'Unknown')} face.
                    Vibe requested: "{custom_vibe}"
                    
                    RULES:
                    1. Keep it punchy: MAXIMUM 2 to 3 short paragraphs. No more.
                    2. Give the fit a hype title.
                    3. Explicitly list the specific top, bottom, and accessories they should wear from their closet.
                    4. Explain why it works for their face shape and skin tone.
                    """
                    
                    # BULLETPROOF GENERATION (Flash -> Pro -> Fallback)
                    try:
                        working_text_model = 'gemini-pro' 
                        for m in genai.list_models():
                            if 'generateContent' in m.supported_generation_methods and 'vision' not in m.name:
                                working_text_model = m.name
                                break
                                
                        text_model = genai.GenerativeModel(working_text_model)
                        pro_outfit = text_model.generate_content(pro_prompt).text
                    except Exception as e:
                        pro_outfit = "The designer is currently busy at Fashion Week (API Limit hit). Grab a drink and check back in 60 seconds!"
                            
                    # 1. ALWAYS PRINT THE TEXT FIRST
                    st.markdown("---")
                    st.write(pro_outfit)
                    
                    # 2. SMARTER CLOTHES EXTRACTION
                    worn_clothes = []
                    for item in my_clothes:
                        c_type = item.get('clothing_type', '').strip().lower()
                        c_color = item.get('color', '').strip().lower()
                        item_full_name = f"{c_color} {c_type}".strip()
                        
                        # Match if the AI mentions the exact full name OR just the specific clothing type
                        if c_type and (item_full_name in pro_outfit.lower() or c_type in pro_outfit.lower()):
                            if item_full_name not in worn_clothes:
                                worn_clothes.append(item_full_name.title())
                    
                    # Create a specific string of what they are wearing
                    clothes_description = ", ".join(worn_clothes) if worn_clothes else "their selected stylish clothes"
                    
                    # 3. THEN GENERATE THE VISUALIZER
                    st.markdown("---")
                    st.subheader("📸 The Editorial Vision")
                    
                    with st.spinner("Generating full-body editorial photoshoot..."):
                        # CAMERA FIX: Using the brand new 'gen.pollinations' URL and removing the dead 'nologo' parameter
                        image_prompt = f"Full-body wide-angle shot, head-to-toe, of a {user.get('gender', 'Male')} model with {user.get('skin_tone', 'Warm')} skin. They are specifically wearing: {clothes_description}. The outfit matches this vibe: {custom_vibe}. Standing in front of a solid minimalist studio background. The entire outfit including shoes and pants must be visible in the frame. Fashion lookbook style."
                        
                        safe_prompt = urllib.parse.quote(image_prompt)
                        # Added a random seed to force Streamlit to fetch a fresh image every time
                        seed_num = random.randint(1, 100000)
                        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=768&height=1024&seed={seed_num}"
                        
                        st.image(image_url, caption=f"Lookbook: {clothes_description}", use_container_width=True)
                        
                        # 4. The Fit Breakdown (Flat Lay)
                        st.markdown("---")
                        st.subheader("👕 The Fit Breakdown")
                        display_cols = st.columns(4)
                        col_idx = 0
                        
                        for item in my_clothes:
                            c_type = item.get('clothing_type', '').strip().lower()
                            c_color = item.get('color', '').strip().lower()
                            item_full_name = f"{c_color} {c_type}".strip()
                            
                            # Same smarter matching for the visual grid
                            if c_type and (item_full_name in pro_outfit.lower() or c_type in pro_outfit.lower()):
                                with display_cols[col_idx % 4]:
                                    st.image(item.get('image_url', ''), width="stretch")
                                    st.caption(item_full_name.title())
                                col_idx += 1

# --- 4. SMART PROFILE & CONTEXT ENGINE (⚙️ Profile) ---
elif menu_selection == "⚙️ Profile":
    st.title("Profiles & Auto-Setup")
    
    # Initialize the profile dictionary if it doesn't exist yet
    if 'profiles' not in st.session_state:
        st.session_state['profiles'] = {
            "Saish": {"gender": "Male", "skin_tone": "Warm", "face_shape": "Unknown", "vibe": "Casual"}
        }
    
    # --- Profile Switcher ---
    col1, col2 = st.columns([3, 1])
    with col1:
        active_profile = st.selectbox("👤 Select Active Profile", list(st.session_state['profiles'].keys()))
    with col2:
        new_profile_name = st.text_input("New Guest Name")
        if st.button("Add Guest") and new_profile_name:
            st.session_state['profiles'][new_profile_name] = {"gender": "Female", "skin_tone": "Neutral", "face_shape": "Unknown", "vibe": "Casual"}
            st.rerun()

    st.markdown("---")
    
    # --- Magic Selfie Scanner ---
    st.subheader("✨ AI Selfie Setup")
    st.write("Let the AI analyze your face shape and skin tone automatically.")
    selfie_file = st.file_uploader("Upload a selfie", type=["jpg", "jpeg", "png"])
    
    if selfie_file:
        selfie_img = Image.open(selfie_file)
        st.image(selfie_img, width=200)
        
        if st.button("Analyze My Face"):
            with st.spinner("AI is analyzing your features..."):
                try:
                    # Dynamically find an available vision model
                    working_model_name = 'gemini-pro-vision' 
                    for m in genai.list_models():
                        if 'vision' in m.name or 'flash' in m.name:
                            working_model_name = m.name
                            break
                            
                    vision_model = genai.GenerativeModel(working_model_name)
                    prompt = "Look at this face. Reply ONLY with a comma-separated list: Gender, Skin Undertone (Warm, Cool, Neutral, or Olive), and Face Shape (Oval, Square, Round, Diamond, etc.). No other text."
                    
                    # API Fix: Convert image format just to be safe
                    safe_selfie = selfie_img.convert('RGB')
                    
                    response = vision_model.generate_content([prompt, safe_selfie])
                    details = response.text.strip().split(',')
                    
                    if len(details) >= 3:
                        st.success(f"Detected: {details[1].strip()} Skin | {details[2].strip()} Face Shape")
                        # Auto-update the active profile with AI data
                        st.session_state['profiles'][active_profile]["gender"] = details[0].strip()
                        st.session_state['profiles'][active_profile]["skin_tone"] = details[1].strip()
                        st.session_state['profiles'][active_profile]["face_shape"] = details[2].strip()
                        
                        # Refresh the screen so the form below updates instantly
                        st.rerun() 
                    else:
                        st.warning("Couldn't read the face clearly. Try another selfie.")
                        
                except Exception as e:
                    st.error("AI Scanner skipped due to API limits. Please set your details manually below!")

    st.markdown("---")
    
    # --- Manual Override & Goals ---
    st.subheader("Current Profile Settings")
    with st.form("profile_form"):
        current_data = st.session_state['profiles'][active_profile]
        
       # Safely get the index to prevent crashes if the AI uses a weird word
        gender_options = ["Male", "Female", "Non-Binary"]
        saved_gender = current_data.get("gender", "Male")
        g_index = gender_options.index(saved_gender) if saved_gender in gender_options else 0
        
        skin_options = ["Warm", "Cool", "Neutral", "Olive"]
        saved_skin = current_data.get("skin_tone", "Warm")
        s_index = skin_options.index(saved_skin) if saved_skin in skin_options else 0

        gender = st.selectbox("Gender", gender_options, index=g_index)
        skin_tone = st.selectbox("Skin Tone", skin_options, index=s_index)
        face_shape = st.text_input("Face Shape", value=current_data.get("face_shape", ""))
        vibe = st.text_input("What vibe are you going for today? (e.g., Old Money, Streetwear, Minimalist)", value=current_data.get("vibe", ""))
        
        if st.form_submit_button("💾 Save Profile"):
            st.session_state['profiles'][active_profile] = {
                "gender": gender, "skin_tone": skin_tone, "face_shape": face_shape, "vibe": vibe
            }
            st.success(f"{active_profile}'s profile updated!")

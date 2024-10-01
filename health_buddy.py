import streamlit as st
import openai
import base64
from geopy.geocoders import Nominatim
import requests
import math

# Set your OpenAI API key
openai.api_key =  # Replace with your actual API key

# Set your Google Places API key
GOOGLE_PLACES_API_KEY = # Replace with your actual API key

def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

def get_openai_response(messages, image=None):
    try:
        if image:
            base64_image = encode_image(image)
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "This is the image I want you to analyze."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            })

        response = openai.ChatCompletion.create(
            model="gpt-4o" if image else "gpt-3.5-turbo",
            messages=messages,
            max_tokens=500
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return f"An error occurred: {str(e)}"

def add_message(role, content):
    st.session_state['chat_history'].append({"role": role, "content": content})
    if role != "system":
        st.session_state['messages'].append({"role": role, "content": content})

def get_user_location():
    location = st.text_input("Enter your location (city, zip code, etc.):")
    if location:
        geolocator = Nominatim(user_agent="healthcare_buddy")
        try:
            location_data = geolocator.geocode(location)
            if location_data:
                st.write(f"Found coordinates: {location_data.latitude}, {location_data.longitude}")
                return location_data.latitude, location_data.longitude
            else:
                st.error("Location not found. Please try a different input.")
        except Exception as e:
            st.error(f"Error finding location: {str(e)}")
    return None

def determine_facility_type(symptoms):
    prompt = f"Given the following symptoms: {symptoms}, what type of medical facility would be most appropriate? Choose from 'hospital', 'doctor', or 'pharmacy'. Only respond with one of these three words."
    messages = [{"role": "system", "content": "You are a medical triage assistant."},
                {"role": "user", "content": prompt}]
    response = get_openai_response(messages)
    return response.lower()

def search_nearby_facilities(lat, lon, facility_type, radius=5000):
    if not GOOGLE_PLACES_API_KEY:
        st.error("Google Places API key is not set. Please set the GOOGLE_PLACES_API_KEY environment variable.")
        return []

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
    }
    payload = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius
            }
        },
        "includedTypes": [facility_type]
    }
    
    st.write(f"Searching for {facility_type} within {radius} meters of {lat}, {lon}")
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        if 'places' not in data:
            st.write("No results found. Try increasing the radius or changing the facility type.")
            return []
        
        results = data['places']
        st.write(f"Found {len(results)} results")
        
        return results
    
    except requests.exceptions.RequestException as e:
        st.write(f"Error making request: {str(e)}")
        return []
        
def extract_symptoms(chat_history):
    user_messages = " ".join([msg["content"] for msg in chat_history if msg["role"] == "user"])
    
    prompt = f"Extract and list the main symptoms mentioned in the following conversation: {user_messages}. Only list the symptoms, nothing else."
    messages = [{"role": "system", "content": "You are a medical symptom extractor."},
                {"role": "user", "content": prompt}]
    response = get_openai_response(messages)
    return response

def process_input():
    user_input = st.session_state.user_input
    uploaded_image = st.session_state.get('uploaded_image')

    if user_input and uploaded_image:
        add_message("user", f"{user_input} [Image uploaded]")
    elif uploaded_image:
        add_message("user", f"[Image uploaded]")
    elif user_input:
        add_message("user", user_input)
        
    ai_response = get_openai_response(st.session_state['messages'], uploaded_image)
    add_message("assistant", ai_response)
        
    st.session_state.user_input = ""
    

def main():
    st.title("HealthCare Buddy 🤖")
    
    # Initialize session state variables
    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []
    if 'messages' not in st.session_state:
        st.session_state['messages'] = [
            {"role": "system", "content": "You are a helpful AI health Buddy. Gather necessary information and provide health advice. Always recommend consulting a healthcare professional for accurate diagnosis and treatment."}
        ]
    if 'facilities' not in st.session_state:
        st.session_state['facilities'] = []
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 1
    if 'recommended_facility_type' not in st.session_state:
        st.session_state['recommended_facility_type'] = None

    # Rest of the main function...
    
    if not st.session_state['chat_history']:
        welcome_message = get_openai_response(st.session_state['messages'] + [
            {"role": "user", "content": "Introduce yourself as an AI health assistant and ask for the user name."}])
        add_message("assistant", welcome_message)

    st.subheader("Chat")
    for message in st.session_state['chat_history']:
        if message["role"] == "user":
            st.markdown(f"""
            <div style="background-color:#e1f5fe; padding:10px; border-radius:10px; margin:10px 0; width:fit-content;">
            <strong>You:</strong> {message['content']}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color:#eeeeee; padding:10px; border-radius:10px; margin:10px 0; width:fit-content;">
            <strong>HealthCare Buddy 🤖:</strong> {message['content']}
            </div>
            """, unsafe_allow_html=True)

    st.file_uploader("Upload an image (optional)", type=["jpg", "jpeg", "png"], key="uploaded_image")

    st.text_input("Your message:", key="user_input", on_change=process_input)

    if st.button("Send", on_click=process_input):
        pass

    st.subheader("Find Nearby Medical Facilities")
    user_location = get_user_location()
    if user_location:
        facility_type = st.selectbox("Select facility type:", ["hospital", "doctor", "pharmacy"])
        radius = st.slider("Search radius (meters)", min_value=1000, max_value=50000, value=5000, step=1000)
        
        if st.button("Search"):
            symptoms = extract_symptoms(st.session_state['chat_history'])
            st.write(f"Extracted symptoms: \n{symptoms}")
            st.session_state['recommended_facility_type'] = determine_facility_type(symptoms)
            
            st.session_state['facilities'] = search_nearby_facilities(user_location[0], user_location[1], facility_type, radius)
            st.session_state['current_page'] = 1

        if st.session_state['facilities']:
            results_per_page = st.selectbox("Results per page:", [5, 10, 20], key="results_per_page")
            
            total_pages = math.ceil(len(st.session_state['facilities']) / results_per_page)
            st.session_state['current_page'] = st.selectbox("Page", range(1, total_pages + 1), index=st.session_state['current_page']-1)
            
            start_idx = (st.session_state['current_page'] - 1) * results_per_page
            end_idx = start_idx + results_per_page
            
            st.write("Nearby medical facilities:")
            for facility in st.session_state['facilities'][start_idx:end_idx]:
                name = facility.get('displayName', {}).get('text', 'Unknown')
                address = facility.get('formattedAddress', 'Address not available')
                st.write(f"- {name} ({address})")
            
            st.write(f"Showing {start_idx + 1}-{min(end_idx, len(st.session_state['facilities']))} of {len(st.session_state['facilities'])} results")
            
            if st.session_state['recommended_facility_type'] and facility_type != st.session_state['recommended_facility_type']:
                st.write(f"Note: Based on your symptoms, a {st.session_state['recommended_facility_type']} might be more appropriate. Consider changing your selection if needed.")
        elif st.session_state['facilities'] is not None:
            st.write("No facilities found nearby. Try increasing the radius or changing the facility type.")

if __name__ == '__main__':
    main()

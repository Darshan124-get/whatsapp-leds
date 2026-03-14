import os
import datetime
from flask import Flask, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

from twilio.rest import Client as TwilioClient

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: SUPABASE_URL or SUPABASE_KEY not found in .env file")
else:
    # Use from_ instead of Client hint to avoid collision
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Twilio client
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "Webhook is active! Use POST to send data.", 200

    # Twilio sends data as form-encoded, but let's also support query params for manual browser testing
    phone = request.form.get("From") or request.args.get("From")
    message = request.form.get("Body") or request.args.get("Body")

    print(f"--- WEBHOOK TRIGGERED ---")
    print(f"Time: {datetime.datetime.now()}")
    print(f"Method: {request.method}")
    print(f"Phone: {phone}")
    print(f"Message: {message}")

    if not phone or not message:
        print("ERROR: Missing phone or message in request.")
        return jsonify({"error": "Missing phone or message"}), 400

    print(f"Form data received: {request.form}")

    # Normalize message for comparison
    clean_message = message.strip().lower()
    trigger_phrase = "i am interested"

    if clean_message == trigger_phrase:
        print(f"MATCH FOUND: '{message}' matches trigger phrase. Processing lead...")
        data = {
            "phone": phone,
            "message": message
        }

        try:
            # Insert into 'leads' table and wait for response
            response = supabase.table("leads").insert(data).execute()
            
            print(f"Supabase full response: {response}")

            # Check if response has data and it's not empty
            if response.data:
                inserted_id = response.data[0].get('id')
                print(f"SUCCESS: Lead saved with ID: {inserted_id}")
                
                # Verify by querying it back
                verification = supabase.table("leads").select("*").eq("id", inserted_id).execute()
                if verification.data:
                    print(f"VERIFICATION SUCCESS: Found record in DB: {verification.data}")
                else:
                    print("VERIFICATION FAILED: Record not found immediately after insert!")
            else:
                print("WARNING: Supabase returned success but no data was inserted.")

            # Send THANK YOU auto-reply
            if twilio_client and TWILIO_WHATSAPP_NUMBER:
                try:
                    print(f"Sending THANK YOU reply to {phone}...")
                    reply = twilio_client.messages.create(
                        from_=TWILIO_WHATSAPP_NUMBER,
                        content_sid='HXb5b62575e6e4ff6129ad7c8efe1f983e',
                        content_variables='{"1":"Thank you","2":"for your interest! We will contact you soon."}',
                        to=phone
                    )
                    print(f"Auto-reply SID: {reply.sid}")
                except Exception as twilio_err:
                    print(f"Twilio Error (Thank you): {twilio_err}")

        except Exception as e:
            print(f"CRITICAL DATABASE ERROR: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        print(f"NO MATCH: '{message}' does not match trigger phrase '{trigger_phrase}'. Lead not saved.")
        
        # Send INSTRUCTIONS auto-reply
        if twilio_client and TWILIO_WHATSAPP_NUMBER:
            try:
                print(f"Sending INSTRUCTION reply to {phone}...")
                reply = twilio_client.messages.create(
                    from_=TWILIO_WHATSAPP_NUMBER,
                    body="To register your interest, please reply with 'I am interested'",
                    to=phone
                )
                print(f"Instruction-reply SID: {reply.sid}")
            except Exception as twilio_err:
                print(f"Twilio Error (Instructions): {twilio_err}")

    return "OK", 200

@app.route("/leads", methods=["GET"])
def view_leads():
    try:
        response = supabase.table("leads").select("*").order("created_at", desc=True).execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Print config preview for debugging
    print("========================================")
    print("SERVER STARTING...")
    print(f"Supabase URL: {SUPABASE_URL}")
    if SUPABASE_KEY:
        print(f"Supabase Key (last 5): ...{SUPABASE_KEY[-5:]}")
    print(f"Twilio Number: {TWILIO_WHATSAPP_NUMBER}")
    print("========================================")
    
    # Run on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)

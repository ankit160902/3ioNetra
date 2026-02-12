
import asyncio
import os
import sys
from datetime import datetime
from pymongo import MongoClient
import uuid
import hashlib
import secrets
import random

# MongoDB Connection (Using the correct URI from your .env)
MONGO_URI = "mongodb+srv://ankit:ozHqxvsmsM5MLFpq@cluster0.zmoledd.mongodb.net/"
DB_NAME = "spiritual_voice_bot"

# Connect to DB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db["users"]

# Correct Password Hashing (Matching auth_service.py)
def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hashed, salt

# Helper to generate user ID
def generate_user_id():
    return secrets.token_hex(12)

# Mock Data Generators
temples_list = ["Kashi Vishwanath", "Tirupati Balaji", "Vaishno Devi", "Kedarnath", "Badrinath", "Rameshwaram", "Somnath", "Dwarkadhish", "Jagannath Puri", "Golden Temple"]
purchases_list = ["Rudraksha Mala", "Bhagavad Gita", "Ganga Jal", "Sandalwood Incense", "Copper Kalash", "Shiva Lingam", "Puja Thali", "Mantra Box", "Saffron", "Diya"]
first_names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan"]
last_names = ["Sharma", "Verma", "Gupta", "Malhotra", "Bhatia", "Saxena", "Mehta", "Joshi", "Singh", "Patel"]
deities_list = ["Shiva", "Krishna", "Ganesha", "Durga", "Hanuman", "Lakshmi", "Saraswati", "Kali", "Vishnu", "Ram"]
rashis = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
gotras = ["Bharadwaja", "Kashyapa", "Vashistha", "Vishvamitra", "Gautama", "Jamadagni", "Atri", "Agastya"]

def create_mock_user(index, custom_first=None, custom_last=None):
    first_name = custom_first if custom_first else first_names[index % len(first_names)]
    last_name = custom_last if custom_last else last_names[index % len(last_names)]
    email = f"user{index+1}@example.com"
    password = f"Password{index+1}!"
    
    hashed, salt = hash_password(password)
    user_id = generate_user_id()
    
    dob_year = random.randint(1980, 2005)
    dob_month = random.randint(1, 12)
    dob_day = random.randint(1, 28)
    dob = f"{dob_year}-{dob_month:02d}-{dob_day:02d}"
    
    # Random selection
    deity = random.choice(deities_list)
    rashi = random.choice(rashis)
    gotra = random.choice(gotras)
    
    # Temples
    user_temples = []
    for _ in range(random.randint(1, 2)):
        temple_name = random.choice(temples_list)
        user_temples.append({
            "temple_id": temple_name,
            "visits": [{
                "date": datetime.utcnow().isoformat(),
                "purpose": "Historical Visit",
                "event": "",
                "sevas": [],
                "activity": []
            }]
        })
        
    # Purchases
    user_purchases = []
    for _ in range(random.randint(1, 2)):
        product_name = random.choice(purchases_list)
        user_purchases.append({
            "type": "Historical",
            "datetime": datetime.utcnow().isoformat(),
            "product_id": "",
            "name": product_name,
            "category": "Spiritual Item",
            "amount": random.randint(100, 5000)
        })

    user_doc = {
        "id": user_id,
        "email": email,
        "phone": f"98765432{index:02d}",
        "password_hash": hashed,
        "password_salt": salt,
        "created_at": datetime.utcnow(),
        
        "first_name": first_name,
        "middle_name": "",
        "last_name": last_name,
        "date_of_birth": dob,
        "occupation": "professional",
        "gender": "male", # Amit and Pratyush are typically male names
        "deities": [deity],
        
        "spiritual_profile": {
            "rashi": rashi,
            "gothra": gotra,
            "nakshatra": "Rohini",
            "kundli": None
        },
        
        "temples": user_temples,
        "purchases": user_purchases
    }
    
    return user_doc, email, password

def seed_users():
    print("Cleanup: Removing existing mock users...")
    emails_to_remove = [f"user{i+1}@example.com" for i in range(12)]
    users_collection.delete_many({"email": {"$in": emails_to_remove}})
    
    print("Seeding 12 users (including Amit and Pratyush)...")
    users_to_insert = []
    creds = []
    
    # Specific users
    specific_users = [
        ("Amit", "Bharadwaj"),
        ("Pratyush", "Ambuj")
    ]
    
    for i in range(12):
        if i < len(specific_users):
            fname, lname = specific_users[i]
            doc, email, pwd = create_mock_user(i, fname, lname)
        else:
            doc, email, pwd = create_mock_user(i)
            
        users_to_insert.append(doc)
        creds.append(f"Email: {email}, Password: {pwd}, Name: {doc['first_name']} {doc['last_name']}, ID: {doc['id']}")
    
    if users_to_insert:
        result = users_collection.insert_many(users_to_insert)
        print(f"Successfully inserted {len(result.inserted_ids)} users.")
        
        print("\n--- NEW USER CREDENTIALS ---")
        for cred in creds:
            print(cred)
        print("----------------------------")
    else:
        print("No users to insert.")

if __name__ == "__main__":
    seed_users()

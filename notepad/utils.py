import json, os, time
from werkzeug.security import generate_password_hash, check_password_hash
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # points to notepad/
USERS_FILE = os.path.join(BASE_DIR, "data", "users.json")
NOTES_FILE = os.path.join(BASE_DIR, "data", "notes.json")


# ---------------- Generic helpers ----------------

def generate_otp():
    """Return a 6-digit string OTP."""
    return "{:06d}".format(random.randint(0, 999999))


def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def hash_password(pw): return generate_password_hash(pw)
def verify_password(pw, h): return check_password_hash(h, pw)

# ---------------- Users ----------------
def load_users():
    try:
        with open("data/users.json", "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Convert dict -> list if old format
                return list(data.values())
            else:
                return []
    except FileNotFoundError:
        return []


def update_user_profile(email, updated_data):
    users = load_json("data/users.json")
    for i, user in enumerate(users):
        if user["email"] == email:
            users[i].update(updated_data)
            break
    save_json("data/users.json", users)


# ---------------- Notes ----------------
def load_notes():
    data = load_json(NOTES_FILE)
    return data.get("notes", [])

def save_notes(notes):
    save_json(NOTES_FILE, {"notes": notes})

def add_note(owner, title, content):
    notes = load_notes()
    note_id = max([n["id"] for n in notes], default=0) + 1
    now = time.time()
    notes.append({
        "id": note_id,
        "owner": owner,
        "title": title,
        "content": content,
        "status": "active",
        "updated_at": now
    })
    save_notes(notes)

def update_note(owner, note_id, title, content):
    notes = load_notes()
    for n in notes:
        if n["id"]==note_id and n["owner"]==owner:
            n["title"] = title
            n["content"] = content
            n["updated_at"] = time.time()
            break
    save_notes(notes)

def soft_delete_note(owner, note_id):
    notes = load_notes()
    for n in notes:
        if n["id"]==note_id and n["owner"]==owner:
            n["status"] = "archived"
            n["updated_at"] = time.time()
            break
    save_notes(notes)

def restore_note(owner, note_id):
    notes = load_notes()
    for n in notes:
        if n["id"]==note_id and n["owner"]==owner:
            n["status"] = "active"
            n["updated_at"] = time.time()
            break
    save_notes(notes)

def permanently_delete_note(owner, note_id):
    notes = load_notes()
    notes = [n for n in notes if not (n["id"]==note_id and n["owner"]==owner)]
    save_notes(notes)

def update_note_owner(old_email, new_email):
    """Updates the 'owner' field for all notes associated with the old email.
       Applies strip/lower for robust matching against JSON data."""
       
    # Normalize emails for comparison against notes data
    normalized_old_email = old_email.strip().lower()
    normalized_new_email = new_email.strip().lower()
    
    notes = load_notes()
    
    # Flag to track if any changes were made
    changes_made = False
    
    for note in notes:
        # Normalize the note owner for comparison
        note_owner_normalized = note["owner"].strip().lower()
        
        # Compare normalized emails
        if note_owner_normalized == normalized_old_email:
            # Update the stored owner to the new normalized email
            # We save the new email in its *correct* case (from the form)
            note["owner"] = new_email # Use the original case from the form/pending data
            changes_made = True
            
    if changes_made:
        save_notes(notes) 
    return changes_made
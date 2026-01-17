import json
import os

SETTINGS_FILE = 'user_settings.json'
BLOCKED_USERS = ["6175052841", "6878892900"]

def remove_blocked_users():
    if not os.path.exists(SETTINGS_FILE):
        print(f"Error: {SETTINGS_FILE} not found.")
        return

    with open(SETTINGS_FILE, 'r') as f:
        data = json.load(f)

    # Convert IDs to strings just in case, though they are likely strings in JSON keys
    blocked_ids = [str(uid) for uid in BLOCKED_USERS]
    
    removed_count = 0
    
    # Iterate over all top-level keys (filters, categories, etc.)
    for section_name, section_data in data.items():
        if isinstance(section_data, dict):
            keys_to_remove = []
            for uid in section_data.keys():
                if uid in blocked_ids:
                    keys_to_remove.append(uid)
            
            for uid in keys_to_remove:
                del section_data[uid]
                print(f"Removed user {uid} from section '{section_name}'")
                removed_count += 1

    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Done. Removed {removed_count} entries for {len(blocked_ids)} users.")

if __name__ == "__main__":
    remove_blocked_users()

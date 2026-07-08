import hashlib
import sys

SECRET_SALT = "VishalStenoPremiumTTS_2026"

def generate_product_key(machine_id):
    mid = str(machine_id).strip().upper()
    h = hashlib.sha256((mid + SECRET_SALT).encode('utf-8')).hexdigest()
    raw_key = h.upper()
    key_parts = [raw_key[i:i+4] for i in range(0, 16, 4)]
    return "VST-" + "-".join(key_parts)

if __name__ == "__main__":
    print("==================================================")
    print("Vishal Steno Speech Studio - License Key Generator")
    print("==================================================")
    try:
        mid = input("Enter client's Machine ID (UUID): ").strip()
        if not mid:
            print("Error: Machine ID cannot be empty.")
            sys.exit(1)
        key = generate_product_key(mid)
        print("\nGenerated Product Key:")
        print(f"👉 {key}")
        print("==================================================")
    except KeyboardInterrupt:
        print("\nCancelled.")

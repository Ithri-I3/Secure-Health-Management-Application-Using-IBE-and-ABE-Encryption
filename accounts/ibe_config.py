import json
from .ibe import IBE  # Assurez-vous que le module IBE est importé

# Initialiser le système IBE globalement
ibe_system = IBE()
public_params, master_key = ibe_system.setup()

def ibe_encrypt(insurance_number, email):
    """Chiffre le numéro d'assurance avec IBE en utilisant l'email comme identité."""
    return ibe_system.encrypt(int(insurance_number), email)

def serialize_ciphertext(ciphertext):
    """Sérialise l'objet ciphertext pour stockage en base de données."""
    return {'U': ciphertext['U'], 'V': ciphertext['V']}

def ibe_decrypt(encrypted_data, email):
    """Déchiffre un message chiffré avec IBE en utilisant l'identité email."""
    try:
        # Charger les données chiffrées
        encrypted_dict = json.loads(encrypted_data.decode('utf-8'))

        # Extraire la clé privée associée à l'email
        private_key = ibe_system.extract_private_key(email)

        # Vérifier que la structure des données est correcte
        if 'U' not in encrypted_dict or 'V' not in encrypted_dict:
            raise ValueError("Format des données chiffrées invalide.")

        # Déchiffrement
        decrypted_value = ibe_system.decrypt(encrypted_dict, private_key, email)

        return str(decrypted_value)
    except Exception as e:
        return f"Erreur lors du déchiffrement : {str(e)}"
    

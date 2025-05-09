import json
from .abe import ABE  # Assurez-vous que le module ABE est accessible (chemin relatif ou PYTHONPATH)

# Initialiser globalement le système ABE
abe_system = ABE()
public_params, master_key = abe_system.setup()

def abe_keygen(attributes):
    """
    Génère la clé privée pour un utilisateur en fonction de ses attributs.
    
    Args:
        attributes (list): Liste des attributs de l'utilisateur.
        
    Returns:
        dict: Clé privée générée par le système ABE.
    """
    return abe_system.key_gen(master_key, attributes)

def abe_encrypt(message, policy):
    """
    Chiffre un message selon une politique d'accès.
    
    Args:
        message (int): Le message à chiffrer (doit être inférieur à p).
        policy (str): La politique d'accès (ex. "médecin AND (cardiologie OR radiologie)").
    
    Returns:
        bytes: Les données chiffrées sérialisées en JSON.
    """
    ciphertext = abe_system.encrypt(message, policy)
    # Sérialisation en JSON pour stockage ou transmission
    return json.dumps(ciphertext).encode('utf-8')

def serialize_ciphertext(ciphertext):
    """
    Sérialise le ciphertext dans un format adapté pour le stockage.
    
    Args:
        ciphertext (dict): L'objet ciphertext généré par abe_system.encrypt.
        
    Returns:
        dict: Représentation sérialisée du ciphertext.
    """
    # Vous pouvez adapter cette fonction pour convertir les types non-JSON (par exemple, les tuples) en chaînes
    return ciphertext

def abe_decrypt(encrypted_data, private_key, attributes, policy_str):
    """
    Déchiffre un message chiffré avec ABE en utilisant la clé privée et les attributs de l'utilisateur.
    """
    try:
        # Vérifier le type de encrypted_data avant toute manipulation
        print(f"DEBUG: Type de encrypted_data avant traitement: {type(encrypted_data)}")
        
        # Gérer les différents types possibles d'encrypted_data
        if isinstance(encrypted_data, dict):
            # Si c'est déjà un dictionnaire, l'utiliser directement
            ciphertext = encrypted_data
            print("DEBUG: encrypted_data est déjà un dictionnaire")
        elif isinstance(encrypted_data, bytes):
            # Si c'est des bytes, décoder en string puis charger le JSON
            try:
                encrypted_str = encrypted_data.decode('utf-8')
                ciphertext = json.loads(encrypted_str)
                print(f"DEBUG: encrypted_data décodé des bytes: {encrypted_str[:50]}...")
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                print(f"DEBUG: Erreur de décodage/parsing: {str(e)}")
                return f"Erreur lors du déchiffrement : {str(e)}"
        elif isinstance(encrypted_data, str):
            # Si c'est une chaîne, charger le JSON
            try:
                ciphertext = json.loads(encrypted_data)
                print(f"DEBUG: encrypted_data chargé depuis string: {encrypted_data[:50]}...")
            except json.JSONDecodeError as e:
                print(f"DEBUG: Erreur de parsing JSON: {str(e)}")
                return f"Erreur lors du déchiffrement : {str(e)}"
        else:
            # Type non pris en charge
            error_msg = f"Type de données non pris en charge: {type(encrypted_data)}"
            print(f"DEBUG: {error_msg}")
            return f"Erreur lors du déchiffrement : {error_msg}"
        
        # Vérifier la structure du ciphertext
        print(f"DEBUG: Structure du ciphertext: {type(ciphertext)}")

        # Déchiffrement
        decrypted_value = abe_system.decrypt(ciphertext, private_key, attributes, policy_str)
        return str(decrypted_value)
    
    except Exception as e:
        print(f"Erreur lors du déchiffrement : {str(e)}")
        return f"Erreur lors du déchiffrement : {str(e)}"



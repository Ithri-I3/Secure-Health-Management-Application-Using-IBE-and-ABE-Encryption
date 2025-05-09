message="test_abe"
message_int = 655305478189230790610674516942053583620123007424828544279924
print("le message en chiffre : ",message_int)

# Supposons que message_int contient l'entier obtenu précédemment
byte_length = (message_int.bit_length() + 7) // 8  # Calculer la longueur en bytes
bytes_data = message_int.to_bytes(byte_length, 'big')  # Convertir l'entier en bytes
decoded_content = bytes_data.decode('utf-8')  # Décoder les bytes en UTF-8

print("le message original: ", decoded_content)
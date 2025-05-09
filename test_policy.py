import sys
from accounts.abe import ABE

# Créer une instance de ABE
abe = ABE()

# Tester avec une politique simple
policy = "medecin or patient"
print(f"Politique originale: {policy}")

# Analyser la politique
parsed = abe._parse_policy(policy)
print(f"Politique analysée: {parsed}")

# Afficher les détails
if parsed['type'] == 'or':
    print("Type de la politique: OR")
    print("Opérandes:")
    for op in parsed['operands']:
        if op['type'] == 'attribute':
            print(f"  - Attribut: {op['name']}")
        else:
            print(f"  - Expression de type: {op['type']}")
else:
    print(f"Type de la politique: {parsed['type']}")

# Tester avec une politique complexe
policy_complex = "medecin AND (cardiologie OR radiologie)"
print(f"\nPolitique complexe originale: {policy_complex}")

# Analyser la politique complexe
parsed_complex = abe._parse_policy(policy_complex)
print(f"Politique complexe analysée: {parsed_complex}")
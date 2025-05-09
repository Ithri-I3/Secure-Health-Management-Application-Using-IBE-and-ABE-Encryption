from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import ABEKey, Consultation, Laborantin, Medecin, MedicalRecord, Prescription, Radiologue, User, Patient, LabTest
import base64
import json
import os
from .ibe_config import ibe_encrypt,serialize_ciphertext
from .abe_config import abe_encrypt





class LoginForm(AuthenticationForm):
    username = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mot de passe'}))

class UserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        
        # Limiter les choix de rôle en fonction de l'utilisateur connecté
        if self.user:
            if self.user.is_medecin or self.user.is_praticien:
                self.fields['role'].choices = [('PATIENT', 'Patient')]
            elif not self.user.is_admin:
                # Pour les autres rôles non-admin, désactiver le champ
                self.fields['role'].disabled = True
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # Set username to be the same as email (or a portion of it)
        # This ensures username is unique since email is unique
        import uuid
        email_prefix = self.cleaned_data['email'].split('@')[0][:20]  # First 20 chars of email
        unique_suffix = str(uuid.uuid4())[:8]  # 8 chars from a UUID
        user.username = f"{email_prefix}_{unique_suffix}"
        
        if commit:
            user.save()
        return user
BLOOD_TYPE_CHOICES = [
            ('A+', 'A+'),
            ('A-', 'A-'),
            ('B+', 'B+'),
            ('B-', 'B-'),
            ('AB+', 'AB+'),
            ('AB-', 'AB-'),
            ('O+', 'O+'),
            ('O-', 'O-'),
        ]
class PatientForm(forms.ModelForm):
    insurance_number = forms.CharField(
        max_length=50, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Numéro d\'assurance'}),
        label='Numéro d\'assurance',
        help_text='Ce numéro sera chiffré pour protéger vos données'
    )
    
    class Meta:
        model = Patient
        fields = ['date_of_birth', 'blood_type']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'blood_type': forms.Select(choices=BLOOD_TYPE_CHOICES, attrs={'class': 'form-control'}),
            
        }
        labels = {
            'date_of_birth': 'Date de naissance',
            'blood_type': 'Groupe sanguin',
            
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        patient = super(PatientForm, self).save(commit=False)
        insurance_number = self.cleaned_data.get('insurance_number')
        
        # On utilise l'email de l'utilisateur connecté comme identité IBE
        email = self.user.email if self.user else None
        print("numero d'assurance: ",insurance_number)
        print("email: ",email)

        if insurance_number and email:
            ibe_ciphertext = ibe_encrypt(insurance_number, email)
            ibe_ciphertext_serialized = ibe_ciphertext
            print("we are here 1")

            # Stocker le ciphertext sous forme de JSON encodé en UTF-8
            patient.encrypted_insurance = json.dumps(ibe_ciphertext_serialized).encode('utf-8')
            patient.ibe_policy = f'email:{email}'
            print("we are here 2")

        # Assigner l'utilisateur au patient
        if self.user:
            patient.user = self.user
            print("we are here 3")

        
        patient.save()
        print("we are here 4")
        return patient



# Formulaire pour le profil Médecin
class MedecinForm(forms.ModelForm):
    class Meta:
        model = Medecin
        fields = ['specialization', 'phone_number']

# Formulaire pour le profil Radiologue
class RadiologueForm(forms.ModelForm):
    class Meta:
        model = Radiologue
        fields = ['radiology_field', 'phone_number']

# Formulaire pour le profil Laborantin
class LaborantinForm(forms.ModelForm):
    class Meta:
        model = Laborantin
        fields = ['lab_department', 'phone_number']

# Formulaire pour le Dossier Médical (MedicalRecord)
class MedicalRecordForm(forms.ModelForm):
    content = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        label='Contenu du dossier médical',
        help_text='Ce contenu sera chiffré pour protéger les données du patient'
    )
    
    class Meta:
        model = MedicalRecord
        fields = ['patient', 'abe_policy']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'abe_policy': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'patient': 'Patient',
            'abe_policy': 'Politique ABE',
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.user = user
    
    def save(self, commit=True):
        medical_record = super().save(commit=False)
        content = self.cleaned_data.get('content')
        
        # Assigner le créateur du dossier médical
        if self.user:
            medical_record.creator = self.user
        
        # Chiffrer le contenu du dossier médical
        if content:
            try:
                # Convertir le contenu (texte) en entier
                message_int = int.from_bytes(content.encode('utf-8'), 'big')
                
                # Utiliser la politique ABE indiquée dans le formulaire pour le chiffrement
                encrypted_content = abe_encrypt(message_int, medical_record.abe_policy)
                # Stocker le ciphertext (ici en bytes)
                medical_record.encrypted_data = encrypted_content
            except Exception as e:
                # En cas d'erreur, vous pouvez soit lever une exception, soit stocker le message en clair (à éviter en prod)
                medical_record.encrypted_data = content.encode('utf-8')
                print(f"Erreur lors du chiffrement ABE : {e}")
        
        if commit:
            medical_record.save()
            # Ajouter le créateur aux utilisateurs assignés
            if self.user:
                medical_record.assigned_to.add(self.user)
        
        return medical_record

# Formulaire pour une Consultation
class ConsultationForm(forms.ModelForm):
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        label='Notes de consultation',
        help_text='Ces notes seront chiffrées avec IBE pour protéger les données du patient'
    )
    
    class Meta:
        model = Consultation
        fields = ['patient', 'abe_policy', 'follow_up_required']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'abe_policy': forms.TextInput(attrs={'class': 'form-control'}),
            'follow_up_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'patient': 'Patient',
            'abe_policy': 'Identité IBE',
            'follow_up_required': 'Suivi nécessaire',
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.user = user
        # Renommer le champ pour plus de clarté dans l'interface
        self.fields['abe_policy'].help_text = "Email du patient ou autre identité pour le chiffrement IBE"
    
    def save(self, commit=True):
        consultation = super().save(commit=False)
        
        # Assigner le professionnel de santé qui a créé la consultation
        if self.user:
            consultation.professional = self.user
        
        # Chiffrer les notes de consultation avec IBE
        notes = self.cleaned_data.get('notes')
        if notes:
            try:
                # Utiliser l'identité IBE (stockée dans le champ abe_policy pour compatibilité)
                identity = self.user.email
                
                # Utiliser le chiffrement IBE
                from .ibe_config import ibe_encrypt, serialize_ciphertext
                ibe_ciphertext = ibe_encrypt(notes, identity)
                
                # Sérialiser et stocker le ciphertext
                ibe_ciphertext_serialized = serialize_ciphertext(ibe_ciphertext)
                consultation.encrypted_notes = json.dumps(ibe_ciphertext_serialized).encode('utf-8')
                
            except Exception as e:
                # En cas d'erreur, stocker le message en clair (à éviter en prod)
                consultation.encrypted_notes = notes.encode('utf-8')
                print(f"Erreur lors du chiffrement IBE : {e}")
        
        if commit:
            consultation.save()
        
        return consultation


# Nouveau formulaire pour les ordonnances
class PrescriptionForm(forms.ModelForm):
    content = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        label='Contenu de l\'ordonnance',
        help_text='Ce contenu sera chiffré pour protéger les données du patient'
    )
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label='Patient'
    )
    
    class Meta:
        model = Prescription
        fields = ['consultation', 'abe_policy', 'validity_days']
        widgets = {
            'consultation': forms.Select(attrs={'class': 'form-control'}),
            'abe_policy': forms.TextInput(attrs={'class': 'form-control'}),
            'validity_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
        labels = {
            'consultation': 'Consultation',
            'abe_policy': 'Politique ABE',
            'validity_days': 'Validité (jours)',
        }

# Formulaire pour les analyses de laboratoire
class LabTestForm(forms.ModelForm):
    class Meta:
        model = LabTest
        fields = ['patient', 'test_type', 'description']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'test_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'patient': 'Patient',
            'test_type': 'Type d\'analyse',
            'description': 'Description',
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.user = user
    
    def save(self, commit=True):
        lab_test = super().save(commit=False)
        
        # Assigner le demandeur de l'analyse
        if self.user:
            lab_test.requested_by = self.user
        
        if commit:
            lab_test.save()
        
        return lab_test

# Formulaire pour remplir les résultats d'analyse
class LabTestResultForm(forms.ModelForm):
    results = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        required=True,
        label='Résultats d\'analyse',
        help_text='Ces résultats seront chiffrés avec ABE pour protéger les données du patient'
    )
    
    abe_policy = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False,
        label='Politique ABE',
        help_text='Politique de contrôle d\'accès pour le chiffrement ABE (laissez vide pour utiliser la politique par défaut)'
    )
    
    class Meta:
        model = LabTest
        fields = ['status', 'abe_policy']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'status': 'Statut',
            'abe_policy': 'Politique ABE',
        }
    
    # Nous ne chiffrons plus les résultats ici, mais dans la vue LabTestUpdateView
    # pour éviter les conflits et s'assurer que le chiffrement est effectué correctement
    def save(self, commit=True):
        lab_test = super().save(commit=False)
        
        if commit:
            lab_test.save()
        
        return lab_test

# Formulaire pour les ordonnances
class PrescriptionForm(forms.ModelForm):
    content = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        label='Contenu de l\'ordonnance',
        help_text='Ce contenu sera chiffré pour protéger les données du patient'
    )
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label='Patient'
    )
    
    class Meta:
        model = Prescription
        fields = ['consultation', 'abe_policy', 'validity_days']
        widgets = {
            'consultation': forms.Select(attrs={'class': 'form-control'}),
            'abe_policy': forms.TextInput(attrs={'class': 'form-control'}),
            'validity_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
        labels = {
            'consultation': 'Consultation',
            'abe_policy': 'Politique ABE',
            'validity_days': 'Validité (jours)',
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['consultation'].required = False
    
    def save(self, commit=True):
        prescription = super().save(commit=False)
        content = self.cleaned_data.get('content')
        print("we are here 1")
        # Si aucune consultation n'est sélectionnée mais qu'un patient est choisi,
        # créer une nouvelle consultation
        if not self.cleaned_data.get('consultation') and self.cleaned_data.get('patient') and self.user:
            print("we are here 2")
            # Créer une nouvelle consultation
            consultation = Consultation.objects.create(
                patient=self.cleaned_data['patient'],
                professional=self.user,
                encrypted_notes=b'Consultation pour ordonnance',
                abe_policy=self.cleaned_data['abe_policy']
            )
            print("we are here 3")
            # Assigner explicitement la consultation à l'ordonnance
            prescription.consultation = consultation
            
            # Sauvegarder immédiatement pour établir la relation
            
            print("we are here 4")
            # Éviter une double sauvegarde si commit est True
            
        
        # Chiffrer le contenu de l'ordonnance
        if content:
            try:
                print("we are here 5")
                # Convertir le contenu (texte) en entier
                message_int = int.from_bytes(content.encode('utf-8'), 'big')
                
                # Utiliser la politique ABE indiquée dans le formulaire pour le chiffrement
                encrypted_content = abe_encrypt(message_int, prescription.abe_policy)
                # Stocker le ciphertext (ici en bytes)
                prescription.encrypted_content = encrypted_content
                print("we are here 6")
            except Exception as e:
                # En cas d'erreur, vous pouvez soit lever une exception, soit stocker le message en clair (à éviter en prod)
                prescription.encrypted_content = content.encode('utf-8')
                print(f"Erreur lors du chiffrement ABE : {e}")
        
        if commit:
            prescription.save()
            print("we are here 7")
        return prescription
    




class ConsultationForm(forms.ModelForm):
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        label='Notes médicales',
        help_text='Ces notes seront chiffrées avec IBE pour protéger les données du patient'
    )
    
    class Meta:
        model = Consultation
        fields = ['patient', 'abe_policy', 'follow_up_required']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'abe_policy': forms.TextInput(attrs={'class': 'form-control'}),
            'follow_up_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'patient': 'Patient',
            'abe_policy': 'Identité IBE',
            'follow_up_required': 'Suivi nécessaire',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Renommer le champ pour plus de clarté dans l'interface
        self.fields['abe_policy'].help_text = "Email du patient ou autre identité pour le chiffrement IBE"
        
        # Si nous sommes en mode édition et que des notes chiffrées existent déjà
        if self.instance and self.instance.pk and self.instance.encrypted_notes:
            try:
                # Récupérer l'identité IBE (stockée dans le champ abe_policy pour compatibilité)
                identity = self.instance.abe_policy
                print(f"DEBUG: Identité IBE: {identity}")
                
                # Tenter de déchiffrer les notes avec IBE
                encrypted_str = None
                if isinstance(self.instance.encrypted_notes, bytes):
                    try:
                        encrypted_str = self.instance.encrypted_notes.decode('utf-8')
                        print(f"DEBUG: Notes décodées avec succès: {encrypted_str[:50]}...")
                    except UnicodeDecodeError:
                        print("DEBUG: Erreur de décodage UTF-8, essai avec latin-1")
                        encrypted_str = self.instance.encrypted_notes.decode('latin-1')
                else:
                    encrypted_str = str(self.instance.encrypted_notes)
                    print(f"DEBUG: Notes non-bytes: {encrypted_str[:50]}...")
                
                # Vérifier que l'identité IBE existe
                if not identity:
                    print("DEBUG: Identité IBE manquante")
                    self.initial['notes'] = "[Impossible de déchiffrer: identité IBE manquante]"
                    return
                
                # Essayer de déchiffrer avec IBE
                from .ibe_config import ibe_decrypt
                decrypted_value = ibe_decrypt(encrypted_str, identity)
                
                # Afficher les notes déchiffrées
                if decrypted_value and not decrypted_value.startswith('Erreur'):
                    self.initial['notes'] = decrypted_value
                    print(f"DEBUG: Déchiffrement IBE réussi: {decrypted_value[:50]}...")
                else:
                    print(f"DEBUG: Échec du déchiffrement IBE: {decrypted_value}")
                    self.initial['notes'] = "[Impossible de déchiffrer les notes avec cette identité]"
            except Exception as e:
                print(f"Erreur lors du déchiffrement des notes: {e}")
                self.initial['notes'] = f"[Erreur: {str(e)}]"
    
    def save(self, commit=True):
        consultation = super().save(commit=False)
        notes = self.cleaned_data.get('notes')
        
        # Assigner le professionnel si c'est une nouvelle consultation
        if not consultation.pk and self.user:
            consultation.professional = self.user
        
        # Chiffrer les notes de consultation
        if notes:
            try:
                # Vérifier que la politique ABE est définie
                if not consultation.abe_policy:
                    print("Erreur: Politique ABE manquante")
                    consultation.abe_policy = f"role:{self.user.role.lower()}" if self.user else "role:admin"
                    print(f"Politique ABE définie par défaut: {consultation.abe_policy}")
                
                # Convertir le contenu (texte) en entier
                from .abe_config import abe_encrypt
                message_int = int.from_bytes(notes.encode('utf-8'), 'big')
                
                # Utiliser la politique ABE indiquée dans le formulaire pour le chiffrement
                encrypted_notes = abe_encrypt(message_int, consultation.abe_policy)
                # Stocker le ciphertext (ici en bytes)
                consultation.encrypted_notes = encrypted_notes
                print(f"Notes chiffrées avec succès pour la politique: {consultation.abe_policy}")
            except Exception as e:
                # En cas d'erreur, stocker le message en clair mais avec un préfixe d'erreur
                error_message = f"ERREUR_CHIFFREMENT: {str(e)}\n{notes}"
                consultation.encrypted_notes = error_message.encode('utf-8')
                print(f"Erreur lors du chiffrement ABE : {e}")
        
        if commit:
            consultation.save()
        
        return consultation

# Formulaire pour les patients qui demandent une analyse
class PatientLabTestRequestForm(forms.ModelForm):
    class Meta:
        model = LabTest
        fields = ['test_type', 'description']
        widgets = {
            'test_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Veuillez expliquer pourquoi vous demandez cette analyse'}),
        }
        labels = {
            'test_type': 'Type d\'analyse',
            'description': 'Description / Raison de la demande',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.patient = None
        
        # Récupérer le profil patient de l'utilisateur connecté
        if self.user and hasattr(self.user, 'patient_profile'):
            self.patient = self.user.patient_profile
            
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        lab_test = super().save(commit=False)
        
        # Assigner le patient (l'utilisateur connecté)
        if self.patient:
            lab_test.patient = self.patient
        
        # Définir le statut initial
        lab_test.status = 'PENDING'
        
        # Enregistrer le demandeur (le patient lui-même)
        if self.user:
            lab_test.requested_by = self.user
        
        if commit:
            lab_test.save()
        
        return lab_test

# Formulaire pour une Clé ABE
class ABEKeyForm(forms.ModelForm):
    class Meta:
        model = ABEKey
        fields = ['attributes', 'public_key',  'revoked']
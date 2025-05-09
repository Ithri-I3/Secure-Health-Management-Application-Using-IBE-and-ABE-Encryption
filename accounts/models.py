from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User

from medical_center import settings

class ABEKeyManager(models.Manager):
    def create_abe_key(self, user, attributes):
        # Implémenter la logique de génération de clés ici
        return self.create(user=user, attributes=attributes)

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('L\'adresse email est obligatoire')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')
        
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Administrateur'),
        ('MEDECIN', 'Médecin'),
        ('PATIENT', 'Patient'),
        ('RADIOLOGUE', 'Radiologue'),
        ('LABORANTIN', 'Laborantin'),
        ('PRATICIEN', 'Praticien de santé'),
    )
    
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='PATIENT')
    created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users')
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = UserManager()
    
    def __str__(self):
        return self.email
    
    @property
    def is_admin(self):
        return self.role == 'ADMIN'
    
    @property
    def is_medecin(self):
        return self.role == 'MEDECIN'
    
    @property
    def is_patient(self):
        return self.role == 'PATIENT'
    
    @property
    def is_radiologue(self):
        return self.role == 'RADIOLOGUE'
    
    @property
    def is_laborantin(self):
        return self.role == 'LABORANTIN'
    
    @property
    def is_praticien(self):
        return self.role == 'PRATICIEN'
    
    def get_user_attributes(self):
        """Récupère dynamiquement les attributs de l'utilisateur pour le déchiffrement ABE"""
        attributes = [self.role.lower()]  # Ajoute le rôle comme premier attribut (en minuscules)
        
        # Ajoute des attributs spécifiques en fonction du rôle
        if self.is_medecin and hasattr(self, 'medecin_profile'):
            attributes.append(self.medecin_profile.specialization.lower())
        elif self.is_radiologue and hasattr(self, 'radiologue_profile'):
            attributes.append(self.radiologue_profile.radiology_field.lower())
        elif self.is_laborantin and hasattr(self, 'laborantin_profile'):
            attributes.append(self.laborantin_profile.lab_department.lower())
        
        return attributes
    

class Patient(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_profile'
    )
    date_of_birth = models.DateField()
    blood_type = models.CharField(max_length=3)
    
    encrypted_insurance = models.BinaryField()
    
    

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.email})"


    # Profil spécifique pour les Médecins
class Medecin(models.Model):
        user = models.OneToOneField(
            settings.AUTH_USER_MODEL,
            on_delete=models.CASCADE,
            related_name='medecin_profile'
        )
        specialization = models.CharField(max_length=100)
        phone_number = models.CharField(max_length=20, blank=True)
        # Ajoutez d'autres champs spécifiques aux médecins si nécessaire

        def __str__(self):
            return f"Dr {self.user.first_name} {self.user.last_name} - {self.specialization}"   


    # Profil spécifique pour les Radiologues
class Radiologue(models.Model):
        user = models.OneToOneField(
            settings.AUTH_USER_MODEL,
            on_delete=models.CASCADE,
            related_name='radiologue_profile'
        )
        radiology_field = models.CharField(max_length=100)  # Exemple : imagerie médicale, IRM, etc.
        phone_number = models.CharField(max_length=20, blank=True)
        # Vous pouvez ajouter d'autres informations spécifiques aux radiologues

        def __str__(self):
            return f"Dr {self.user.first_name} {self.user.last_name} - Radiologue ({self.radiology_field})"


    # Profil spécifique pour les Laborantins
class Laborantin(models.Model):
        user = models.OneToOneField(
            settings.AUTH_USER_MODEL,
            on_delete=models.CASCADE,
            related_name='laborantin_profile'
        )
        lab_department = models.CharField(max_length=100)  # Département ou spécialisation en laboratoire
        phone_number = models.CharField(max_length=20, blank=True)
        # Vous pouvez ajouter d'autres informations spécifiques aux laborantins

        def __str__(self):
            return f"{self.user.first_name} {self.user.last_name} - Laborantin ({self.lab_department})"


    # Modèle pour le dossier médical (MedicalRecord)
class MedicalRecord(models.Model):
        patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='records')
        creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_records')
        assigned_to = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='assigned_records')
        encrypted_data = models.BinaryField()
        abe_policy = models.TextField()
        creation_date = models.DateTimeField(auto_now_add=True)
        last_modified = models.DateTimeField(auto_now=True)

        class Meta:
            permissions = [
                ('decrypt_record', 'Can decrypt medical record'),
                ('transfer_record', 'Can transfer record ownership'),
            ]


    # Modèle pour enregistrer les consultations
class Consultation(models.Model):
        patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='consultations')
        professional = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
        date = models.DateTimeField(auto_now_add=True)
        encrypted_notes = models.BinaryField()
        abe_policy = models.TextField()
        follow_up_required = models.BooleanField(default=False)


    # Modèle pour les ordonnances associées à une consultation
class Prescription(models.Model):
        consultation = models.ForeignKey('Consultation', on_delete=models.CASCADE, related_name='prescriptions')
        encrypted_content = models.BinaryField()
        abe_policy = models.TextField()
        issue_date = models.DateField(auto_now_add=True)
        validity_days = models.PositiveIntegerField(default=30)

class ABEKey(models.Model):
        user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='abe_keys')
        attributes = models.JSONField()
        public_key = models.TextField()
        encrypted_private_key = models.BinaryField()
        created_at = models.DateTimeField(auto_now_add=True)
        revoked = models.BooleanField(default=False)

        objects = ABEKeyManager()

# Modèle pour les analyses médicales
class LabTest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'En attente'),
        ('IN_PROGRESS', 'En cours'),
        ('COMPLETED', 'Terminé'),
    )
    
    TEST_TYPE_CHOICES = (
        ('BLOOD', 'Analyse de sang'),
        ('URINE', 'Analyse d\'urine'),
        ('STOOL', 'Analyse de selles'),
        ('BIOPSY', 'Biopsie'),
        ('OTHER', 'Autre'),
    )
    
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='lab_tests')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='requested_tests')
    performed_by = models.ForeignKey('Laborantin', on_delete=models.SET_NULL, null=True, related_name='performed_tests')
    test_type = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES)
    description = models.TextField()
    request_date = models.DateTimeField(auto_now_add=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    encrypted_results = models.BinaryField(null=True, blank=True)
    abe_policy = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"Test {self.test_type} pour {self.patient} - {self.get_status_display()}"

       


        
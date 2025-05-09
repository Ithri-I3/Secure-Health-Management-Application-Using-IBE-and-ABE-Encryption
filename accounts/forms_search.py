from django import forms
from .models import Patient, MedicalRecord, Consultation, Prescription, User

class PatientSearchForm(forms.Form):
    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rechercher par nom, prénom ou email...'}),
        label='Rechercher un patient'
    )
    blood_type = forms.ChoiceField(
        required=False,
        choices=[(None, '---')] + [
            ('A+', 'A+'),
            ('A-', 'A-'),
            ('B+', 'B+'),
            ('B-', 'B-'),
            ('AB+', 'AB+'),
            ('AB-', 'AB-'),
            ('O+', 'O+'),
            ('O-', 'O-'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Groupe sanguin'
    )

class MedicalRecordSearchForm(forms.Form):
    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rechercher par nom du patient...'}),
        label='Rechercher un dossier médical'
    )
    creator = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(role__in=['MEDECIN', 'ADMIN']),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Créé par',
        empty_label='Tous les créateurs'
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Date de création (début)'
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Date de création (fin)'
    )

class ConsultationSearchForm(forms.Form):
    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rechercher par nom du patient...'}),
        label='Rechercher une consultation'
    )
    professional = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(role__in=['MEDECIN', 'PRATICIEN']),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Professionnel',
        empty_label='Tous les professionnels'
    )
    follow_up_required = forms.ChoiceField(
        required=False,
        choices=[(None, 'Tous'), (True, 'Oui'), (False, 'Non')],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Suivi nécessaire'
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Date (début)'
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Date (fin)'
    )

class PrescriptionSearchForm(forms.Form):
    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rechercher par nom du patient...'}),
        label='Rechercher une ordonnance'
    )
    validity_days = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        label='Validité (jours)'
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Date d\'émission (début)'
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Date d\'émission (fin)'
    )
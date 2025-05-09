from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.db import models

from .models import Patient, User, MedicalRecord, Consultation
from .forms import ConsultationForm
from .abe_config import abe_decrypt, abe_encrypt, abe_keygen

# Vue pour afficher la liste des patients pour le radiologue
class PatientListForRadioView(UserPassesTestMixin, ListView):
    model = User
    template_name = 'accounts/patient_list_radio.html'
    context_object_name = 'patients'
    
    def test_func(self):
        # Seuls les radiologues peuvent accéder à cette vue
        return self.request.user.is_radiologue
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(role='PATIENT')
        
        # Recherche par nom de patient
        search_query = self.request.GET.get('search_query')
        if search_query:
            queryset = queryset.filter(
                models.Q(first_name__icontains=search_query) |
                models.Q(last_name__icontains=search_query) |
                models.Q(email__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search_query', '')
        return context

# Vue pour afficher les détails d'un patient pour le radiologue
class PatientDetailForRadioView(UserPassesTestMixin, DetailView):
    model = User
    template_name = 'accounts/patient_detail_radio.html'
    context_object_name = 'patient'
    
    def test_func(self):
        # Seuls les radiologues peuvent accéder à cette vue
        return self.request.user.is_radiologue
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_user = self.get_object()
        
        # Vérifier que l'utilisateur est bien un patient
        if not patient_user.is_patient or not hasattr(patient_user, 'patient_profile'):
            messages.error(self.request, "Cet utilisateur n'est pas un patient ou n'a pas de profil patient.")
            return context
        
        # Récupérer le profil patient
        patient_profile = patient_user.patient_profile
        context['patient_profile'] = patient_profile
        
        # Récupérer les dossiers médicaux du patient
        medical_records = MedicalRecord.objects.filter(patient=patient_profile).order_by('-creation_date')
        context['medical_records'] = medical_records
        
        # Récupérer les consultations du patient
        consultations = Consultation.objects.filter(patient=patient_profile).order_by('-date')
        context['consultations'] = consultations
        
        # Récupérer les examens radiologiques (à implémenter)
        context['radio_exams'] = []
        
        return context

# Vue pour la liste des examens radiologiques
class RadioExamListView(UserPassesTestMixin, ListView):
    model = Consultation  # Utiliser le modèle Consultation en attendant un modèle spécifique
    template_name = 'accounts/radio_exam_list.html'
    context_object_name = 'radio_exams'
    
    def test_func(self):
        # Seuls les radiologues peuvent accéder à cette vue
        return self.request.user.is_radiologue
    
    def get_queryset(self):
        # Filtrer pour n'afficher que les consultations avec des examens radiologiques
        # Pour l'instant, on affiche toutes les consultations
        queryset = super().get_queryset()
        
        # Recherche par nom de patient
        search_query = self.request.GET.get('search_query')
        if search_query:
            queryset = queryset.filter(
                models.Q(patient__user__first_name__icontains=search_query) |
                models.Q(patient__user__last_name__icontains=search_query) |
                models.Q(patient__user__email__icontains=search_query)
            )
        
        return queryset.order_by('-date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search_query', '')
        return context

# Vue pour créer un nouvel examen radiologique (consultation spécifique)
class RadioExamCreateView(UserPassesTestMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'accounts/radio_exam_form.html'
    success_url = reverse_lazy('radio_exam_list')
    
    def test_func(self):
        # Seuls les radiologues peuvent créer des examens
        return self.request.user.is_radiologue
    
    def form_valid(self, form):
        # Assigner le radiologue comme professionnel
        form.instance.professional = self.request.user
        
        # Récupérer les notes du formulaire
        notes = form.cleaned_data.get('notes')
        
        # Récupérer la politique ABE
        abe_policy = form.cleaned_data.get('abe_policy')
        if not abe_policy:
            # Politique par défaut: le patient et les radiologues peuvent accéder
            patient_email = form.instance.patient.user.email
            abe_policy = f"(role:patient AND email:{patient_email}) OR role:radiologue"
        
        # Chiffrer les notes avec ABE
        try:
            # Convertir le contenu (texte) en entier
            message_int = int.from_bytes(notes.encode('utf-8'), 'big')
            
            # Chiffrer les notes
            encrypted_notes = abe_encrypt(message_int, abe_policy)
            
            # Assigner les notes chiffrées et la politique
            form.instance.encrypted_notes = encrypted_notes
            form.instance.abe_policy = abe_policy
        except Exception as e:
            messages.error(self.request, f"Erreur lors du chiffrement: {str(e)}")
            return self.form_invalid(form)
        
        messages.success(self.request, "L'examen radiologique a été créé avec succès.")
        return super().form_valid(form)

# Vue pour afficher les détails d'un examen radiologique
class RadioExamDetailView(UserPassesTestMixin, DetailView):
    model = Consultation
    template_name = 'accounts/radio_exam_detail.html'
    context_object_name = 'radio_exam'
    
    def test_func(self):
        # Seuls les radiologues peuvent voir les détails
        return self.request.user.is_radiologue
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consultation = self.get_object()
        
        # Tenter de déchiffrer les notes
        if consultation.encrypted_notes:
            try:
                # Récupérer les attributs de l'utilisateur pour le déchiffrement ABE
                user_attributes = self.request.user.get_user_attributes()
                
                # Générer la clé privée ABE à partir des attributs
                private_key = abe_keygen(user_attributes)
                
                # Politique ABE utilisée lors du chiffrement
                abe_policy = consultation.abe_policy
                
                # Déchiffrer les notes
                encrypted_data = consultation.encrypted_notes
                decrypted_value = abe_decrypt(encrypted_data, private_key, user_attributes, abe_policy)
                
                # Convertir la valeur déchiffrée en texte
                if decrypted_value and not isinstance(decrypted_value, str):
                    try:
                        decrypted_value = int(decrypted_value)
                        decrypted_notes = decrypted_value.to_bytes((decrypted_value.bit_length() + 7) // 8, 'big').decode('utf-8')
                        context['decrypted_notes'] = decrypted_notes
                    except (ValueError, OverflowError, UnicodeDecodeError) as e:
                        context['decryption_error'] = f"Erreur de conversion: {str(e)}"
                else:
                    decrypted_value = int(decrypted_value)
                    decrypted_results = decrypted_value.to_bytes((decrypted_value.bit_length() + 7) // 8, 'big').decode('utf-8')
                    
                    context['decrypted_notes'] = decrypted_results
            except Exception as e:
                context['decryption_error'] = str(e)
        
        return context

# Vue pour mettre à jour un examen radiologique
class RadioExamUpdateView(UserPassesTestMixin, UpdateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'accounts/radio_exam_form.html'
    success_url = reverse_lazy('radio_exam_list')
    
    def test_func(self):
        # Seuls les radiologues peuvent mettre à jour les examens
        return self.request.user.is_radiologue
    
    def form_valid(self, form):
        # Récupérer les notes du formulaire
        notes = form.cleaned_data.get('notes')
        
        # Récupérer la politique ABE
        abe_policy = form.cleaned_data.get('abe_policy')
        if not abe_policy:
            # Utiliser la politique existante ou en créer une nouvelle
            if form.instance.abe_policy:
                abe_policy = form.instance.abe_policy
            else:
                # Politique par défaut
                patient_email = form.instance.patient.user.email
                abe_policy = f"(role:patient AND email:{patient_email}) OR role:radiologue"
        
        # Chiffrer les notes avec ABE
        try:
            # Convertir le contenu (texte) en entier
            message_int = int.from_bytes(notes.encode('utf-8'), 'big')
            
            # Chiffrer les notes
            encrypted_notes = abe_encrypt(message_int, abe_policy)
            
            # Assigner les notes chiffrées et la politique
            form.instance.encrypted_notes = encrypted_notes
            form.instance.abe_policy = abe_policy
        except Exception as e:
            messages.error(self.request, f"Erreur lors du chiffrement: {str(e)}")
            return self.form_invalid(form)
        
        messages.success(self.request, "L'examen radiologique a été mis à jour avec succès.")
        return super().form_valid(form)
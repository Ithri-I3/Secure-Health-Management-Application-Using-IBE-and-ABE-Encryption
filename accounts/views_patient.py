from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.db import models

from .models import LabTest, Patient, User, MedicalRecord, Prescription, Consultation
from .forms import PatientLabTestRequestForm
from .ibe_config import ibe_decrypt
from .abe_config import abe_keygen, abe_decrypt

# Vue pour le tableau de bord patient
@login_required
def patient_dashboard(request):
    if not request.user.is_patient:
        messages.error(request, "Vous n'avez pas accès à cette page.")
        return redirect('dashboard')
    
    context = {}
    
    # Récupérer le profil patient
    if hasattr(request.user, 'patient_profile'):
        profile = request.user.patient_profile
        context['profile'] = profile
        
        # Déchiffrer le numéro d'assurance
        if profile.encrypted_insurance:
            try:
                insurance_number_decrypted = ibe_decrypt(profile.encrypted_insurance, request.user.email)
                context['insurance_number_decrypted'] = insurance_number_decrypted
            except Exception as e:
                context['insurance_number_decrypted'] = None
        
        # Récupérer les dossiers médicaux
        medical_records = MedicalRecord.objects.filter(patient=profile).order_by('-creation_date')[:5]
        context['medical_records'] = medical_records
        context['medical_records_count'] = MedicalRecord.objects.filter(patient=profile).count()
        
        # Récupérer les ordonnances
        prescriptions = Prescription.objects.filter(
            consultation__patient=profile
        ).order_by('-issue_date')[:5]
        context['prescriptions'] = prescriptions
        context['prescriptions_count'] = Prescription.objects.filter(consultation__patient=profile).count()
        
        # Récupérer les analyses
        lab_tests = LabTest.objects.filter(patient=profile).order_by('-request_date')[:5]
        context['lab_tests'] = lab_tests
        context['lab_tests_count'] = LabTest.objects.filter(patient=profile).count()
        
        # Récupérer les examens radiologiques
        radio_exams = Consultation.objects.filter(
            patient=profile,
            professional__role='RADIOLOGUE'
        ).order_by('-date')[:5]
        context['radio_exams'] = radio_exams
        context['radio_exams_count'] = Consultation.objects.filter(
            patient=profile,
            professional__role='RADIOLOGUE'
        ).count()
        
        # Vérifier s'il y a des analyses avec des résultats récemment ajoutés
        recent_completed_tests = LabTest.objects.filter(
            patient=profile, 
            status='COMPLETED',
            completion_date__isnull=False
        ).order_by('-completion_date')[:3]
        
        context['recent_completed_tests'] = recent_completed_tests
    else:
        messages.warning(request, "Votre profil patient n'est pas complet.")
    
    return render(request, 'accounts/patient_dashboard.html', context)

# Vue pour afficher la liste des analyses du patient
class PatientLabTestListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = LabTest
    template_name = 'accounts/patient_labtest_list.html'
    context_object_name = 'lab_tests'
    
    def test_func(self):
        # Seuls les patients peuvent accéder à cette vue
        return self.request.user.is_patient
    
    def get_queryset(self):
        # Filtrer pour n'afficher que les analyses du patient connecté
        if hasattr(self.request.user, 'patient_profile'):
            queryset = LabTest.objects.filter(patient=self.request.user.patient_profile)
            
            # Filtrer selon le statut si spécifié
            status_filter = self.request.GET.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            return queryset.order_by('-request_date')
        return LabTest.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['status_choices'] = LabTest.STATUS_CHOICES
        return context

# Vue pour afficher les détails d'une analyse pour un patient
class PatientLabTestDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = LabTest
    template_name = 'accounts/patient_labtest_detail.html'
    context_object_name = 'lab_test'
    
    def test_func(self):
        # Vérifier que l'utilisateur est un patient et que l'analyse lui appartient
        lab_test = self.get_object()
        return (self.request.user.is_patient and 
                hasattr(self.request.user, 'patient_profile') and 
                lab_test.patient == self.request.user.patient_profile)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lab_test = self.get_object()
        
        # Tenter de déchiffrer les résultats si disponibles
        if lab_test.encrypted_results:
            try:
                # Récupérer les attributs de l'utilisateur pour le déchiffrement ABE
                user_attributes = self.request.user.get_user_attributes()
                user_attributes.append(f"email:{self.request.user.email}")
                
                # Générer la clé privée ABE à partir des attributs
                from .abe_config import abe_keygen, abe_decrypt
                private_key = abe_keygen(user_attributes)
                
                # Récupérer la politique ABE stockée ou utiliser une politique par défaut
                abe_policy = lab_test.abe_policy
                if not abe_policy:
                    abe_policy = f"(role:patient AND email:{self.request.user.email}) OR role:laborantin"
                
                # Déchiffrer les résultats
                encrypted_data = lab_test.encrypted_results
                # Passer directement les données chiffrées à abe_decrypt qui gère maintenant tous les types
                decrypted_value = abe_decrypt(encrypted_data, private_key, user_attributes, abe_policy)
                
                # Convertir la valeur déchiffrée en texte
                if decrypted_value and not isinstance(decrypted_value, str):
                    try:
                        decrypted_value = int(decrypted_value)
                        decrypted_results = decrypted_value.to_bytes((decrypted_value.bit_length() + 7) // 8, 'big').decode('utf-8')
                        context['decrypted_results'] = decrypted_results
                    except (ValueError, OverflowError, UnicodeDecodeError) as e:
                        context['decryption_error'] = f"Erreur de conversion: {str(e)}"
                else:
                    decrypted_value = int(decrypted_value)
                    decrypted_results = decrypted_value.to_bytes((decrypted_value.bit_length() + 7) // 8, 'big').decode('utf-8')
                    context['decrypted_results'] = decrypted_results
                    
            except Exception as e:
                context['decryption_error'] = str(e)
        
        return context

# Vue pour demander une nouvelle analyse
class PatientLabTestRequestView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = LabTest
    form_class = PatientLabTestRequestForm
    template_name = 'accounts/patient_labtest_request.html'
    success_url = reverse_lazy('patient_labtest_list')
    
    def test_func(self):
        # Seuls les patients peuvent demander une analyse
        return self.request.user.is_patient and hasattr(self.request.user, 'patient_profile')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['test_type_choices'] = LabTest.TEST_TYPE_CHOICES
        return context
    
    def form_valid(self, form):
        messages.success(self.request, "Votre demande d'analyse a été soumise avec succès. Vous serez notifié lorsque les résultats seront disponibles.")
        return super().form_valid(form)

# Vue pour afficher la liste des examens radiologiques du patient
class PatientRadioExamListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Consultation
    template_name = 'accounts/patient_radioexam_list.html'
    context_object_name = 'radio_exams'
    
    def test_func(self):
        # Seuls les patients peuvent accéder à cette vue
        return self.request.user.is_patient
    
    def get_queryset(self):
        # Filtrer pour n'afficher que les examens radiologiques du patient connecté
        if hasattr(self.request.user, 'patient_profile'):
            queryset = Consultation.objects.filter(
                patient=self.request.user.patient_profile,
                professional__role='RADIOLOGUE'
            )
            
            # Filtrer selon la date si spécifiée
            date_filter = self.request.GET.get('date')
            if date_filter:
                try:
                    date_obj = timezone.datetime.strptime(date_filter, '%Y-%m-%d').date()
                    queryset = queryset.filter(date__date=date_obj)
                except ValueError:
                    pass
            
            return queryset.order_by('-date')
        return Consultation.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_filter'] = self.request.GET.get('date', '')
        return context

# Vue pour afficher les détails d'un examen radiologique pour un patient
class PatientRadioExamDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Consultation
    template_name = 'accounts/patient_radioexam_detail.html'
    context_object_name = 'radio_exam'
    
    def test_func(self):
        # Vérifier que l'utilisateur est un patient et que l'examen lui appartient
        consultation = self.get_object()
        return (self.request.user.is_patient and 
                hasattr(self.request.user, 'patient_profile') and 
                consultation.patient == self.request.user.patient_profile and
                consultation.professional.role == 'RADIOLOGUE')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consultation = self.get_object()
        
        # Tenter de déchiffrer les notes si disponibles
        if consultation.encrypted_notes:
            try:
                # Récupérer les attributs de l'utilisateur pour le déchiffrement ABE
                user_attributes = self.request.user.get_user_attributes()
                user_attributes.append(f"email:{self.request.user.email}")
                
                # Générer la clé privée ABE à partir des attributs
                private_key = abe_keygen(user_attributes)
                
                # Récupérer la politique ABE stockée ou utiliser une politique par défaut
                abe_policy = consultation.abe_policy
                if not abe_policy:
                    abe_policy = f"(role:patient AND email:{self.request.user.email}) OR role:radiologue"
                
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
                    decrypted_notes = decrypted_value.to_bytes((decrypted_value.bit_length() + 7) // 8, 'big').decode('utf-8')
                    context['decrypted_notes'] = decrypted_notes
                    
            except Exception as e:
                context['decryption_error'] = str(e)
        
        return context

# Vue pour afficher la liste des examens radiologiques du patient
class PatientRadioExamListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Consultation
    template_name = 'accounts/patient_radioexam_list.html'
    context_object_name = 'radio_exams'
    
    def test_func(self):
        # Seuls les patients peuvent accéder à cette vue
        return self.request.user.is_patient
    
    def get_queryset(self):
        # Filtrer pour n'afficher que les examens radiologiques du patient connecté
        if hasattr(self.request.user, 'patient_profile'):
            queryset = Consultation.objects.filter(
                patient=self.request.user.patient_profile,
                professional__role='RADIOLOGUE'
            )
            
            # Filtrer selon la date si spécifiée
            date_filter = self.request.GET.get('date')
            if date_filter:
                try:
                    date_obj = timezone.datetime.strptime(date_filter, '%Y-%m-%d').date()
                    queryset = queryset.filter(date__date=date_obj)
                except ValueError:
                    pass
            
            return queryset.order_by('-date')
        return Consultation.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_filter'] = self.request.GET.get('date', '')
        return context

# Vue pour afficher les détails d'un examen radiologique pour un patient
class PatientRadioExamDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Consultation
    template_name = 'accounts/patient_radioexam_detail.html'
    context_object_name = 'radio_exam'
    
    def test_func(self):
        # Vérifier que l'utilisateur est un patient et que l'examen lui appartient
        consultation = self.get_object()
        return (self.request.user.is_patient and 
                hasattr(self.request.user, 'patient_profile') and 
                consultation.patient == self.request.user.patient_profile and
                consultation.professional.role == 'RADIOLOGUE')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consultation = self.get_object()
        
        # Tenter de déchiffrer les notes si disponibles
        if consultation.encrypted_notes:
            try:
                # Récupérer les attributs de l'utilisateur pour le déchiffrement ABE
                user_attributes = self.request.user.get_user_attributes()
                user_attributes.append(f"email:{self.request.user.email}")
                
                # Générer la clé privée ABE à partir des attributs
                private_key = abe_keygen(user_attributes)
                
                # Récupérer la politique ABE stockée ou utiliser une politique par défaut
                abe_policy = consultation.abe_policy
                if not abe_policy:
                    abe_policy = f"(role:patient AND email:{self.request.user.email}) OR role:radiologue"
                
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
                    decrypted_notes = decrypted_value.to_bytes((decrypted_value.bit_length() + 7) // 8, 'big').decode('utf-8')
                    context['decrypted_notes'] = decrypted_notes
                    
            except Exception as e:
                context['decryption_error'] = str(e)
        
        return context
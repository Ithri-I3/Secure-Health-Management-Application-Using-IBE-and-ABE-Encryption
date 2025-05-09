from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.db import models

from .models import LabTest, Patient, User
from .forms import LabTestForm, LabTestResultForm
from .ibe_config import ibe_decrypt

# Vue pour afficher la liste des analyses de laboratoire
class LabTestListView(UserPassesTestMixin, ListView):
    model = LabTest
    template_name = 'accounts/labtest_list.html'
    context_object_name = 'lab_tests'
    
    def test_func(self):
        # Seuls les laborantins peuvent accéder à cette vue
        return self.request.user.is_laborantin
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrer selon le statut si spécifié
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Recherche par nom de patient
        search_query = self.request.GET.get('search_query')
        if search_query:
            queryset = queryset.filter(
                models.Q(patient__user__first_name__icontains=search_query) |
                models.Q(patient__user__last_name__icontains=search_query) |
                models.Q(patient__user__email__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search_query', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['status_choices'] = LabTest.STATUS_CHOICES
        return context

# Vue pour afficher les détails d'une analyse
class LabTestDetailView(UserPassesTestMixin, DetailView):
    model = LabTest
    template_name = 'accounts/labtest_detail.html'
    context_object_name = 'lab_test'
    
    def test_func(self):
        # Seuls les laborantins et les médecins peuvent accéder à cette vue
        return self.request.user.is_laborantin or self.request.user.is_medecin
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lab_test = self.get_object()
        
        # Tenter de déchiffrer les résultats si disponibles
        if lab_test.encrypted_results:
            try:
                # Récupérer les attributs de l'utilisateur pour le déchiffrement ABE
                user_attributes = self.request.user.get_user_attributes()
                
                # Générer la clé privée ABE à partir des attributs
                from .abe_config import abe_keygen, abe_decrypt
                private_key = abe_keygen(user_attributes)
                
                # Politique ABE utilisée lors du chiffrement
                abe_policy = lab_test.abe_policy
                print("helloooooooooooooooooooooooooooooooooooooooooooooooooooooooooo")
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

# Vue pour créer une nouvelle analyse
class LabTestCreateView(UserPassesTestMixin, CreateView):
    model = LabTest
    form_class = LabTestForm
    template_name = 'accounts/labtest_form.html'
    success_url = reverse_lazy('labtest_list')
    
    def test_func(self):
        # Seuls les médecins peuvent créer des analyses
        return self.request.user.is_medecin
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, "L'analyse a été créée avec succès.")
        return super().form_valid(form)

# Vue pour mettre à jour les résultats d'une analyse
class LabTestUpdateView(UserPassesTestMixin, UpdateView):
    model = LabTest
    form_class = LabTestResultForm
    template_name = 'accounts/labtest_result_form.html'
    success_url = reverse_lazy('labtest_list')
    
    def test_func(self):
        # Seuls les laborantins peuvent mettre à jour les résultats
        return self.request.user.is_laborantin
    
    def form_valid(self, form):
        # Ne pas sauvegarder immédiatement pour pouvoir modifier l'objet
        lab_test = form.save(commit=False)
        
        # Assigner le laborantin qui a effectué l'analyse
        if self.request.user.is_laborantin and hasattr(self.request.user, 'laborantin_profile'):
            try:
                lab_test.performed_by = self.request.user.laborantin_profile
                print(f"Laborantin assigné: {self.request.user.laborantin_profile}")
            except Exception as e:
                print(f"Erreur lors de l'assignation du laborantin: {str(e)}")
        
        # Récupérer les résultats du formulaire
        results = form.cleaned_data.get('results')
        
        # Vérifier si le statut passe à COMPLETED pour notifier le patient
        is_completed = lab_test.status == 'COMPLETED'
        
        try:
            # Chiffrer les résultats avec ABE si le patient existe
            if results and lab_test.patient and lab_test.patient.user:
                patient_user = lab_test.patient.user
                
                try:
                    # Utiliser ABE pour chiffrer les résultats
                    from .abe_config import abe_encrypt
                    
                    # Convertir le contenu (texte) en entier
                    message_int = int.from_bytes(results.encode('utf-8'), 'big')
                    
                    # Récupérer la politique ABE saisie dans le formulaire
                    abe_policy = form.cleaned_data.get('abe_policy')
                    
                    # Si aucune politique n'est fournie, utiliser une politique par défaut
                    if not abe_policy:
                        abe_policy = f"(role:patient AND email:{patient_user.email}) OR role:laborantin"
                    
                    # Enregistrer la politique ABE dans l'objet lab_test
                    lab_test.abe_policy = abe_policy
                    
                    # Chiffrer les résultats
                    encrypted_results = abe_encrypt(message_int, abe_policy)
                    
                    # Assigner les résultats chiffrés à l'objet lab_test
                    lab_test.encrypted_results = encrypted_results
                    print(f"Résultats chiffrés avec succès pour la politique: {abe_policy}")
                except Exception as e:
                    # En cas d'erreur, stocker le message en clair mais avec un préfixe d'erreur
                    error_message = f"ERREUR_CHIFFREMENT: {str(e)}\n{results}"
                    lab_test.encrypted_results = error_message.encode('utf-8')
                    print(f"Erreur lors du chiffrement ABE : {e}")
                
                # Si le statut est 'COMPLETED', enregistrer la date de complétion
                if is_completed:
                    from django.utils import timezone
                    lab_test.completion_date = timezone.now()
            
            # Sauvegarder l'objet lab_test avec les modifications
            lab_test.save()
            
            messages.success(self.request, "Les résultats d'analyse ont été enregistrés avec succès.")
            
            # Notifier le patient si l'analyse est complétée
            if is_completed and lab_test.patient and lab_test.patient.user:
                # Créer un message de notification pour le patient
                patient_user = lab_test.patient.user
                messages.add_message(
                    self.request,
                    messages.SUCCESS,
                    f"Le patient {patient_user.get_full_name()} a été notifié que les résultats de son analyse sont disponibles."
                )
                
                # Dans un système réel, on pourrait envoyer un email ou une notification push ici
                # Exemple: send_email_notification(patient_user.email, "Résultats d'analyse disponibles")
            
            # Retourner la réponse de redirection vers success_url
            return super(UpdateView, self).form_valid(form)
            
        except Exception as e:
            messages.error(self.request, f"Erreur lors de l'enregistrement des résultats: {str(e)}")
            print(f"Erreur lors de l'enregistrement des résultats: {str(e)}")
            return self.form_invalid(form)

# Vue pour afficher la liste des patients pour les laborantins
class PatientListForLabView(UserPassesTestMixin, ListView):
    model = User
    template_name = 'accounts/patient_list_lab.html'
    context_object_name = 'patients'
    
    def test_func(self):
        # Seuls les laborantins peuvent accéder à cette vue
        return self.request.user.is_laborantin
    
    def get_queryset(self):
        # Filtrer pour n'afficher que les patients
        queryset = super().get_queryset().filter(role='PATIENT')
        
        # Recherche par nom ou email
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

# Vue pour afficher les détails d'un patient pour les laborantins
class PatientDetailForLabView(UserPassesTestMixin, DetailView):
    model = User
    template_name = 'accounts/patient_detail_lab.html'
    context_object_name = 'patient'
    
    def test_func(self):
        # Seuls les laborantins peuvent accéder à cette vue
        return self.request.user.is_laborantin
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_user = self.get_object()
        
        # Récupérer les analyses de ce patient
        if hasattr(patient_user, 'patient_profile'):
            try:
                context['lab_tests'] = LabTest.objects.filter(patient=patient_user.patient_profile)
                print(f"Analyses trouvées pour {patient_user.email}: {context['lab_tests'].count()}")
            except Exception as e:
                messages.error(self.request, f"Erreur lors de la récupération des analyses: {str(e)}")
                context['lab_tests'] = []
                print(f"Erreur lors de la récupération des analyses: {str(e)}")
        else:
            # Si l'utilisateur n'a pas de profil patient, ajouter un message d'erreur
            messages.error(self.request, f"L'utilisateur {patient_user.email} n'a pas de profil patient.")
            context['lab_tests'] = []
            print(f"Aucun profil patient trouvé pour {patient_user.email}")
        
        return context
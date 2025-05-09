from re import I
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import CreateView, ListView, UpdateView, DetailView, DeleteView
from django.urls import reverse_lazy
from django.db import models
from .forms import ConsultationForm, LaborantinForm, LoginForm, MedecinForm, MedicalRecordForm, PatientForm, RadiologueForm, UserCreationForm,PrescriptionForm
from .models import User, MedicalRecord, Patient, Consultation,Prescription
from django.contrib import messages
from django.http import Http404, HttpResponseForbidden
from .ibe_config import ibe_decrypt
from .abe_config import abe_decrypt,abe_keygen


import json



class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = 'accounts/login.html'

@login_required
def dashboard(request):
    return render(request, 'accounts/dashboard.html')

from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    # Clear any session data
    request.session.flush()
    # Redirect to login page
    return redirect('login')

PROFILE_FORMS = {
    'patient': PatientForm,
    'medecin': MedecinForm,
    'radiologue': RadiologueForm,
    'laborantin': LaborantinForm,
}

class UserCreateView(UserPassesTestMixin, CreateView):
    model = User
    form_class = UserCreationForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('user_list')

    def test_func(self):
        # Seuls admins, médecins et praticiens peuvent créer des utilisateurs
        return self.request.user.is_admin or self.request.user.is_medecin or self.request.user.is_praticien

    def dispatch(self, request, *args, **kwargs):
        # Récupère le type de profil dans l'URL ; par défaut, "user" signifie sans profil additionnel
        self.profile_type = kwargs.get('profile_type', 'user')
        if self.profile_type != 'user' and self.profile_type not in PROFILE_FORMS:
            raise Http404("Type de profil non trouvé.")
        if self.profile_type != 'user':
            self.profile_form_class = PROFILE_FORMS[self.profile_type]
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Si le profil n'est pas "user", ajouter le formulaire spécifique en lui passant éventuellement l'utilisateur
        if self.profile_type != 'user':
            if self.request.POST:
                # On pourra par exemple passer l'utilisateur ici si nécessaire
                context['profile_form'] = self.profile_form_class(self.request.POST, user=self.request.user)
            else:
                context['profile_form'] = self.profile_form_class(user=self.request.user)
        context['profile_type'] = self.profile_type
        return context

    def form_valid(self, form):
        # Création de l'utilisateur
        user = form.save(commit=False)
        user.created_by = self.request.user

        # Vérification des permissions de création
        if (self.request.user.is_medecin or self.request.user.is_praticien) and user.role != 'PATIENT':
            messages.error(self.request, "Vous ne pouvez créer que des patients.")
            return self.form_invalid(form)
        if self.request.user.is_radiologue or self.request.user.is_laborantin:
            messages.error(self.request, "Vous n'avez pas les permissions pour créer des utilisateurs.")
            return self.form_invalid(form)
        user.save()

        # Si un profil additionnel doit être créé, le traiter
        if self.profile_type != 'user':
            # On passe l'utilisateur nouvellement créé au formulaire de profil
            profile_form = self.profile_form_class(self.request.POST, user=user)
            if profile_form.is_valid():
                profile = profile_form.save(commit=False)
                profile.user = user
                profile.save()
            else:
                messages.error(self.request, "Erreur lors de la création du profil.")
                return self.form_invalid(form)

        if self.profile_type != 'user':
            messages.success(
                self.request,
                f"L'utilisateur {user.email} et son profil {self.profile_type} ont été créés avec succès."
            )
        else:
            messages.success(
                self.request,
                f"L'utilisateur {user.email} a été créé avec succès."
            )
        return super().form_valid(form)


class UserListView(UserPassesTestMixin, ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    
    def test_func(self):
        # Définir qui peut voir la liste des utilisateurs
        return (self.request.user.is_admin or 
                self.request.user.is_medecin or 
                self.request.user.is_radiologue or 
                self.request.user.is_laborantin or 
                self.request.user.is_praticien)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Appliquer les filtres de recherche
        search_query = self.request.GET.get('search_query')
        if search_query:
            queryset = queryset.filter(
                models.Q(email__icontains=search_query) |
                models.Q(first_name__icontains=search_query) |
                models.Q(last_name__icontains=search_query)
            )
        
        # Filtrer selon le rôle
        if self.request.user.is_medecin:
            # Les médecins voient tous les patients
            queryset = queryset.filter(role='PATIENT')
        elif self.request.user.is_radiologue:
            # Les radiologues voient tous les patients
            queryset = queryset.filter(role='PATIENT')
        elif self.request.user.is_laborantin:
            # Les laborantins voient tous les patients
            queryset = queryset.filter(role='PATIENT')
        elif self.request.user.is_praticien:
            # Les praticiens voient tous les patients
            queryset = queryset.filter(role='PATIENT')
        
        # Les admins voient tout le monde
        return queryset
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search_query', '')
        return context


class UserDeleteView(UserPassesTestMixin, DeleteView):
    model = User
    template_name = 'accounts/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')
    
    def test_func(self):
        # Vérifier si l'utilisateur a le droit de supprimer
        user_to_delete = self.get_object()
        
        # L'admin peut supprimer n'importe quel compte
        if self.request.user.is_admin:
            return True
            
        # Un médecin peut supprimer uniquement les patients qu'il a créés
        if self.request.user.is_medecin and user_to_delete.is_patient and user_to_delete.created_by == self.request.user:
            return True
            
        # Un praticien peut supprimer uniquement les patients qu'il a créés
        if self.request.user.is_praticien and user_to_delete.is_patient and user_to_delete.created_by == self.request.user:
            return True
            
        return False
    
    def delete(self, request, *args, **kwargs):
        user_to_delete = self.get_object()
        messages.success(request, f"L'utilisateur {user_to_delete.email} a été supprimé avec succès.")
        return super().delete(request, *args, **kwargs)
    



from django.views.generic import DetailView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.http import Http404, HttpResponseForbidden

from .models import User, Patient, Medecin, Radiologue, Laborantin


class UserDetailView(UserPassesTestMixin, DetailView):
    model = User
    template_name = 'accounts/user_detail.html'
    context_object_name = 'user_object'  # Évite la confusion avec request.user
    

    def test_func(self):
        user_to_view = self.get_object()
        print(f"Utilisateur connecté: {self.request.user}, Profil demandé: {user_to_view}")
        # Autorisations : admin, utilisateur lui-même ou professionnels de santé
        if self.request.user.is_admin:
            return True
        if self.request.user == user_to_view:
            return True
        if (self.request.user.is_medecin or self.request.user.is_praticien or
            self.request.user.is_radiologue or self.request.user.is_laborantin ):
            return True
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_object = self.get_object()

        # Ajout des attributs d'utilisateur (exemple)
        user_attributes = []
        if self.request.user.is_admin:
            user_attributes.append("ADMIN")
        if self.request.user.is_medecin:
            user_attributes.append("MEDECIN")
        if self.request.user.is_praticien:
            user_attributes.append("PRATICIEN")
        if self.request.user.is_radiologue:
            user_attributes.append("RADIOLOGUE")
        if self.request.user.is_laborantin:
            user_attributes.append("LABORANTIN")

        context['user_attributes'] = user_attributes

        # Si l'utilisateur affiché est un patient avec un profil patient, tenter de déchiffrer l'assurance
        if user_object.is_patient and hasattr(user_object, 'patient_profile'):
            patient_profile = user_object.patient_profile
            context['profile'] = patient_profile
            if user_object.email != self.request.user.email:
                context['insurance_number_decrypted']="Vous n'êtes pas autorisé à voir cet utilisateur."
                return context
            encrypted_insurance = patient_profile.encrypted_insurance

            insurance_number_decrypted = None

            if encrypted_insurance:
                try:
                    
                    insurance_number_decrypted = ibe_decrypt(encrypted_insurance, self.request.user.email)
                except Exception as e:
                    insurance_number_decrypted = f"Erreur lors du déchiffrement : {str(e)}"

            context['insurance_number_decrypted'] = insurance_number_decrypted

        return context



        


class UserUpdateView(UserPassesTestMixin, UpdateView):
        model = User
        form_class = UserCreationForm  # Remplacez par UserUpdateForm si disponible
        template_name = 'accounts/user_form.html'
        success_url = reverse_lazy('user_list')

        def test_func(self):
            # Seuls admins, médecins et praticiens peuvent modifier des utilisateurs
            return self.request.user.is_admin or self.request.user.is_medecin or self.request.user.is_praticien

        def dispatch(self, request, *args, **kwargs):
            # Récupère le type de profil dans l'URL ; par défaut, "user" signifie sans profil additionnel
            self.profile_type = kwargs.get('profile_type', 'user')
            if self.profile_type != 'user' and self.profile_type not in PROFILE_FORMS:
                raise Http404("Type de profil non trouvé.")
            if self.profile_type != 'user':
                self.profile_form_class = PROFILE_FORMS[self.profile_type]
            return super().dispatch(request, *args, **kwargs)

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            # Si un profil additionnel doit être modifié, récupérez l'instance correspondante
            if self.profile_type != 'user':
                if self.request.POST:
                    context['profile_form'] = self.profile_form_class(
                        self.request.POST,
                        instance=getattr(self.object, f"{self.profile_type.lower()}_profile", None)
                    )
                else:
                    context['profile_form'] = self.profile_form_class(
                        instance=getattr(self.object, f"{self.profile_type.lower()}_profile", None)
                    )
            context['profile_type'] = self.profile_type
            return context

        def form_valid(self, form):
            user = form.save(commit=False)
            user.created_by = self.request.user

            # Vérification des permissions (exemple, ajustez si nécessaire)
            if (self.request.user.is_medecin or self.request.user.is_praticien) and user.role != 'PATIENT':
                messages.error(self.request, "Vous ne pouvez modifier que des patients.")
                return self.form_invalid(form)
            if self.request.user.is_radiologue or self.request.user.is_laborantin:
                messages.error(self.request, "Vous n'avez pas les permissions pour modifier des utilisateurs.")
                return self.form_invalid(form)

            user.save()

            # Mise à jour du profil additionnel s'il existe
            if self.profile_type != 'user':
                try:
                    profile_instance = getattr(user, f"{self.profile_type.lower()}_profile")
                except AttributeError:
                    profile_instance = None

                profile_form = self.profile_form_class(self.request.POST, instance=profile_instance)
                if profile_form.is_valid():
                    profile = profile_form.save(commit=False)
                    profile.user = user
                    profile.save()
                else:
                    messages.error(self.request, "Erreur lors de la modification du profil.")
                    return self.form_invalid(form)

            if self.profile_type != 'user':
                messages.success(
                    self.request,
                    f"L'utilisateur {user.email} et son profil {self.profile_type} ont été modifiés avec succès."
                )
            else:
                messages.success(
                    self.request,
                    f"L'utilisateur {user.email} a été modifié avec succès."
                )
            return super().form_valid(form)


# Vues pour la gestion des dossiers médicaux
class MedicalRecordListView(UserPassesTestMixin, ListView):
    model = MedicalRecord
    template_name = 'accounts/medical_record_list.html'
    context_object_name = 'medical_records'
    
    def test_func(self):
        # Les médecins, les administrateurs, les praticiens et les laborantins peuvent voir la liste des dossiers médicaux
        return self.request.user.is_admin or self.request.user.is_medecin or self.request.user.is_praticien or self.request.user.is_laborantin
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Appliquer les filtres de recherche
        form = self.search_form
        if form.is_valid():
            search_query = form.cleaned_data.get('search_query')
            creator = form.cleaned_data.get('creator')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            
            if search_query:
                queryset = queryset.filter(
                    models.Q(patient__user__first_name__icontains=search_query) |
                    models.Q(patient__user__last_name__icontains=search_query) |
                    models.Q(patient__user__email__icontains=search_query)
                )
            
            if creator:
                queryset = queryset.filter(creator=creator)
            
            if date_from:
                queryset = queryset.filter(creation_date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(creation_date__lte=date_to)
        
        # Les médecins voient les dossiers qu'ils ont créés et ceux auxquels ils sont assignés
        if self.request.user.is_medecin:
            queryset = queryset.filter(
                models.Q(creator=self.request.user) | models.Q(assigned_to=self.request.user)
            ).distinct()
        
        # Les laborantins voient les dossiers auxquels ils sont assignés
        elif self.request.user.is_laborantin:
            queryset = queryset.filter(assigned_to=self.request.user).distinct()
        
        # Les administrateurs voient tous les dossiers
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = self.search_form
        return context
    
    def dispatch(self, request, *args, **kwargs):
        from .forms_search import MedicalRecordSearchForm
        self.search_form = MedicalRecordSearchForm(request.GET or None)
        return super().dispatch(request, *args, **kwargs)


class MedicalRecordDetailView(UserPassesTestMixin, DetailView):
    model = MedicalRecord
    template_name = 'accounts/medical_record_detail.html'
    context_object_name = 'record'
    
    def test_func(self):
        record = self.get_object()
        # Vérifier si l'utilisateur a le droit de voir ce dossier
        if self.request.user.is_admin:
            return True
        if self.request.user == record.creator:
            return True
        if self.request.user in record.assigned_to.all():
            return True
        # Les laborantins peuvent voir les dossiers médicaux auxquels ils sont assignés
        # (cette condition est déjà couverte par la condition précédente, mais on l'explicite pour plus de clarté)
        if self.request.user.is_laborantin and self.request.user in record.assigned_to.all():

            return True
        if self.request.user == record.patient.user:
            return True
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.get_object()
        
        # Récupérer dynamiquement les attributs ABE de l'utilisateur
        user_attributes = self.request.user.get_user_attributes()
        print(f"DEBUG: Attributs utilisateur: {user_attributes}")
        # Générer la clé privée ABE à partir des attributs
        private_key = abe_keygen(user_attributes)
        # Récupérer la politique ABE associée à ce dossier médical
        policy_str = record.abe_policy
        print(f"DEBUG: Politique ABE: {policy_str}")
        
        # Tenter de déchiffrer les données médicales
        decrypted_data = None
        try:
            if record.encrypted_data:
                # On souhaite toujours passer une chaîne JSON à abe_decrypt
                if isinstance(record.encrypted_data, bytes):
                    encrypted_str = record.encrypted_data.decode("utf-8")
                elif isinstance(record.encrypted_data, str):
                    encrypted_str = record.encrypted_data
                elif isinstance(record.encrypted_data, dict):
                    encrypted_str = json.dumps(record.encrypted_data)
                else:
                    raise ValueError("Format de encrypted_data inconnu.")
                
                # Pour vérifier que la chaîne correspond bien à un dictionnaire attendu
                try:
                    data = json.loads(encrypted_str)
                    print("DEBUG: Type de data après json.loads:", type(data))
                except Exception as ex:
                    print("DEBUG: Erreur lors du json.loads:", ex)
                
                # Appeler abe_decrypt en lui fournissant la chaîne JSON
                decrypted_value = abe_decrypt(
                    encrypted_str,
                    private_key,
                    user_attributes,
                    policy_str
                )
                decrypted_value = int(decrypted_value)
                decrypted_data = decrypted_value.to_bytes(100000000, 'big').decode('utf-8')
        except Exception as e:
            error_message = f"Erreur lors du déchiffrement ABE : {e}. "
            print(error_message)
            decrypted_data = None
        
        context['decrypted_data'] = decrypted_data
        
        # Récupérer les consultations associées au patient
        context['consultations'] = Consultation.objects.filter(patient=record.patient)
        
        # Tenter de déchiffrer le numéro d'assurance du patient
        insurance_number_decrypted = None
        if record.patient.encrypted_insurance:
            try:
                insurance_number_decrypted = ibe_decrypt(record.patient.encrypted_insurance, record.patient.user.email)
            except Exception as e:
                insurance_number_decrypted = None
        
        context['insurance_number_decrypted'] = insurance_number_decrypted
        
        return context


class MedicalRecordCreateView(UserPassesTestMixin, CreateView):
    model = MedicalRecord
    form_class = MedicalRecordForm
    template_name = 'accounts/medical_record_form.html'
    success_url = reverse_lazy('medical_record_list')
    
    def test_func(self):
        # Seuls les médecins et les administrateurs peuvent créer des dossiers médicaux
        return self.request.user.is_admin or self.request.user.is_medecin
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Récupérer tous les professionnels de santé pour l'assignation
        context['professionals'] = User.objects.filter(
            models.Q(role='MEDECIN') | models.Q(role='RADIOLOGUE') | 
            models.Q(role='LABORANTIN') | models.Q(role='PRATICIEN')
        )
        return context
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.is_authenticated:
            kwargs['user'] = self.request.user
        return kwargs
        
    def form_valid(self, form):
        record = form.save(commit=False)
        record.creator = self.request.user
        
        # Le chiffrement des données médicales est maintenant géré dans le formulaire
        # avec la méthode abe_encrypt, similaire à ce qui est fait pour Prescription
        record = form.save()
        
        # Gérer les professionnels assignés
        assigned_professionals = self.request.POST.getlist('assigned_to')
        record.assigned_to.set(assigned_professionals)
        
        messages.success(self.request, "Le dossier médical a été créé avec succès.")
        return super().form_valid(form)


class MedicalRecordUpdateView(UserPassesTestMixin, UpdateView):
    model = MedicalRecord
    form_class = MedicalRecordForm
    template_name = 'accounts/medical_record_form.html'
    context_object_name = 'record'
    
    def test_func(self):
        record = self.get_object()
        # Vérifier si l'utilisateur a le droit de modifier ce dossier
        if self.request.user.is_admin:
            return True
        if self.request.user == record.creator:
            return True
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.get_object()
        
        # Récupérer tous les professionnels de santé pour l'assignation
        context['professionals'] = User.objects.filter(
            models.Q(role='MEDECIN') | models.Q(role='RADIOLOGUE') | 
            models.Q(role='LABORANTIN') | models.Q(role='PRATICIEN')
        )
        
        # Tenter de déchiffrer les données médicales pour les afficher dans le formulaire
        try:
            # Ici, vous devriez utiliser la fonction de déchiffrement ABE appropriée
            # medical_data = abe_decrypt(record.encrypted_data, self.request.user)
            medical_data = record.encrypted_data.decode('utf-8')  # Pour l'exemple
            context['medical_data'] = medical_data
        except Exception as e:
            context['medical_data'] = ''
            messages.error(self.request, "Impossible de déchiffrer les données médicales.")
        
        return context
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.is_authenticated:
            kwargs['user'] = self.request.user
        return kwargs
        
    def form_valid(self, form):
        record = form.save(commit=False)
        
        # Le chiffrement des données médicales est maintenant géré dans le formulaire
        # avec la méthode abe_encrypt, similaire à ce qui est fait pour Prescription
        record = form.save()
        
        # Gérer les professionnels assignés
        assigned_professionals = self.request.POST.getlist('assigned_to')
        record.assigned_to.set(assigned_professionals)
        
        messages.success(self.request, "Le dossier médical a été mis à jour avec succès.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('medical_record_detail', kwargs={'pk': self.object.pk})


class MedicalRecordDeleteView(UserPassesTestMixin, DeleteView):
    model = MedicalRecord
    template_name = 'accounts/medical_record_confirm_delete.html'
    success_url = reverse_lazy('medical_record_list')
    
    def test_func(self):
        record = self.get_object()
        # Vérifier si l'utilisateur a le droit de supprimer ce dossier
        if self.request.user.is_admin:
            return True
        if self.request.user == record.creator:
            return True
        return False
    
    def delete(self, request, *args, **kwargs):
        record = self.get_object()
        messages.success(request, f"Le dossier médical de {record.patient.user.get_full_name()} a été supprimé avec succès.")
        return super().delete(request, *args, **kwargs)


# Vues pour la gestion des ordonnances
class PrescriptionListView(UserPassesTestMixin, ListView):
    model = Prescription
    template_name = 'accounts/prescription_list.html'
    context_object_name = 'prescriptions'
    
    def test_func(self):
        # Seuls les médecins, les administrateurs et les praticiens peuvent voir la liste des ordonnances
        return self.request.user.is_admin or self.request.user.is_medecin or self.request.user.is_praticien
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Appliquer les filtres de recherche
        form = self.search_form
        if form.is_valid():
            search_query = form.cleaned_data.get('search_query')
            validity_days = form.cleaned_data.get('validity_days')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            
            if search_query:
                queryset = queryset.filter(
                    models.Q(consultation__patient__user__first_name__icontains=search_query) |
                    models.Q(consultation__patient__user__last_name__icontains=search_query) |
                    models.Q(consultation__patient__user__email__icontains=search_query)
                )
            
            if validity_days:
                queryset = queryset.filter(validity_days=validity_days)
            
            if date_from:
                queryset = queryset.filter(issue_date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(issue_date__lte=date_to)
        
        # Les médecins voient les ordonnances qu'ils ont créées
        if self.request.user.is_medecin or self.request.user.is_praticien:
            queryset = queryset.filter(consultation__professional=self.request.user)
        
        # Les administrateurs voient toutes les ordonnances
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = self.search_form
        return context
    
    def dispatch(self, request, *args, **kwargs):
        from .forms_search import PrescriptionSearchForm
        self.search_form = PrescriptionSearchForm(request.GET or None)
        return super().dispatch(request, *args, **kwargs)


class PatientPrescriptionListView(ListView):
    model = Prescription
    template_name = 'accounts/patient_prescriptions.html'
    context_object_name = 'prescriptions'

    def get_queryset(self):
        user = self.request.user

        # Vérifier si l'utilisateur est un patient
        try:
            patient = Patient.objects.get(user=user)
        except Patient.DoesNotExist:
            return Prescription.objects.none()

        # Filtrer les ordonnances du patient
        prescriptions = Prescription.objects.filter(consultation__patient=patient)

        # Déchiffrer le contenu de chaque ordonnance
        user_attributes = self.request.user.get_user_attributes()
        private_key = abe_keygen(user_attributes)

        for prescription in prescriptions:
            decrypted_data = None
            try:
                if prescription.encrypted_content:
                    # Convertir en format JSON si nécessaire
                    if isinstance(prescription.encrypted_content, bytes):
                        encrypted_str = prescription.encrypted_content.decode("utf-8")
                    elif isinstance(prescription.encrypted_content, str):
                        encrypted_str = prescription.encrypted_content
                    elif isinstance(prescription.encrypted_content, dict):
                        encrypted_str = json.dumps(prescription.encrypted_content)
                    else:
                        raise ValueError("Format de encrypted_content inconnu.")

                    # Déchiffrer
                    decrypted_value = abe_decrypt(
                        encrypted_str,
                        private_key,
                        user_attributes,
                        prescription.abe_policy
                    )

                    # Convertir en texte si nécessaire
                    decrypted_value = int(decrypted_value)
                    decrypted_data = decrypted_value.to_bytes(1000000, 'big').decode('utf-8')

            except Exception as e:
                print(f"Erreur lors du déchiffrement ABE : {e}")
                decrypted_data = "Impossible de déchiffrer cette ordonnance."

            # Ajouter les données déchiffrées à l'objet prescription
            prescription.decrypted_content = decrypted_data  # Attribut dynamique

        return prescriptions
import json

class PrescriptionDetailView(UserPassesTestMixin, DetailView):
    model = Prescription 
    template_name = 'accounts/prescription_detail.html'
    context_object_name = 'prescription'

    def test_func(self):
        prescription = self.get_object()
        user = self.request.user

        # Si l'utilisateur est un admin, il a accès
        if user.is_admin:
            return True

        # Si l'utilisateur est le médecin qui a créé l'ordonnance, il a accès
        if user == prescription.consultation.professional:
            return True

        # Vérifier si l'utilisateur est un patient et si c'est bien son ordonnance
        if user.is_patient and hasattr(user, 'patient_profile') and prescription.consultation.patient == user.patient_profile:
            return True

        return False


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prescription = self.get_object()
        
        # Récupérer dynamiquement les attributs ABE de l'utilisateur
        user_attributes = self.request.user.get_user_attributes()
        print(f"DEBUG: Attributs utilisateur: {user_attributes}")
        # Générer la clé privée ABE à partir des attributs
        private_key = abe_keygen(user_attributes)
        # Récupérer la politique ABE associée à cette ordonnance
        policy_str = prescription.abe_policy
        print("la politique necessaire 11111" ,policy_str)
        
        decrypted_content = None
        try:
            if prescription.encrypted_content:
                # On souhaite toujours passer une chaîne JSON à abe_decrypt.
                if isinstance(prescription.encrypted_content, bytes):
                    encrypted_str = prescription.encrypted_content.decode("utf-8")
                elif isinstance(prescription.encrypted_content, str):
                    encrypted_str = prescription.encrypted_content
                elif isinstance(prescription.encrypted_content, dict):
                    encrypted_str = json.dumps(prescription.encrypted_content)
                else:
                    raise ValueError("Format de encrypted_content inconnu.")
                
                # Pour vérifier que la chaîne correspond bien à un dictionnaire attendu,
                # on peut la désérialiser et afficher le type.
                try:
                    data = json.loads(encrypted_str)
                    print("DEBUG: Type de data après json.loads:", type(data))
                except Exception as ex:
                    print("DEBUG: Erreur lors du json.loads:", ex)
                
                # Appeler abe_decrypt en lui fournissant la chaîne JSON
                decrypted_value = abe_decrypt(
                    encrypted_str,
                    private_key,
                    user_attributes,
                    policy_str
                )
                decrypted_value=int(decrypted_value)
                decrypted_content = decrypted_value.to_bytes(10000000, 'big').decode('utf-8')


        except Exception as e:
            error_message = f"Erreur lors du déchiffrement ABE : {e}. "
            if "list indices must be integers" in str(e):
                error_message += ("Cela indique que, dans la donnée chiffrée, "
                                  "une liste est utilisée là où une structure indexable par clé est attendue. "
                                  "Vérifiez que le JSON fourni correspond exactement au format requis par abe_decrypt.")
            print(error_message)
            decrypted_content = None
        
        context['decrypted_content'] = decrypted_content
        return context




class PrescriptionCreateView(UserPassesTestMixin, CreateView):
    model = Prescription
    form_class = PrescriptionForm
    template_name = 'accounts/prescription_form.html'
    success_url = reverse_lazy('prescription_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.is_authenticated:
            kwargs['user'] = self.request.user
        return kwargs
    
    def test_func(self):
        # Seuls les médecins et les praticiens peuvent créer des ordonnances
        return self.request.user.is_medecin or self.request.user.is_praticien
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.is_authenticated:
            kwargs['user'] = self.request.user
        return kwargs
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filtrer les consultations pour n'afficher que celles du médecin connecté
        form.fields['consultation'].queryset = Consultation.objects.filter(professional=self.request.user)
        
        # Récupérer l'ID du patient depuis les paramètres GET (si disponible)
        patient_id = self.request.GET.get('patient_id')
        if patient_id:
            try:
                patient = Patient.objects.get(id=patient_id)
                form.fields['patient'].initial = patient
            except Patient.DoesNotExist:
                pass
        
        return form
    
    def form_valid(self, form):
        prescription = form.save(commit=False)
        content = form.cleaned_data.get('content')
        
        # Si aucune consultation n'est sélectionnée mais qu'un patient est choisi,
        # créer une nouvelle consultation
        if not prescription.consultation and form.cleaned_data.get('patient') and self.request.user:
            consultation = Consultation.objects.create(
                patient=form.cleaned_data['patient'],
                professional=self.request.user,
                encrypted_notes=b'Consultation pour ordonnance',
                abe_policy=form.cleaned_data['abe_policy']
            )
            prescription.consultation = consultation
        
        # Chiffrer le contenu de l'ordonnance
        if content:
            prescription.encrypted_content = content.encode('utf-8')
            
        prescription.save()
        messages.success(self.request, "L'ordonnance a été créée avec succès.")
        return super().form_valid(form)


class PrescriptionUpdateView(UserPassesTestMixin, UpdateView):
    model = Prescription
    form_class = PrescriptionForm
    template_name = 'accounts/prescription_form.html'
    
    def test_func(self):
        prescription = self.get_object()
        # Vérifier si l'utilisateur a le droit de modifier cette ordonnance
        if self.request.user.is_admin:
            return True
        if self.request.user == prescription.consultation.professional:
            return True
        return False
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filtrer les consultations pour n'afficher que celles du médecin connecté
        form.fields['consultation'].queryset = Consultation.objects.filter(professional=self.request.user)
        return form
    
    def form_valid(self, form):
        messages.success(self.request, "L'ordonnance a été modifiée avec succès.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('prescription_detail', kwargs={'pk': self.object.pk})


class PrescriptionDeleteView(UserPassesTestMixin, DeleteView):
    model = Prescription
    template_name = 'accounts/prescription_confirm_delete.html'
    success_url = reverse_lazy('prescription_list')
    
    def test_func(self):
        prescription = self.get_object()
        # Vérifier si l'utilisateur a le droit de supprimer cette ordonnance
        if self.request.user.is_admin:
            return True
        if self.request.user == prescription.consultation.professional:
            return True
        return False
    
    def delete(self, request, *args, **kwargs):
        prescription = self.get_object()
        messages.success(request, f"L'ordonnance pour {prescription.consultation.patient.user.get_full_name()} a été supprimée avec succès.")
        return super().delete(request, *args, **kwargs)


# Vue pour afficher les détails d'une consultation
class ConsultationDetailView(UserPassesTestMixin, DetailView):
    model = Consultation
    template_name = 'accounts/consultation_detail.html'
    context_object_name = 'consultation'
    
    def test_func(self):
        consultation = self.get_object()
        # Vérifier si l'utilisateur a le droit de voir cette consultation
        if self.request.user.is_admin:
            return True
        if self.request.user == consultation.professional:
            return True
        # Permettre au patient de voir sa propre consultation
        if self.request.user.is_patient and hasattr(self.request.user, 'patient_profile'):
            if self.request.user.patient_profile == consultation.patient:
                return True
        # Ajouter d'autres conditions d'accès si nécessaire
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consultation = self.get_object()
        
        # Récupérer les ordonnances associées à cette consultation
        context['prescriptions'] = consultation.prescriptions.all()
        
        # Tenter de déchiffrer les notes de consultation avec IBE
        decrypted_notes = None
        try:
            if consultation.encrypted_notes:
                # Importer la fonction de déchiffrement IBE
                from .ibe_config import ibe_decrypt
                
                # Récupérer l'identité IBE (stockée dans le champ abe_policy pour compatibilité)
                identity = self.request.user.email
                
                # Préparer les données chiffrées pour le déchiffrement
                
                
                # Déchiffrer les notes avec IBE
                decrypted_value = ibe_decrypt(consultation.encrypted_notes, identity)
                
                # Vérifier que le déchiffrement a réussi
                if decrypted_value and not decrypted_value.startswith('Erreur'):
                    decrypted_notes = decrypted_value
        except Exception as e:
            print(f"Erreur lors du déchiffrement IBE : {e}")
            decrypted_notes = 100
        
        context['decrypted_notes'] = decrypted_value 
        return context


# Vue pour mettre à jour une consultation
class ConsultationUpdateView(UserPassesTestMixin, UpdateView):
    model = Consultation
    template_name = 'accounts/consultation_form.html'
    form_class = ConsultationForm
    
    def test_func(self):
        consultation = self.get_object()
        # Vérifier si l'utilisateur a le droit de modifier cette consultation
        if self.request.user.is_admin:
            return True
        
        # Vérifier si l'utilisateur est le professionnel qui a créé la consultation
        if self.request.user == consultation.professional:
            # Vérifier si l'utilisateur peut déchiffrer les notes avec IBE
            try:
                # L'identité IBE est stockée dans le champ abe_policy pour compatibilité
                identity = consultation.abe_policy
                
                # Tenter de déchiffrer les notes pour vérifier l'accès
                if consultation.encrypted_notes:
                    encrypted_str = None
                    if isinstance(consultation.encrypted_notes, bytes):
                        try:
                            encrypted_str = consultation.encrypted_notes.decode('utf-8')
                        except UnicodeDecodeError:
                            return False
                    else:
                        encrypted_str = str(consultation.encrypted_notes)
                    
                    # Vérifier si l'identité IBE existe
                    if not identity:
                        return False
                    
                    # Essayer de déchiffrer pour vérifier l'accès
                    from .ibe_config import ibe_decrypt
                    try:
                        # Pour IBE, nous n'avons besoin que de l'identité (email)
                        decrypted_value = ibe_decrypt(encrypted_str, identity)
                        # Si on arrive ici sans exception, l'utilisateur a accès
                        return True
                    except Exception as e:
                        print(f"Erreur lors de la vérification de l'accès IBE: {e}")
                        messages.error(self.request, "Vous n'avez pas accès à cette consultation.")
                        return False
            except Exception as e:
                print(f"Erreur lors de la vérification de l'accès: {e}")
                return False
        
        return False
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Le chiffrement est maintenant géré dans le formulaire
        consultation = form.save()
        messages.success(self.request, "La consultation a été mise à jour avec succès.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('consultation_detail', kwargs={'pk': self.object.pk})
    
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            messages.error(request, f"Vous ne possédez pas les attributs nécessaires pour modifier cette consultation: {str(e)}")
            return redirect('consultation_list')


# Vue pour afficher les détails d'une consultation


class ConsultationListView(UserPassesTestMixin, ListView):
    model = Consultation
    template_name = 'accounts/consultation_list.html'
    context_object_name = 'consultations'

    def get_queryset(self):
        queryset = Consultation.objects.filter(patient__user=self.request.user) if self.request.user.is_patient else Consultation.objects.all()
        
        # Appliquer les filtres de recherche
        form = self.search_form
        if form.is_valid():
            search_query = form.cleaned_data.get('search_query')
            professional = form.cleaned_data.get('professional')
            follow_up_required = form.cleaned_data.get('follow_up_required')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            
            if search_query:
                queryset = queryset.filter(
                    models.Q(patient__user__first_name__icontains=search_query) |
                    models.Q(patient__user__last_name__icontains=search_query) |
                    models.Q(patient__user__email__icontains=search_query)
                )
            
            if professional:
                queryset = queryset.filter(professional=professional)
            
            if follow_up_required is not None and follow_up_required != '':
                queryset = queryset.filter(follow_up_required=follow_up_required == 'True')
            
            if date_from:
                queryset = queryset.filter(date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(date__lte=date_to)
        
        return queryset
    
    def test_func(self):
        # Autoriser uniquement les utilisateurs qui sont des médecins
        return self.request.user.is_authenticated and (self.request.user.is_medecin or self.request.user.is_admin or self.request.user.is_praticien)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = self.search_form
        return context
    
    def dispatch(self, request, *args, **kwargs):
        from .forms_search import ConsultationSearchForm
        self.search_form = ConsultationSearchForm(request.GET or None)
        return super().dispatch(request, *args, **kwargs)

class ConsultationCreateView(UserPassesTestMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = "accounts/consultation_form.html"
    success_url = reverse_lazy('consultation_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Ajoute l'utilisateur au formulaire
        return kwargs
    
    def test_func(self):
        # Autoriser uniquement les utilisateurs qui sont des médecins ou praticiens
        return self.request.user.is_authenticated and (self.request.user.is_medecin or self.request.user.is_praticien)
    
    def form_valid(self, form):
        # Le chiffrement est géré dans le formulaire
        consultation = form.save()
        messages.success(self.request, "La consultation a été créée avec succès.")
        return super().form_valid(form)
    





class ConsultationDeleteView(UserPassesTestMixin, DeleteView):
    model = Consultation
    template_name = 'accounts/consultation_confirm_delete.html'
    success_url = reverse_lazy('consultation_list')

    def test_func(self):
        # Autoriser uniquement les utilisateurs qui sont des médecins
        return self.request.user.is_authenticated and self.request.user.is_medecin


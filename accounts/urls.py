from django.urls import path
from . import views
from . import views_lab
from . import views_patient
from . import views_radio
from .views import PatientPrescriptionListView
# Remove the LogoutView import since we're using our custom view

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    # Use our custom logout view instead
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/<str:profile_type>/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    path('user/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    
    # Routes pour la gestion des dossiers médicaux
    path('medical-records/', views.MedicalRecordListView.as_view(), name='medical_record_list'),
    path('medical-records/create/', views.MedicalRecordCreateView.as_view(), name='medical_record_create'),
    path('medical-records/<int:pk>/', views.MedicalRecordDetailView.as_view(), name='medical_record_detail'),
    path('medical-records/<int:pk>/update/', views.MedicalRecordUpdateView.as_view(), name='medical_record_update'),
    path('medical-records/<int:pk>/delete/', views.MedicalRecordDeleteView.as_view(), name='medical_record_delete'),
    
    # Routes pour la gestion des consultations
    path('consultations/<int:pk>/', views.ConsultationDetailView.as_view(), name='consultation_detail'),
    path('consultations/<int:pk>/update/', views.ConsultationUpdateView.as_view(), name='consultation_update'),
    
    # Routes pour la gestion des ordonnances
    path('mes-prescriptions/', PatientPrescriptionListView.as_view(), name='patient_prescriptions'),
    path('prescriptions/', views.PrescriptionListView.as_view(), name='prescription_list'),
    path('prescriptions/create/', views.PrescriptionCreateView.as_view(), name='prescription_create'),
    path('prescriptions/<int:pk>/', views.PrescriptionDetailView.as_view(), name='prescription_detail'),
    path('prescriptions/<int:pk>/update/', views.PrescriptionUpdateView.as_view(), name='prescription_update'),
    path('prescriptions/<int:pk>/delete/', views.PrescriptionDeleteView.as_view(), name='prescription_delete'),


    path('consultations/', views.ConsultationListView.as_view(), name='consultation_list'),
    path('consultations/new/', views.ConsultationCreateView.as_view(), name='consultation_create'),
    path('consultations/<int:pk>/', views.ConsultationDetailView.as_view(), name='consultation_detail'),
    path('consultations/<int:pk>/edit/', views.ConsultationUpdateView.as_view(), name='consultation_update'),
    path('consultations/<int:pk>/delete/', views.ConsultationDeleteView.as_view(), name='consultation_delete'),
    
    # Routes pour les laborantins
    path('lab/patients/', views_lab.PatientListForLabView.as_view(), name='patient_list_lab'),
    path('lab/patients/<int:pk>/', views_lab.PatientDetailForLabView.as_view(), name='patient_detail_lab'),
    path('lab/tests/', views_lab.LabTestListView.as_view(), name='labtest_list'),
    path('lab/tests/create/', views_lab.LabTestCreateView.as_view(), name='labtest_create'),
    path('lab/tests/<int:pk>/', views_lab.LabTestDetailView.as_view(), name='labtest_detail'),
    path('lab/tests/<int:pk>/update/', views_lab.LabTestUpdateView.as_view(), name='labtest_update'),
    
    # Routes pour le dashboard patient
    path('patient/dashboard/', views_patient.patient_dashboard, name='patient_dashboard'),
    path('patient/labtests/', views_patient.PatientLabTestListView.as_view(), name='patient_labtest_list'),
    path('patient/labtests/<int:pk>/', views_patient.PatientLabTestDetailView.as_view(), name='patient_labtest_detail'),
    path('patient/labtests/request/', views_patient.PatientLabTestRequestView.as_view(), name='patient_labtest_request'),
    path('patient/radioexams/', views_patient.PatientRadioExamListView.as_view(), name='patient_radioexam_list'),
    path('patient/radioexams/<int:pk>/', views_patient.PatientRadioExamDetailView.as_view(), name='patient_radioexam_detail'),
    
    # Routes pour les radiologues
    path('radio/patients/', views_radio.PatientListForRadioView.as_view(), name='patient_list_radio'),
    path('radio/patients/<int:pk>/', views_radio.PatientDetailForRadioView.as_view(), name='patient_detail_radio'),
    path('radio/exams/', views_radio.RadioExamListView.as_view(), name='radio_exam_list'),
    path('radio/exams/create/', views_radio.RadioExamCreateView.as_view(), name='radio_exam_create'),
    path('radio/exams/<int:pk>/', views_radio.RadioExamDetailView.as_view(), name='radio_exam_detail'),
    path('radio/exams/<int:pk>/update/', views_radio.RadioExamUpdateView.as_view(), name='radio_exam_update'),
]
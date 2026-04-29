"""
URL configuration for jobee project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from blog import views 


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('analyse/', views.analyses, name='analyses'),
    path('producteur/', views.ajouter_producteur, name='ajouter_producteur'),
    path('ajouter/', views.ajouter_recolte, name='ajouter_recolte'),
    path('liste-producteurs/', views.liste_producteurs, name='liste_producteurs'),
    
    # URLs pour les exports
    path('export/excel/', views.export_excel, name='export_excel'),
    path('export/pdf/', views.export_pdf, name='export_pdf'),
    path('alertes/generer/', views.generer_alertes, name='generer_alertes'),
    path('importer-donnees/', views.importer_donnees, name='importer_donnees'),
]
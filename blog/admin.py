from django.contrib import admin
from .models import Producteur, Recolte

# Register your models here.

@admin.register(Producteur)
class ProducteurAdmin(admin.ModelAdmin):
    list_display = ['nom', 'region', 'contact', 'date_enregistrement']
    list_filter  = ['region', 'date_enregistrement']
    search_fields = ['nom']


@admin.register(Recolte)
class RecolteAdmin(admin.ModelAdmin):  # ← corrigé : était ProducteurAdmin
    list_display = [
        'producteur',
        'culture',
        'superficie',
        'rendement',        # ← AJOUTÉ
        'prix_vente',
        'cout_production',
        'date_recolte'
    ]
    list_filter  = ['culture', 'date_recolte']
    search_fields = ['producteur__nom']  # ← corrigé : accès via FK
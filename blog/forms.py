from django import forms 
from .models import Producteur, Recolte

# Creation des formulaires 
REGIONS = [
    ('NORD', 'Nord'),
    ('SUD', 'Sud'),
    ('EST', 'Est'),
    ('OUEST', 'Ouest'),
    ('CENTRE', 'Centre'),
    ('LITTORAL', 'Littoral'),
    ('ADAMAOUA', 'Adamaoua'),
    ('EXTREME-NORD', 'Extrême-Nord'),
    ('NORD-OUEST', 'Nord-Ouest'),
    ('SUD-OUEST', 'Sud-Ouest'),
]

TAILWIND_INPUT = {
    "class": "w-full bg-black/20 text-white border border-white/20 rounded-xl px-4 py-3 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-500/30 transition"
}


class ProducteurForm(forms.ModelForm):
    region = forms.ChoiceField(
        choices=REGIONS,
        widget=forms.Select(attrs={
            'class': 'w-full bg-black/20 text-white border border-white/20 rounded-xl px-4 py-3 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-500/30 transition',
            'required': True,
        }),
        label='Region de Production'
    )

    class Meta:
        model = Producteur
        fields = ['nom', 'region', 'contact']
        widgets = {
            'nom': forms.TextInput(attrs={
                **TAILWIND_INPUT,
                'placeholder': 'Nom du Producteur',
            }),
            'contact': forms.TextInput(attrs={
                **TAILWIND_INPUT,
                'placeholder': 'Contact du Producteur',
                'required': True
            })
        }
        labels = {
            'nom': 'Nom Complet',
            'contact': 'Contact'
        }


class RecolteForm(forms.ModelForm):
    CULTURES = [
        ('', 'Selectionner une culture'),
        ('CAFE', 'Café'),
        ('CACAO', 'Cacao'),
        ('BANANE', 'Banane'),
        ('MAIS', 'Maïs'),
        ('MANIOC', 'Manioc'),
    ]

    culture = forms.ChoiceField(
        choices=CULTURES,
        widget=forms.Select(attrs={
            'class': 'w-full bg-black/20 text-white border border-white/20 rounded-xl px-4 py-3 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-500/30 transition',
            'placeholder': 'Type de culture',
        }),
        label='Type de Culture'
    )

    class Meta:
        model = Recolte
        fields = [
            'producteur',
            'culture',
            'superficie',
            'rendement',        # ← AJOUTÉ
            'prix_vente',
            'cout_production',
            'date_recolte'
        ]
        widgets = {
            'producteur': forms.Select(attrs={
                **TAILWIND_INPUT,
            }),
            'superficie': forms.NumberInput(attrs={
                **TAILWIND_INPUT,
                'placeholder': 'Superficie en hectare',
                'step': '0.01'
            }),
            'rendement': forms.NumberInput(attrs={   # ← AJOUTÉ
                **TAILWIND_INPUT,
                'placeholder': 'Rendement en kg/hectare',
                'step': '0.1',
                'min': '0',
            }),
            'prix_vente': forms.NumberInput(attrs={
                **TAILWIND_INPUT,
                'placeholder': 'Prix de vente (FCFA)',
                'step': '100'
            }),
            'cout_production': forms.NumberInput(attrs={
                **TAILWIND_INPUT,
                'placeholder': 'Coût de production (FCFA)',
                'step': '100'
            }),
            'date_recolte': forms.DateInput(attrs={
                **TAILWIND_INPUT,
                'type': 'date',
            })
        }
        labels = {
            'producteur': 'Producteur',
            'culture': 'Type de culture',
            'superficie': 'Superficie (en hectare)',
            'rendement': 'Rendement (kg/hectare)',   # ← AJOUTÉ
            'prix_vente': 'Prix de vente (FCFA)',
            'cout_production': 'Coût Production (FCFA)',
            'date_recolte': 'Date de récolte',
        }
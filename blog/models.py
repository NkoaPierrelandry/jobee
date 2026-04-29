from django.db import models

class Producteur(models.Model):
    nom = models.CharField(max_length=100, verbose_name='nom')
    region = models.CharField(max_length=100)
    contact = models.CharField(max_length=20, blank=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_enregistrement']

    def __str__(self):
        return self.nom


class Recolte(models.Model):
    producteur = models.ForeignKey(
        Producteur,
        on_delete=models.CASCADE,
        related_name='recoltes'
    )
    culture = models.CharField(max_length=100)
    superficie = models.FloatField(help_text="En hectares")
    rendement = models.FloatField(help_text="En kg/hectare", default=0)   
    prix_vente = models.FloatField(help_text="En FCFA")
    cout_production = models.FloatField(help_text="En FCFA")
    date_recolte = models.DateField()

    class Meta:
        ordering = ['-date_recolte']  # Ajout d'un tri par défaut

    def __str__(self):
        return f"{self.producteur.nom} - {self.culture}"

    @property
    def benefice(self):
        """Calcule le bénéfice : (prix_vente * superficie * rendement) - cout_production"""
        revenu = self.prix_vente * self.superficie * self.rendement
        return revenu - self.cout_production

    @property
    def revenu_total(self):
        """Calcule le revenu total : prix_vente * superficie * rendement"""
        return self.prix_vente * self.superficie * self.rendement


class Alerte(models.Model):
    TYPES = (
        ('info', 'Information'),
        ('warning', 'Attention'),
        ('danger', 'Danger'),
        ('success', 'Succès'),
    )
    
    titre = models.CharField(max_length=200)
    message = models.TextField()
    type_alerte = models.CharField(max_length=20, choices=TYPES)
    date_creation = models.DateTimeField(auto_now_add=True)
    est_lu = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date_creation']
    
    def __str__(self):
        return self.titre
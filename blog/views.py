from django.shortcuts import render, redirect
from django.contrib import messages  # ← AJOUT DE L'IMPORT MANQUANT
from .models import Producteur, Recolte, Alerte
from .forms import RecolteForm, ProducteurForm
from django.db.models import Sum, Avg
import pandas as pd
from datetime import datetime  
from django.http import HttpResponse
from io import BytesIO
import plotly.io as pio
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
import os
from google import genai
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)


# Create your views here.
def ajouter_producteur(request):
    if request.method == "POST":
        form = ProducteurForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('liste_producteurs')
    else:
        form = ProducteurForm()

    return render(request, "pages/ajouter_producteur.html", {
        "form": form
    })


def home(request):
    return render(request, "shop/home.html")


def ajouter_recolte(request):
    if request.method == "POST":
        form = RecolteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = RecolteForm()

    return render(
        request,
        "pages/ajouter_recolte.html",
        {"form": form}
    )


def liste_producteurs(request):
    producteurs = Producteur.objects.all().order_by('nom')
    return render(request, 'pages/liste_producteurs.html', {
        'producteurs': producteurs
    })


def analyses(request):
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import confusion_matrix

    # Récupérer les alertes non lues
    alertes = Alerte.objects.filter(est_lu=False)[:5]

    recoltes = Recolte.objects.all().values(
        'superficie',
        'rendement',
        'prix_vente',
        'cout_production',
        'culture',
    )

    df = pd.DataFrame(recoltes).dropna()

    # =========================
    # 📌 ANALYSE DESCRIPTIVE
    # =========================
    total_superficie = df['superficie'].sum() if len(df) > 0 else 0
    total_revenu = df['prix_vente'].sum() if len(df) > 0 else 0
    cout_total = df['cout_production'].sum() if len(df) > 0 else 0
    benefice = total_revenu - cout_total
    total_recoltes = df.shape[0]

    # Stats descriptives complètes
    stats = {}
    if len(df) > 0:
        stats = {
            "superficie_moy": round(df['superficie'].mean(), 2),
            "superficie_med": round(df['superficie'].median(), 2),
            "superficie_std": round(df['superficie'].std(), 2),
            "rendement_moy": round(df['rendement'].mean(), 2),
            "rendement_med": round(df['rendement'].median(), 2),
            "rendement_std": round(df['rendement'].std(), 2),
            "prix_moy": round(df['prix_vente'].mean(), 2),
            "prix_med": round(df['prix_vente'].median(), 2),
            "prix_std": round(df['prix_vente'].std(), 2),
        }

    # -------------------------
    # GRAPHE 1 — Histogramme rendements
    # -------------------------
    graph_hist = None
    if len(df) > 0:
        fig = px.histogram(
            df,
            x='rendement',
            nbins=10,
            title='Distribution des rendements (kg/ha)',
            color_discrete_sequence=['#22c55e'],
            template='plotly_dark',
            labels={'rendement': 'Rendement (kg/ha)', 'count': 'Nombre'}
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            title_font_size=16,
        )
        graph_hist = fig.to_json()

    # -------------------------
    # GRAPHE 2 — Boxplot
    # -------------------------
    graph_box = None
    if len(df) > 0:
        fig2 = go.Figure()
        fig2.add_trace(go.Box(
            y=df['superficie'],
            name='Superficie (ha)',
            marker_color='#22c55e'
        ))
        fig2.add_trace(go.Box(
            y=df['rendement'],
            name='Rendement (kg/ha)',
            marker_color='#3b82f6'
        ))
        fig2.add_trace(go.Box(
            y=df['prix_vente'],
            name='Prix vente (FCFA)',
            marker_color='#f59e0b'
        ))
        fig2.update_layout(
            title='Boxplot des variables agricoles',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            title_font_size=16,
            template='plotly_dark',
        )
        graph_box = fig2.to_json()

    # -------------------------
    # GRAPHE 3 — Heatmap corrélations
    # -------------------------
    graph_heatmap = None
    if len(df) > 1:
        corr = df[['superficie', 'rendement', 'prix_vente', 'cout_production']].corr()
        fig3 = px.imshow(
            corr,
            text_auto=True,
            color_continuous_scale='RdYlGn',
            title='Matrice de corrélation',
            template='plotly_dark',
        )
        fig3.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            title_font_size=16,
        )
        graph_heatmap = fig3.to_json()

    # -------------------------
    # GRAPHE 4 — Barres par culture
    # -------------------------
    graph_culture = None
    if len(df) > 0 and 'culture' in df.columns:
        culture_group = df.groupby('culture')['rendement'].mean().reset_index()
        fig4 = px.bar(
            culture_group,
            x='culture',
            y='rendement',
            title='Rendement moyen par culture',
            color='rendement',
            color_continuous_scale='Greens',
            template='plotly_dark',
            labels={'culture': 'Culture', 'rendement': 'Rendement moyen (kg/ha)'}
        )
        fig4.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            title_font_size=16,
        )
        graph_culture = fig4.to_json()

    # =========================
    # 📈 GRAPHIQUE REGRESSION SIMPLE
    # =========================
    graph_reg_simple = None
    if len(df) > 1:
        fig_reg = px.scatter(
            df, x='superficie', y='prix_vente',
            title='Régression Simple : Prix vs Superficie',
            labels={'superficie': 'Superficie (ha)', 'prix_vente': 'Prix de vente (FCFA)'},
            trendline='ols',
            trendline_color_override='red',
            template='plotly_dark'
        )
        fig_reg.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white'
        )
        graph_reg_simple = fig_reg.to_json()

    # =========================
    # 📊 GRAPHIQUE REGRESSION MULTIPLE
    # =========================
    graph_reg_multiple = None
    if len(df) > 1:
        X_multi = df[['superficie', 'cout_production']]
        y_multi = df['prix_vente']
        model_multi = LinearRegression()
        model_multi.fit(X_multi, y_multi)
        y_pred = model_multi.predict(X_multi)
        
        fig_multi = go.Figure()
        fig_multi.add_trace(go.Scatter(
            x=y_multi, y=y_pred, mode='markers',
            marker=dict(color='blue', size=10),
            name='Prédictions'
        ))
        fig_multi.add_trace(go.Scatter(
            x=[y_multi.min(), y_multi.max()],
            y=[y_multi.min(), y_multi.max()],
            mode='lines', name='Idéal',
            line=dict(color='red', dash='dash')
        ))
        fig_multi.update_layout(
            title='Régression Multiple : Valeurs Prédites vs Réelles',
            xaxis_title='Valeurs Réelles (FCFA)',
            yaxis_title='Valeurs Prédites (FCFA)',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white'
        )
        graph_reg_multiple = fig_multi.to_json()

    # =========================
    # 📉 GRAPHIQUE PCA 2D
    # =========================
    graph_pca = None
    if len(df) >= 2:
        X_pca = df[['superficie', 'prix_vente', 'cout_production']]
        n_components = min(2, X_pca.shape[1], len(df))
        pca = PCA(n_components=n_components)
        result = pca.fit_transform(X_pca)
        variance = pca.explained_variance_ratio_.tolist()
        
        fig_pca = px.scatter(
            x=[p[0] for p in result],
            y=[p[1] for p in result] if len(result[0]) > 1 else [0]*len(result),
            title='Analyse en Composantes Principales (PCA)',
            labels={'x': f'PC1 ({variance[0]*100:.1f}%)',
                    'y': f'PC2 ({variance[1]*100:.1f}%)' if len(variance) > 1 else 'PC2'},
            template='plotly_dark'
        )
        fig_pca.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white'
        )
        graph_pca = fig_pca.to_json()

    # =========================
    # 🧠 MATRICE DE CONFUSION
    # =========================
    graph_confusion = None
    if len(df) > 1:
        df['benefice'] = df['prix_vente'] - df['cout_production']
        df['classe'] = df['benefice'].apply(lambda x: 1 if x > 0 else 0)
        X_class = df[['superficie', 'prix_vente', 'cout_production']]
        y_class = df['classe']
        if len(y_class.unique()) >= 2:
            model_class = LogisticRegression(max_iter=1000)
            model_class.fit(X_class, y_class)
            y_pred_class = model_class.predict(X_class)
            cm = confusion_matrix(y_class, y_pred_class)
            
            fig_cm = px.imshow(
                cm, text_auto=True,
                labels=dict(x="Prédictions", y="Réalité", color="Nombre"),
                x=['Classe 0', 'Classe 1'],
                y=['Classe 0', 'Classe 1'],
                title='Matrice de Confusion',
                color_continuous_scale='Blues',
                template='plotly_dark'
            )
            fig_cm.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='white'
            )
            graph_confusion = fig_cm.to_json()

    # =========================
    # 🔵 GRAPHIQUE CLUSTERING
    # =========================
    graph_cluster = None
    if len(df) >= 3:
        X_cluster = df[['superficie', 'prix_vente']].dropna()
        n_clusters = min(3, len(X_cluster))
        kmeans_cluster = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans_cluster.fit_predict(X_cluster)
        
        fig_cluster = px.scatter(
            x=X_cluster['superficie'], y=X_cluster['prix_vente'],
            color=cluster_labels.astype(str),
            title=f'Clustering K-means ({n_clusters} clusters) - Superficie vs Prix',
            labels={'x': 'Superficie (ha)', 'y': 'Prix de vente (FCFA)'},
            template='plotly_dark'
        )
        fig_cluster.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white'
        )
        graph_cluster = fig_cluster.to_json()

    # =========================
    # 📉 REGRESSION SIMPLE (stats)
    # =========================
    reg_simple = {}
    if len(df) > 1:
        X = df[['superficie']]
        y = df['prix_vente']
        model = LinearRegression()
        model.fit(X, y)
        reg_simple = {
            "coef": round(model.coef_[0], 2),
            "intercept": round(model.intercept_, 2),
            "score": round(model.score(X, y), 2)
        }

    # =========================
    # 📊 REGRESSION MULTIPLE (stats)
    # =========================
    reg_multiple = {}
    if len(df) > 1:
        X = df[['superficie', 'cout_production']]
        y = df['prix_vente']
        model = LinearRegression()
        model.fit(X, y)
        reg_multiple = {
            "coef": [round(c, 2) for c in model.coef_.tolist()],
            "intercept": round(model.intercept_, 2),
            "score": round(model.score(X, y), 2)
        }

    # =========================
    # 🧠 CLASSIFICATION SUPERVISEE (stats)
    # =========================
    classification = None
    if len(df) > 1:
        df['benefice'] = df['prix_vente'] - df['cout_production']
        df['classe'] = df['benefice'].apply(lambda x: 1 if x > 0 else 0)
        X = df[['superficie', 'prix_vente', 'cout_production']]
        y = df['classe']
        if len(y.unique()) >= 2:
            model = LogisticRegression(max_iter=1000)
            model.fit(X, y)
            classification = {
                "accuracy": round(model.score(X, y), 2)
            }

    # =========================
    # 🔵 CLUSTERING (K-MEANS) stats
    # =========================
    clusters = None
    if len(df) >= 3:
        X = df[['superficie', 'prix_vente', 'cout_production']]
        n_clusters = min(3, len(df))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df['cluster'] = kmeans.fit_predict(X)
        clusters = df['cluster'].value_counts().to_dict()

    # =========================
    # 📉 PCA stats
    # =========================
    pca_data = None
    if len(df) >= 2:
        X = df[['superficie', 'prix_vente', 'cout_production']]
        n_components = min(2, X.shape[1], len(df))
        pca = PCA(n_components=n_components)
        result = pca.fit_transform(X)
        pca_data = {
            "variance_expliquee": [round(v, 4) for v in pca.explained_variance_ratio_.tolist()],
            "data": result.tolist()
        }

    # =========================
    # 💡 RECOMMANDATIONS PERSONNALISEES
    # =========================
    recommendations = []
    
    if len(df) > 0:
        # 1. Recommandation basée sur le bénéfice
        if benefice < 0:
            recommendations.append({
                "type": "warning",
                "icon": "⚠️",
                "title": "Bénéfice négatif détecté",
                "message": f"Votre bénéfice actuel est de {benefice} FCFA. Essayez de réduire les coûts de production ou d'augmenter les prix de vente.",
                "action": "Augmenter les prix ou réduire les coûts"
            })
        elif benefice < 10000:
            recommendations.append({
                "type": "info",
                "icon": "📈",
                "title": "Bénéfice faible",
                "message": f"Votre bénéfice est de {benefice} FCFA. Envisagez d'optimiser votre production.",
                "action": "Augmenter la superficie cultivée"
            })
        else:
            recommendations.append({
                "type": "success",
                "icon": "🎉",
                "title": "Bon bénéfice !",
                "message": f"Félicitations ! Votre bénéfice de {benefice} FCFA est excellent.",
                "action": "Maintenez vos bonnes pratiques"
            })
        
        # 2. Recommandation sur le rendement
        rendement_moy = df['rendement'].mean()
        if rendement_moy < 1000:
            recommendations.append({
                "type": "warning",
                "icon": "🌾",
                "title": "Rendement faible",
                "message": f"Votre rendement moyen est de {rendement_moy:.0f} kg/ha, ce qui est inférieur à la moyenne.",
                "action": "Améliorez l'irrigation et la fertilisation"
            })
        elif rendement_moy > 3000:
            recommendations.append({
                "type": "success",
                "icon": "🌟",
                "title": "Excellent rendement !",
                "message": f"Votre rendement de {rendement_moy:.0f} kg/ha est exceptionnel.",
                "action": "Partagez vos techniques avec d'autres agriculteurs"
            })
        
        # 3. Recommandation sur la superficie
        superficie_moy = df['superficie'].mean()
        if superficie_moy < 0.5:
            recommendations.append({
                "type": "info",
                "icon": "📏",
                "title": "Petite superficie",
                "message": f"Vos parcelles sont petites ({superficie_moy:.2f} ha en moyenne).",
                "action": "Optimisez chaque mètre carré avec des cultures à haute valeur"
            })
        
        # 4. Recommandation sur la corrélation superficie/prix
        if len(df) > 1 and reg_simple:
            if reg_simple.get('coef', 0) > 100:
                recommendations.append({
                    "type": "tip",
                    "icon": "💡",
                    "title": "Corrélation positive forte",
                    "message": f"Chaque hectare supplémentaire augmente le revenu de {reg_simple['coef']:.0f} FCFA.",
                    "action": "Investissez dans l'agrandissement de vos parcelles"
                })
        
        # 5. Recommandation sur la culture la plus rentable
        if 'culture' in df.columns and len(df['culture'].unique()) > 1:
            culture_rentable = df.groupby('culture').apply(
                lambda x: (x['prix_vente'] - x['cout_production']).mean()
            ).idxmax()
            recommendations.append({
                "type": "star",
                "icon": "⭐",
                "title": "Culture la plus rentable",
                "message": f"La culture la plus rentable est : {culture_rentable}",
                "action": "Augmentez la surface de cette culture"
            })
        
        # 6. Recommandation PCA (réduction de dimensionnalité)
        if pca_data and len(pca_data.get('variance_expliquee', [])) >= 2:
            var_total = sum(pca_data['variance_expliquee'][:2]) * 100
            if var_total > 80:
                recommendations.append({
                    "type": "insight",
                    "icon": "📊",
                    "title": "Données bien structurées",
                    "message": f"Les 2 premières composantes expliquent {var_total:.0f}% de vos données.",
                    "action": "Utilisez ces 2 variables principales pour vos analyses"
                })
        
        # 7. Recommandation sur les clusters
        if clusters:
            max_cluster = max(clusters.values())
            total = sum(clusters.values())
            pourcentage = (max_cluster / total) * 100
            if pourcentage > 60:
                recommendations.append({
                    "type": "info",
                    "icon": "🔵",
                    "title": "Groupe majoritaire identifié",
                    "message": f"{pourcentage:.0f}% de vos données sont dans un même groupe.",
                    "action": "Analysez ce groupe pour comprendre ses caractéristiques"
                })
        
        # 8. Recommandation classification
        if classification:
            accuracy = classification.get('accuracy', 0)
            if accuracy > 0.8:
                recommendations.append({
                    "type": "success",
                    "icon": "🤖",
                    "title": "Prédictions fiables",
                    "message": f"Votre modèle de classification a une précision de {accuracy*100:.0f}%.",
                    "action": "Utilisez ce modèle pour prédire la rentabilité"
                })
            elif accuracy < 0.6:
                recommendations.append({
                    "type": "warning",
                    "icon": "⚠️",
                    "title": "Prédictions à améliorer",
                    "message": f"La précision de classification est faible ({accuracy*100:.0f}%).",
                    "action": "Ajoutez plus de variables pour améliorer le modèle"
                })
        
        # 9. Recommandation sur la variance des prix
        if stats and stats.get('prix_std', 0) > 500:
            recommendations.append({
                "type": "tip",
                "icon": "💰",
                "title": "Fluctuation des prix",
                "message": "Les prix de vente varient beaucoup selon les cultures.",
                "action": "Planifiez vos ventes aux périodes de prix élevés"
            })
        
        # 10. Recommandation sur le nombre de données
        if len(df) < 10:
            recommendations.append({
                "type": "info",
                "icon": "📝",
                "title": "Peu de données disponibles",
                "message": f"Vous avez seulement {len(df)} enregistrements. Plus de données = meilleures analyses !",
                "action": "Ajoutez plus de récoltes pour des analyses plus précises"
            })

    # Recommendation du jour aléatoire si pas assez de données
    if len(recommendations) == 0:
        recommendations.append({
            "type": "welcome",
            "icon": "🌱",
            "title": "Bienvenue sur AgriCam Analytics",
            "message": "Ajoutez vos premières récoltes pour recevoir des recommandations personnalisées.",
            "action": "Commencez par ajouter une récolte"
        })


    # ===========================
    # RECOMMANDATIONS IA GEMINI
    # ===========================
    recommendations = generer_recommandations_ia(
        stats=stats,
        benefice=benefice,
        reg_simple=reg_simple,
        reg_multiple=reg_multiple,
        classification=classification,
        clusters=clusters
    )

    # =========================
    # CONTEXT FINAL
    # =========================
    context = {
        "total_superficie": round(total_superficie, 2),
        "total_revenu": round(total_revenu, 2),
        "cout_total": round(cout_total, 2),
        "benefice": round(benefice, 2),
        "total_recoltes": total_recoltes,
        "stats": stats,
        "graph_hist": graph_hist,
        "graph_box": graph_box,
        "graph_heatmap": graph_heatmap,
        "graph_culture": graph_culture,
        "graph_reg_simple": graph_reg_simple,
        "graph_reg_multiple": graph_reg_multiple,
        "graph_pca": graph_pca,
        "graph_confusion": graph_confusion,
        "graph_cluster": graph_cluster,
        "reg_simple": reg_simple,
        "reg_multiple": reg_multiple,
        "classification": classification,
        "clusters": clusters,
        "pca": pca_data,
        "recommendations": recommendations,
        "alertes": alertes,
        "recommendations": recommendations,
    }

    return render(request, "pages/analyses.html", context)


# =========================
# 📊 EXPORT EXCEL
# =========================
def export_excel(request):
    """Exporte les données au format Excel"""
    recoltes = Recolte.objects.all().values(
        'producteur__nom',
        'culture', 
        'superficie', 
        'rendement', 
        'prix_vente', 
        'cout_production', 
        'date_recolte'
    )
    df = pd.DataFrame(list(recoltes))
    
    export_df = pd.DataFrame()
    
    if len(df) > 0:
        df['revenu'] = df['prix_vente'] * df['superficie'] * df['rendement']
        df['benefice'] = df['revenu'] - df['cout_production']
        
        export_df = pd.DataFrame({
            'Producteur': df['producteur__nom'],
            'Culture': df['culture'],
            'Superficie (ha)': df['superficie'].round(2),
            'Rendement (kg/ha)': df['rendement'].round(2),
            'Prix vente (FCFA)': df['prix_vente'].round(0),
            'Coût production (FCFA)': df['cout_production'].round(0),
            'Revenu (FCFA)': df['revenu'].round(0),
            'Bénéfice (FCFA)': df['benefice'].round(0),
            'Date récolte': pd.to_datetime(df['date_recolte']).dt.strftime('%d/%m/%Y')
        })
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if len(export_df) > 0:
            export_df.to_excel(writer, sheet_name='Détail des récoltes', index=False)
        else:
            pd.DataFrame({'Message': ['Aucune donnée disponible']}).to_excel(
                writer, sheet_name='Détail des récoltes', index=False
            )
        
        if len(df) > 0:
            stats_data = {
                'Indicateur': [
                    'Superficie totale (ha)',
                    'Revenu total (FCFA)',
                    'Coût total (FCFA)',
                    'Bénéfice total (FCFA)',
                    'Rendement moyen (kg/ha)',
                    'Prix vente moyen (FCFA)',
                    'Nombre total de récoltes',
                    'Nombre de cultures différentes',
                    'Date de génération'
                ],
                'Valeur': [
                    f"{df['superficie'].sum():.2f}",
                    f"{df['revenu'].sum():,.0f}",
                    f"{df['cout_production'].sum():,.0f}",
                    f"{df['benefice'].sum():,.0f}",
                    f"{df['rendement'].mean():.2f}",
                    f"{df['prix_vente'].mean():,.0f}",
                    len(df),
                    df['culture'].nunique(),
                    datetime.now().strftime('%d/%m/%Y %H:%M')
                ]
            }
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name='Statistiques', index=False)
        
        if len(df) > 0:
            resume_culture = df.groupby('culture').agg({
                'superficie': 'sum',
                'rendement': 'mean',
                'revenu': 'sum',
                'cout_production': 'sum',
                'benefice': 'sum',
                'culture': 'count'
            }).rename(columns={'culture': 'nombre_recoltes'}).round(2)
            
            resume_culture.index.name = 'Culture'
            resume_culture.columns = [
                'Superficie totale (ha)',
                'Rendement moyen (kg/ha)',
                'Revenu total (FCFA)',
                'Coût total (FCFA)',
                'Bénéfice total (FCFA)',
                'Nombre de récoltes'
            ]
            resume_culture.to_excel(writer, sheet_name='Résumé par culture')
    
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="rapport_agricole.xlsx"'
    
    return response


# =========================
# 📄 EXPORT PDF
# =========================
def export_pdf(request):
    """Exporte le rapport au format PDF"""
    recoltes = Recolte.objects.all().values(
        'culture', 'superficie', 'rendement', 'prix_vente', 'cout_production', 'date_recolte'
    )
    df = pd.DataFrame(list(recoltes))
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rapport_agricole.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#22c55e'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    elements.append(Paragraph("Rapport d'Analyse Agricole", title_style))
    elements.append(Spacer(1, 20))
    
    if len(df) > 0:
        df['revenu'] = df['prix_vente'] * df['superficie'] * df['rendement']
        revenu_total = df['revenu'].sum()
        cout_total = df['cout_production'].sum()
        benefice = revenu_total - cout_total
        
        stats_data = [
            ['Indicateur', 'Valeur'],
            ['Superficie totale', f"{df['superficie'].sum():.2f} ha"],
            ['Revenu total', f"{revenu_total:,.0f} FCFA"],
            ['Coût total', f"{cout_total:,.0f} FCFA"],
            ['Bénéfice', f"{benefice:,.0f} FCFA"],
            ['Rendement moyen', f"{df['rendement'].mean():.2f} kg/ha"],
            ['Prix vente moyen', f"{df['prix_vente'].mean():,.0f} FCFA"],
            ['Nombre de récoltes', len(df)]
        ]
        
        stats_table = Table(stats_data, colWidths=[200, 200])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#22c55e')),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (1, 0), 12),
            ('BACKGROUND', (0, 1), (1, -1), colors.beige),
            ('GRID', (0, 0), (1, -1), 1, colors.black)
        ]))
        elements.append(stats_table)
        elements.append(Spacer(1, 30))
        
        elements.append(Paragraph("Détail des récoltes", styles['Heading2']))
        elements.append(Spacer(1, 10))
        
        table_data = [
            ['Culture', 'Superficie (ha)', 'Rendement (kg/ha)', 'Prix vente (FCFA)', 'Coût (FCFA)', 'Date récolte']
        ]
        for _, row in df.head(20).iterrows():
            table_data.append([
                str(row.get('culture', 'N/A')),
                f"{row['superficie']:.2f}",
                f"{row['rendement']:.2f}",
                f"{row['prix_vente']:,.0f}",
                f"{row['cout_production']:,.0f}",
                str(row.get('date_recolte', 'N/A'))
            ])
        
        data_table = Table(table_data, colWidths=[80, 70, 70, 80, 80, 80])
        data_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(data_table)
    else:
        no_data_style = ParagraphStyle(
            'NoData',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.grey,
            alignment=TA_CENTER,
        )
        elements.append(Paragraph("Aucune donnée agricole disponible", no_data_style))
    
    doc.build(elements)
    return response


# =========================
# 🔔 GENERATION D'ALERTES
# =========================
def generer_alertes(request):
    """Génère des alertes automatiques basées sur les données"""
    
    # Supprimer les anciennes alertes
    Alerte.objects.all().delete()
    
    recoltes = Recolte.objects.all().values(
        'superficie', 'rendement', 'prix_vente', 'cout_production', 'culture'
    )
    df = pd.DataFrame(recoltes).dropna()
    
    alertes_generees = 0
    
    if len(df) > 0:
        total_revenu = df['prix_vente'].sum()
        total_cout = df['cout_production'].sum()
        benefice = total_revenu - total_cout
        
        if benefice < 0:
            Alerte.objects.create(
                titre="⚠️ Bénéfice négatif détecté !",
                message=f"Votre bénéfice est de {benefice:,.0f} FCFA. Réduisez vos coûts ou augmentez vos prix.",
                type_alerte="danger"
            )
            alertes_generees += 1
        
        rendement_moy = df['rendement'].mean()
        if rendement_moy < 1500:
            Alerte.objects.create(
                titre="🌾 Rendement préoccupant",
                message=f"Votre rendement moyen est de {rendement_moy:.0f} kg/ha, en dessous de la moyenne régionale.",
                type_alerte="warning"
            )
            alertes_generees += 1
        
        if len(df) < 5:
            Alerte.objects.create(
                titre="📊 Données insuffisantes",
                message=f"Vous n'avez que {len(df)} récoltes enregistrées. Ajoutez plus de données pour de meilleures analyses.",
                type_alerte="info"
            )
            alertes_generees += 1
        
        if 'culture' in df.columns and len(df['culture'].unique()) > 1:
            culture_rentable = df.groupby('culture').apply(
                lambda x: (x['prix_vente'] - x['cout_production']).sum()
            ).idxmax()
            
            Alerte.objects.create(
                titre="⭐ Culture star détectée",
                message=f"La culture '{culture_rentable}' est votre plus rentable. Envisagez de l'étendre !",
                type_alerte="success"
            )
            alertes_generees += 1
        
        if benefice > 100000:
            Alerte.objects.create(
                titre="🎉 Excellente performance !",
                message=f"Félicitations ! Vous avez réalisé un bénéfice de {benefice:,.0f} FCFA.",
                type_alerte="success"
            )
            alertes_generees += 1
    
    if alertes_generees == 0:
        Alerte.objects.create(
            titre="🌱 Tout va bien !",
            message="Aucune alerte particulière à signaler. Continuez vos bonnes pratiques agricoles.",
            type_alerte="success"
        )
    
    return redirect('analyses')


# =========================
# 📤 IMPORTATION DE DONNEES
# =========================
def importer_donnees(request):
    """Importe des données depuis un fichier Excel ou CSV"""
    
    if request.method == "POST" and request.FILES.get('fichier'):
        fichier = request.FILES['fichier']
        
        if fichier.name.endswith('.csv'):
            df = pd.read_csv(fichier)
        elif fichier.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(fichier, engine='openpyxl')
        else:
            messages.error(request, "Format non supporté. Utilisez CSV ou Excel.")
            return redirect('importer_donnees')
        
        df.columns = df.columns.str.lower().str.strip()
        
        mapping_colonnes = {
            'culture': ['culture', 'cultures', 'type_culture', 'nom_culture'],
            'superficie': ['superficie', 'surface', 'area', 'taille'],
            'rendement': ['rendement', 'yield', 'production', 'productivite'],
            'prix_vente': ['prix_vente', 'prix', 'price', 'prix_de_vente', 'revenu'],
            'cout_production': ['cout_production', 'cout', 'cost', 'depense', 'frais'],
            'date_recolte': ['date', 'dates', 'date_recolte', 'periode']  # ← CORRIGÉ: date_recolte au lieu de date
        }
        
        colonnes_trouvees = {}
        for champ, possibilites in mapping_colonnes.items():
            for col in df.columns:
                if col in possibilites or any(p in col for p in possibilites):
                    colonnes_trouvees[champ] = col
                    break
        
        colonnes_obligatoires = ['culture', 'superficie', 'rendement', 'prix_vente', 'cout_production']
        manquantes = [c for c in colonnes_obligatoires if c not in colonnes_trouvees]
        
        if manquantes:
            messages.error(request, f"Colonnes manquantes: {', '.join(manquantes)}. Colonnes trouvées: {list(df.columns)}")
            return redirect('importer_donnees')
        
        importes = 0
        erreurs = []
        
        for index, row in df.iterrows():
            try:
                producteur = Producteur.objects.first()
                if not producteur:
                    producteur = Producteur.objects.create(
                        nom="Producteur Importé",
                        region="Non spécifiée"
                    )
                
                date_valeur = None
                if 'date_recolte' in colonnes_trouvees:
                    try:
                        date_valeur = pd.to_datetime(row[colonnes_trouvees['date_recolte']]).date()
                    except:
                        date_valeur = None
                
                # CORRIGÉ: utiliser date_recolte au lieu de date
                Recolte.objects.create(
                    producteur=producteur,
                    culture=str(row[colonnes_trouvees['culture']]).strip(),
                    superficie=float(row[colonnes_trouvees['superficie']]),
                    rendement=float(row[colonnes_trouvees['rendement']]),
                    prix_vente=float(row[colonnes_trouvees['prix_vente']]),
                    cout_production=float(row[colonnes_trouvees['cout_production']]),
                    date_recolte=date_valeur if date_valeur else None
                )
                importes += 1
                
            except Exception as e:
                erreurs.append(f"Ligne {index + 2}: {str(e)}")
        
        if importes > 0:
            messages.success(request, f"✅ {importes} récoltes importées avec succès !")
        if erreurs:
            messages.warning(request, f"⚠️ {len(erreurs)} erreurs rencontrées. Les premières: {erreurs[:3]}")
        
        return redirect('analyses')
    
    return render(request, "pages/importer_donnees.html")


def dashboard(request):
    return render(request, 'pages/dashboard.html')



# Fonction pour les recommandations avec IA (version mise à jour)
logger = logging.getLogger(__name__)

def generer_recommandations_ia(stats, benefice, reg_simple, reg_multiple, classification, clusters):
    """Génère des recommandations personnalisées via Google Gemini"""

    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        logger.warning("GEMINI_API_KEY non configurée — recommandations IA désactivées.")
        return [
            {
                "titre": "Clé API Gemini manquante",
                "message": "Configurez la variable d'environnement GEMINI_API_KEY pour activer les recommandations IA.",
                "action": "Ajoutez GEMINI_API_KEY dans les variables d'environnement Railway.",
                "priorite": "haute"
            }
        ]

    try:
        # Initialisation du client avec la nouvelle API
        client = genai.Client(api_key=api_key)

        # Construction du prompt avec tes vraies données
        prompt = f"""
Tu es un expert en agriculture camerounaise et en analyse de données.
Analyse ces données agricoles et génère exactement 4 recommandations 
personnalisées et concrètes en français.

DONNÉES ANALYSÉES :
- Superficie moyenne : {stats.get('superficie_moy', 0)} hectares
- Superficie médiane : {stats.get('superficie_med', 0)} hectares
- Rendement moyen : {stats.get('rendement_moy', 0)} kg/ha
- Rendement médian : {stats.get('rendement_med', 0)} kg/ha
- Prix de vente moyen : {stats.get('prix_moy', 0)} FCFA
- Bénéfice total : {benefice} FCFA
- Score régression simple (R²) : {reg_simple.get('score', 'N/A') if reg_simple else 'Données insuffisantes'}
- Score régression multiple (R²) : {reg_multiple.get('score', 'N/A') if reg_multiple else 'Données insuffisantes'}
- Précision classification : {classification.get('accuracy', 'N/A') if classification else 'Données insuffisantes'}
- Nombre de clusters : {len(clusters) if clusters else 0}

INSTRUCTIONS :
Réponds UNIQUEMENT en JSON valide avec ce format exact, sans texte avant ni après :
{{
    "recommandations": [
        {{
            "titre": "Titre court et percutant",
            "message": "Analyse basée sur les données ci-dessus",
            "action": "Action concrète et spécifique à faire",
            "priorite": "haute" 
        }},
        {{
            "titre": "Titre court et percutant",
            "message": "Analyse basée sur les données ci-dessus",
            "action": "Action concrète et spécifique à faire",
            "priorite": "moyenne"
        }},
        {{
            "titre": "Titre court et percutant",
            "message": "Analyse basée sur les données ci-dessus",
            "action": "Action concrète et spécifique à faire",
            "priorite": "haute"
        }},
        {{
            "titre": "Titre court et percutant",
            "message": "Analyse basée sur les données ci-dessus",
            "action": "Action concrète et spécifique à faire",
            "priorite": "basse"
        }}
    ]
}}
"""

        # Appel à l'API avec le nouveau client
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",  # Utilisation du modèle recommandé
            contents=prompt
        )
        
        texte = response.text.strip()

        # Nettoyage du JSON (si l'API retourne du markdown)
        if '```json' in texte:
            texte = texte.split('```json')[1].split('```')[0].strip()
        elif '```' in texte:
            texte = texte.split('```')[1].split('```')[0].strip()

        # Parser le JSON
        data = json.loads(texte)
        return data.get('recommandations', [])

    except Exception as e:
        logger.error(f"Erreur Gemini avec google-genai : {e}")
        # Recommandations de secours si l'API échoue
        return [
            {
                "titre": "Service IA temporairement indisponible",
                "message": "Les recommandations personnalisées ne peuvent pas être générées pour le moment.",
                "action": "Vérifiez votre connexion internet et votre clé API Gemini.",
                "priorite": "basse"
            },
            {
                "titre": "Analyse des données disponible",
                "message": f"Bénéfice total : {benefice} FCFA",
                "action": "Consultez les graphiques et tableaux pour plus de détails.",
                "priorite": "moyenne"
            }
        ]
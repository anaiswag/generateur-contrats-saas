import streamlit as st
from docxtpl import DocxTemplate
from openai import OpenAI
import json
import io

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="ContractAI SaaS", page_icon="📝")
st.title("📝 Générateur de Contrats par IA")

# --- 2. SÉCURITÉ ET CLÉ API ---
st.sidebar.markdown("### ⚙️ Configuration")
API_KEY = st.sidebar.text_input("Votre clé API OpenAI (sk-...)", type="password")
st.sidebar.info("Cette clé n'est pas sauvegardée. Elle sert uniquement à générer ce contrat.")

# --- 3. FONCTION IA ---
def analyser_variables_avec_ia(variables_trouvees):
    """L'IA analyse les balises trouvées et crée la structure du formulaire"""
    client = OpenAI(api_key=API_KEY)
    
    prompt = f"""
    Tu es un assistant juridique expert en automatisation.
    Voici une liste de variables extraites d'un modèle de contrat Word : {list(variables_trouvees)}.
    Tu dois générer un formulaire pour l'utilisateur. 
    Renvoie UNIQUEMENT un objet JSON valide avec cette structure stricte :
    {{"champs":[
        {{"variable_exacte": "Nom_Client", "label_joli": "Nom complet du client", "type": "text"}},
        {{"variable_exacte": "Montant", "label_joli": "Montant total (€)", "type": "number"}},
        {{"variable_exacte": "Date_Debut", "label_joli": "Date de début du contrat", "type": "date"}}
    ]}}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    resultat = json.loads(response.choices[0].message.content)
    return resultat.get("champs",[])

# --- 4. INTERFACE UTILISATEUR ---
st.markdown("### Étape 1 : Uploadez votre modèle Word (.docx)")
st.info("💡 Astuce : Dans votre document Word, placez les éléments variables entre doubles accolades, par exemple : {{Nom_Entreprise}} ou {{Prix_Prestation}}.")

fichier_upload = st.file_uploader("Glissez votre contrat ici", type=["docx"])

if fichier_upload is not None:
    if not API_KEY:
        st.error("⚠️ Veuillez entrer votre clé API OpenAI dans la barre latérale à gauche pour continuer.")
        st.stop()

    # Lecture du document et extraction des variables {{...}}
    try:
        doc = DocxTemplate(fichier_upload)
        variables_detectees = doc.get_undeclared_template_variables()
    except Exception as e:
        st.error("Erreur lors de la lecture du fichier Word. Assurez-vous qu'il s'agit bien d'un .docx valide.")
        st.stop()

    if not variables_detectees:
        st.warning("⚠️ Aucune balise (ex: {{Nom}}) n'a été trouvée dans votre document.")
        st.stop()

    # Appel à l'IA pour générer le formulaire (on sauvegarde dans session_state pour ne pas recharger l'IA)
    with st.spinner("🧠 L'IA analyse votre contrat et prépare le formulaire..."):
        if "formulaire_ia" not in st.session_state:
            try:
                st.session_state.formulaire_ia = analyser_variables_avec_ia(variables_detectees)
            except Exception as e:
                st.error(f"Erreur avec l'API OpenAI. Vérifiez votre clé. Détail : {e}")
                st.stop()

    # Affichage du formulaire généré
    st.markdown("### Étape 2 : Remplissez les informations")
    
    with st.form("formulaire_contrat"):
        reponses_utilisateur = {}
        
        # On crée un champ dynamique pour chaque variable trouvée par l'IA
        for champ in st.session_state.formulaire_ia:
            var_nom = champ.get("variable_exacte")
            question = champ.get("label_joli", var_nom)
            var_type = champ.get("type", "text")
            
            if var_type == "number":
                reponses_utilisateur[var_nom] = st.number_input(question, value=0)
            elif var_type == "date":
                reponses_utilisateur[var_nom] = st.text_input(question, placeholder="JJ/MM/AAAA")
            else:
                reponses_utilisateur[var_nom] = st.text_input(question)
                
        bouton_generer = st.form_submit_button("✨ Créer mon Contrat")

    # Génération du document final
    if bouton_generer:
        with st.spinner("Génération du document avec formatage d'origine..."):
            doc.render(reponses_utilisateur)
            
            fichier_final = io.BytesIO()
            doc.save(fichier_final)
            fichier_final.seek(0)
            
            st.success("🎉 Votre contrat est prêt ! La mise en page a été conservée.")
            st.download_button(
                label="📥 Télécharger le Contrat (Word)",
                data=fichier_final,
                file_name="Contrat_Genere.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

import streamlit as st
from docxtpl import DocxTemplate
from openai import OpenAI
import json
import io
import os
import tempfile
from pdf2docx import Converter

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="ContractAI Pro", page_icon="⚖️")
st.title("⚖️ Générateur de Contrats (Word & PDF)")

# Récupération de la clé API depuis le serveur (Railway) invisible pour l'utilisateur
API_KEY = os.environ.get("OPENAI_API_KEY")

if not API_KEY:
    st.error("🚨 Erreur Serveur : La clé API OpenAI n'est pas configurée sur Railway.")
    st.stop()

# --- 2. FONCTION INTELLIGENCE ARTIFICIELLE ---
def analyser_variables_avec_ia(variables_trouvees):
    client = OpenAI(api_key=API_KEY)
    prompt = f"""
    Tu es un assistant juridique. Voici les variables d'un contrat : {list(variables_trouvees)}.
    Génère un formulaire JSON strict :
    {{"champs":[
        {{"variable_exacte": "Nom", "label_joli": "Nom complet", "type": "text"}}
    ]}}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    resultat = json.loads(response.choices[0].message.content)
    return resultat.get("champs",[])

# --- 3. INTERFACE UTILISATEUR ---
st.markdown("### Étape 1 : Importez votre modèle")
st.info("💡 Formats acceptés : .docx et .pdf. Placez vos variables entre {{...}} dans le document.")

fichier_upload = st.file_uploader("Glissez votre contrat ici", type=["docx", "pdf"])

if fichier_upload is not None:
    variables_detectees =[]
    doc = None
    
    with st.spinner("Analyse du document en cours..."):
        try:
            # SI C'EST UN WORD (.docx)
            if fichier_upload.name.endswith('.docx'):
                file_bytes = fichier_upload.read()
                fichier_en_memoire = io.BytesIO(file_bytes)
                doc = DocxTemplate(fichier_en_memoire)
                variables_detectees = doc.get_undeclared_template_variables()
                
            # SI C'EST UN PDF (.pdf)
            elif fichier_upload.name.endswith('.pdf'):
                st.toast("Conversion du PDF en cours...")
                # On sauvegarde le PDF temporairement
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                    tmp_pdf.write(fichier_upload.read())
                    pdf_path = tmp_pdf.name
                
                # On le convertit en Word en arrière-plan
                docx_path = pdf_path.replace(".pdf", ".docx")
                cv = Converter(pdf_path)
                cv.convert(docx_path)
                cv.close()
                
                # On charge le nouveau document converti
                doc = DocxTemplate(docx_path)
                variables_detectees = doc.get_undeclared_template_variables()
                
        except Exception as e:
            st.error(f"❌ Erreur lors de la lecture : {e}")
            st.stop()

    if not variables_detectees:
        st.warning("⚠️ Aucune balise (ex: {{Nom}}) trouvée. Si c'est un PDF, assurez-vous que le texte est bien lisible.")
        st.stop()

    # --- 4. CRÉATION DU FORMULAIRE ---
    with st.spinner("🧠 L'IA prépare votre formulaire..."):
        if "formulaire_ia" not in st.session_state:
            st.session_state.formulaire_ia = analyser_variables_avec_ia(variables_detectees)

    st.markdown("### Étape 2 : Remplissez les champs")
    
    with st.form("form_contrat"):
        reponses = {}
        for champ in st.session_state.formulaire_ia:
            var = champ.get("variable_exacte")
            question = champ.get("label_joli", var)
            v_type = champ.get("type", "text")
            
            if v_type == "number":
                reponses[var] = st.number_input(question, value=0)
            elif v_type == "date":
                reponses[var] = st.text_input(question, placeholder="JJ/MM/AAAA")
            else:
                reponses[var] = st.text_input(question)
                
        bouton_generer = st.form_submit_button("✨ Générer le Contrat")

    # --- 5. GÉNÉRATION FINALE ---
    if bouton_generer:
        with st.spinner("Création du document final..."):
            doc.render(reponses)
            fichier_final = io.BytesIO()
            doc.save(fichier_final)
            fichier_final.seek(0)
            
            st.success("🎉 Contrat prêt ! La mise en page est conservée.")
            st.download_button(
                label="📥 Télécharger le Contrat Rempli (.docx)",
                data=fichier_final,
                file_name="Nouveau_Contrat.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

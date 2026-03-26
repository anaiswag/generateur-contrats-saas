import streamlit as st
from docx import Document
import pandas as pd
import io
import os
import tempfile
from openai import OpenAI
from pdf2docx import Converter

st.set_page_config(page_title="ContractAI Surlignage", page_icon="🖍️", layout="wide")
st.title("🖍️ Générateur de Contrats (Par Surlignage)")
st.markdown("Surlignez vos mots dans Word • Remplissage automatique • Tableau interactif")

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    st.error("🚨 Erreur : La clé API OpenAI n'est pas configurée sur Railway.")
    st.stop()

# --- FONCTIONS ---
def extraire_mots_surlignes(chemin_fichier):
    """Parcourt tout le document et extrait les mots surlignés en jaune/autre couleur"""
    doc = Document(chemin_fichier)
    mots_trouves =[]
    
    def lire_paragraphe(p):
        for r in p.runs:
            # Si le texte a une couleur de surlignage et n'est pas vide
            if r.font.highlight_color is not None and r.text.strip():
                mots_trouves.append(r.text.strip())
                
    for p in doc.paragraphs:
        lire_paragraphe(p)
        
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    lire_paragraphe(p)
                    
    return list(set(mots_trouves)) # set() permet d'enlever les doublons

def deduire_responsable(montant, regle):
    client = OpenAI(api_key=API_KEY)
    prompt = f"Règle: '{regle}'. Le montant est de {montant}€. Qui est le responsable ? Réponds UNIQUEMENT par le nom de la personne."
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

def modifier_document(chemin_fichier, reponses_formulaire, df_tableau, mot_cle_responsable, nom_ia):
    doc = Document(chemin_fichier)
    
    # On force la réponse du responsable avec celle trouvée par l'IA
    if mot_cle_responsable in reponses_formulaire:
        reponses_formulaire[mot_cle_responsable] = nom_ia

    def remplacer_paragraphe(p):
        for r in p.runs:
            if r.font.highlight_color is not None:
                texte_original = r.text.strip()
                if texte_original in reponses_formulaire:
                    r.text = str(reponses_formulaire[texte_original])
                    r.font.highlight_color = None # Enlève le surlignage !

    for p in doc.paragraphs:
        remplacer_paragraphe(p)
        
    for table in doc.tables:
        # On repère le tableau dynamique s'il a exactement 3 colonnes !
        if len(table.columns) == 3 and len(table.rows) > 0:
            ligne_exemple = table.rows[1] if len(table.rows) > 1 else None
            
            # Ajout des lignes du site web
            for index, row_data in df_tableau.iterrows():
                new_row = table.add_row()
                new_row.cells[0].text = str(row_data.iloc[0])
                new_row.cells[1].text = str(row_data.iloc[1])
                new_row.cells[2].text = str(row_data.iloc[2])
                
            # Suppression de la ligne d'exemple surlignée du modèle
            if ligne_exemple:
                table._tbl.remove(ligne_exemple._tr)
        else:
            # Si c'est un tableau normal, on remplace juste le fluo
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        remplacer_paragraphe(p)
                        
    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out

# --- INTERFACE ---
fichier_upload = st.file_uploader("📂 Glissez votre contrat (avec vos mots surlignés)", type=["docx", "pdf"])

if fichier_upload is not None:
    chemin_travail = ""
    with st.spinner("Lecture du fichier..."):
        if fichier_upload.name.endswith('.pdf'):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                tmp_pdf.write(fichier_upload.read())
                pdf_path = tmp_pdf.name
            docx_path = pdf_path.replace(".pdf", ".docx")
            cv = Converter(pdf_path)
            cv.convert(docx_path)
            cv.close()
            chemin_travail = docx_path
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_docx:
                tmp_docx.write(fichier_upload.read())
                chemin_travail = tmp_docx.name

    mots_surlignes = extraire_mots_surlignes(chemin_travail)
    
    if not mots_surlignes:
        st.error("❌ Aucun texte surligné trouvé. Ouvrez votre Word, sélectionnez un mot, et mettez-le en surbrillance jaune.")
        st.stop()

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 Remplissez les champs trouvés")
        st.success(f"{len(mots_surlignes)} éléments surlignés détectés !")
        
        reponses = {}
        for mot in mots_surlignes:
            reponses[mot] = st.text_input(f"Remplacer '{mot}' par :", value=mot)
            
        st.markdown("---")
        st.markdown("### 🧠 Logique du Responsable")
        mot_responsable = st.selectbox("Parmi ces mots fluos, lequel désigne le Responsable ?", options=["Aucun"] + mots_surlignes)
        montant = st.number_input("Montant total du contrat (€) :", value=0)
        regle = st.text_area("Règle (ex: Si > 10000€, c'est Mme Dubois, sinon M. Martin)", value="Si le montant dépasse 10000€, c'est Mme Dubois. Sinon c'est M. Martin.")

    with col2:
        st.markdown("### 📋 Tableau de Prestations")
        st.info("Ajoutez des lignes. Elles rempliront le tableau de 3 colonnes de votre contrat.")
        df_base = pd.DataFrame([{"Description": "", "Channel": "", "Date": ""}])
        tableau_web = st.data_editor(df_base, num_rows="dynamic", use_container_width=True)

    if st.button("✨ Générer le Contrat Final", use_container_width=True):
        with st.spinner("L'IA applique la règle et crée le Word..."):
            
            nom_responsable = ""
            if mot_responsable != "Aucun":
                nom_responsable = deduire_responsable(montant, regle)
                st.info(f"💡 L'IA a déduit que le responsable est : {nom_responsable}")
                
            doc_final = modifier_document(chemin_travail, reponses, tableau_web, mot_responsable, nom_responsable)
            
            st.balloons()
            st.download_button("📥 TÉLÉCHARGER LE CONTRAT (.docx)", data=doc_final, file_name="Contrat_Final.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
